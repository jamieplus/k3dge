"""Consistency engine: orchestrates the gate evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Set

import ast
import json
import re

from k3dge.engine import contract, diff, spec_schema
from k3dge.engine.contract import _ExtractError
from k3dge.engine.diff import GitError
from k3dge.engine.manifest import Manifest, ManifestError
from k3dge.engine.models import GateReport, Violation
from k3dge.engine.pairs import PAIRS

_TEST_REF_RE = re.compile(r"`(tests/[^\s`]+)`")
_VERIFICATION_MATRIX_RE = re.compile(r"^#{2,3}\s+.*Verification Matrix", re.MULTILINE)
_PIN_LINE_RE = re.compile(
    r"^[ \t]*(?:#|//|<!--)[ \t]*k3dit:(?:pending|leftover|disputed|fixnote|fixed)\b"
)


def _without_pins(text: str) -> str:
    """Drop whole-line k3dit marker lines so transient audit pins don't trip TEMPLATE_DRIFT.

    Pins live at the finding's location on the audit line and are harvested out by Hall before
    merge (peer_contract §8 / ADR-0025 §2.7). A pin on a byte-locked PAIRS file is an audit-time
    artifact, not drift (ADR-0004 §2.1.6), so normalize both sides before comparing.
    """
    return "\n".join(ln for ln in text.splitlines() if not _PIN_LINE_RE.match(ln))


def _verification_matrix_section(content: str) -> str:
    m = _VERIFICATION_MATRIX_RE.search(content)
    return content[m.start():] if m else content


def _spec_violation_path(workspace: Path, manifest: Manifest, domain: str) -> Optional[str]:
    rel = manifest.spec_path(domain)
    return str(workspace / rel) if rel else None


def _package_prefix(manifest: Manifest, domain: str) -> str:
    """Top-level import package for the repo's domains (manifest-derived, never hardcoded).

    = basename of the longest common ancestor dir of all domains' `src`. Handles both
    `package_root` conventions without relying on `__init__.py`:
      - k3dge: `src/k3dge/{engine,cli,…}` -> `k3dge`  (package_root = src/k3dge)
      - k3dit: `src/k3dit`               -> `k3dit`   (package_root = src)
    Downstream repos use a different package name, so a baked-in `k3dge.` made the
    reverse-import ban silently no-op there (code-6).
    """
    srcs = [str(p).replace("\\", "/").strip("/")
            for p in (manifest.src_path(d) for d in manifest.domains) if p]
    own = str(manifest.src_path(domain) or "").replace("\\", "/").strip("/")
    if not srcs and own:
        srcs = [own]
    if not srcs:
        return ""
    parts = srcs[0].split("/")
    for s in srcs[1:]:
        seg = s.split("/")
        i = 0
        while i < len(parts) and i < len(seg) and parts[i] == seg[i]:
            i += 1
        parts = parts[:i]
    if not parts:
        return ""
    if parts[-1] in {"src", "lib", "source"}:
        # domains are sibling packages directly under a generic root -> package = next seg
        own_parts = own.split("/") if own else []
        if len(own_parts) > len(parts):
            return own_parts[len(parts)]
    return parts[-1]


def _pkg_chain(workspace_root: Path, py: Path, pkg: str) -> List[str]:
    """Directories between the shared package root and this file's own directory.

    `src/k3dge/engine/sub/x.py` with pkg `k3dge` -> `["engine", "sub"]`; the first entry is
    the domain, and the length tells a relative import how many levels stay inside a domain.
    """
    try:
        parts = list(py.relative_to(workspace_root).parts[:-1])
    except ValueError:
        return []
    if pkg in parts:
        return parts[parts.index(pkg) + 1:]
    return parts


def _imported_domains(tree: "ast.AST", chain: List[str], pkg: str) -> List[str]:
    """First module segment after `pkg` for every import in the tree (absolute + relative).

    Replaces the line regex (code-3), which only saw `pkg.<name>` with `[a-z_]+` and so missed
    `from pkg import <domain>`, multi-name imports and `from ..engine import x`.
    """
    targets: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                seg = alias.name.split(".")
                if seg[0] == pkg and len(seg) > 1:
                    targets.append(seg[1])
        elif isinstance(node, ast.ImportFrom):
            names = [a.name.split(".")[0] for a in node.names]
            if node.level:
                keep = len(chain) - (node.level - 1)
                if keep < 0:
                    continue  # escapes the package — no domain attributable
                resolved = chain[:keep] + (node.module.split(".") if node.module else [])
                targets.extend(resolved[:1] if resolved else names)
            elif node.module:
                seg = node.module.split(".")
                if seg[0] == pkg:
                    targets.extend(seg[1:2] if len(seg) > 1 else names)
    return targets


def _shape_change_documented(workspace: Path, domain: str, spec_content: str, sym_diff: dict) -> bool:
    """C gate (WARN only): a shape change (added/removed/changed symbols) must leave a human trace.

    Either a CHANGELOG `## [Unreleased]` line, or a spec §1 boundary sentence, mentioning the
    domain or any changed symbol. Structural check only — never NLP over the prose (ADR-0001 decision 6).
    """
    names = set(
        sym_diff.get("added", []) + sym_diff.get("removed", []) + sym_diff.get("changed", [])
    )
    if not names:
        return True
    needles = {domain, *names}
    cl = workspace / "CHANGELOG.md"
    if cl.is_file():
        try:
            text = cl.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        i = text.find("## [Unreleased]")
        if i != -1:
            j = text.find("## [", i + 1)
            block = text[i:j] if j != -1 else text[i:]
            if any(n in block for n in needles):
                return True
    m = re.search(r"^#{2,3}\s+.*(?:Domain Boundary|边界)", spec_content, re.MULTILINE)
    if m:
        nxt = re.search(r"\n#{2,3}\s+", spec_content[m.start() + 1 :])
        sec = spec_content[m.start() : nxt.start() if nxt else len(spec_content)]
        if any(n in sec for n in needles):
            return True
    return False


def _run_batch_tests(
    workspace: Path,
    manifest: Manifest,
    batch_refs: dict[str, set[str]],
) -> List[Violation]:
    """Run pytest (or test_command_template) for collected refs; never Path/None."""
    import shlex
    import subprocess
    import sys

    violations: List[Violation] = []
    if not batch_refs:
        return violations
    refs = sorted(batch_refs)
    template = manifest.data.get("test_command_template")
    cmd: Optional[list[str]] = None
    if template:
        try:
            cmd = shlex.split(template.format(refs=" ".join(refs)))
        except (KeyError, ValueError, TypeError) as exc:
            return [
                Violation("MANIFEST_INVALID", f"test_command_template invalid: {exc}",
                          detail={"path": ".agent/manifest.json",
                                  "reason": f"test_command_template 不是合法模板：{exc}"})
            ]
    else:
        cmd = [sys.executable, "-m", "pytest", *refs, "-q"]
    try:
        result = subprocess.run(
            cmd, cwd=workspace, capture_output=True, text=True, timeout=300
        )
    except subprocess.TimeoutExpired:
        for _ref, domains in batch_refs.items():
            for d in domains:
                violations.append(
                    Violation(
                        "TEST_FAILURE",
                        f"tests timed out after 300s (batch {refs})",
                        domain=d,
                        file_path=_spec_violation_path(workspace, manifest, d),
                        detail={"domain": d, "target": refs, "reason": "300s 超时"},
                    )
                )
        return violations
    except FileNotFoundError:
        for _ref, domains in batch_refs.items():
            for d in domains:
                violations.append(
                    Violation(
                        "TEST_ENV_MISSING",
                        "pytest not available",
                        domain=d,
                        file_path=_spec_violation_path(workspace, manifest, d),
                        detail={"domain": d},
                    )
                )
        return violations
    if result.returncode == 0:
        return violations
    if result.stderr and "No module named" in result.stderr and "pytest" in result.stderr:
        for _ref, domains in batch_refs.items():
            for d in domains:
                violations.append(
                    Violation(
                        "TEST_ENV_MISSING",
                        "pytest not available",
                        domain=d,
                        file_path=_spec_violation_path(workspace, manifest, d),
                        detail={"domain": d},
                    )
                )
        return violations
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    # CI / 终端必须看见 pytest 正文：闸码 alone 不够修。打印不是豁免，是让 TEST_FAILURE 可观测。
    print("=" * 60, flush=True)
    print("pytest output (TEST_FAILURE)", flush=True)
    print("=" * 60, flush=True)
    print(output, flush=True)
    tail = "\n".join(output.splitlines()[-40:])
    failed = {ref for ref in refs if ref in output and "failed" in output.lower()}
    if not failed:
        failed = set(refs)
    for ref in sorted(failed):
        for d in sorted(batch_refs[ref]):
            violations.append(
                Violation(
                    "TEST_FAILURE",
                    f"test '{ref}' failed",
                    domain=d,
                    file_path=_spec_violation_path(workspace, manifest, d),
                    detail={
                        "domain": d, "target": ref,
                        "reason": "退出码非 0（--with-tests）",
                        "pytest_tail": tail,
                    },
                )
            )
    return violations


class ConsistencyEngine:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    def _staged_files(self) -> List[str]:
        import subprocess

        try:
            out = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []
        if out.returncode != 0:
            return []
        return [p.strip() for p in out.stdout.splitlines() if p.strip()]

# k3dit:leftover value-1 283行/9门控重构无窗内测试保行为；M7-Q3同域已接受技术债，交独立refactor task
    def evaluate(self, run_tests: bool = False, force_full: bool = False, staged: bool = False) -> GateReport:
        from k3dge.engine import events
        try:
            manifest = Manifest.load(self.workspace_root)
        except ManifestError as exc:
            report = GateReport(
                passed=False,
                changed_files=(),
                modified_domains=(),
                violations=(Violation("MANIFEST_INVALID", str(exc),
                                      file_path=".agent/manifest.json",
                                      detail={"path": ".agent/manifest.json",
                                              "reason": str(exc)}),),
            )
            events.emit(self.workspace_root, "gate_fail", violations=len(report.violations))
            return report
        if staged:
            files = self._staged_files()
        else:
            try:
                files = diff.get_changed_files(self.workspace_root)
            except GitError as exc:
                if not force_full:
                    git_vs: List[Violation] = [
                        Violation(
                            "GIT_UNAVAILABLE",
                            f"git unavailable: {exc}",
                            detail={"reason": str(exc)},
                        )
                    ]
                    if not manifest.domains:
                        git_vs.insert(
                            0,
                            Violation(
                                "NO_DOMAINS",
                                "manifest.domains is empty",
                                file_path=".agent/manifest.json",
                            ),
                        )
                    report = GateReport(
                        passed=False,
                        changed_files=(),
                        modified_domains=(),
                        violations=tuple(git_vs),
                    )
                    events.emit(self.workspace_root, "gate_fail", violations=len(report.violations))
                    return report
                files = ()

        violations: List[Violation] = []
        if not manifest.domains:
            violations.append(
                Violation(
                    "NO_DOMAINS",
                    "manifest.domains is empty",
                    file_path=".agent/manifest.json",
                )
            )
        modified_domains, specs_touched, dom_vs = self._collect_modified_domains(files, manifest)
        violations.extend(dom_vs)

        touched = modified_domains | specs_touched
        if force_full:
            touched = set(manifest.domains)
            modified_domains = set(manifest.domains)

        if run_tests:
            violations.extend(self._run_affected_tests(modified_domains, manifest))

        for domain in sorted(touched):
            violations.extend(self._check_domain(domain, manifest))

        violations.extend(self._check_version_consistency())


        violations.extend(self._check_template_drift(manifest))

        violations.extend(self._check_pipeline())

        violations.extend(self._check_audit_trail())

        violations.extend(self._check_docs(files, force_full))

        violations.extend(self._check_generated_projections(manifest))

        violations.extend(self._check_extractor_plugins())

        violations.extend(self._check_docs_toml())

        violations.extend(self._check_architecture_tables(manifest))

        violations.extend(self._check_state_doc_coverage())

        report = GateReport(
            passed=not violations,
            changed_files=tuple(files),
            modified_domains=tuple(sorted(modified_domains)),
            violations=tuple(violations),
        )
        events.emit(
            self.workspace_root,
            "gate_pass" if report.passed else "gate_fail",
            violations=len(report.violations),
            domains=list(report.modified_domains),
        )
        return report

    def _collect_modified_domains(self, files, manifest: Manifest):
        """按改动文件归域：返回 (modified_domains, specs_touched, violations)。

        docs 根直放 / 未注册域（package_root 下无域映射）在此报。
        """
        modified_domains: Set[str] = set()
        specs_touched: Set[str] = set()
        out: List[Violation] = []
        for path in files:
            if manifest.is_ignored(path):
                continue
            if path.endswith("__init__.py"):
                continue
            # docs/ 根下不直放文档；唯一例外 docs/README.md（根索引/治理总纲）
            if path.startswith("docs/") and "/" not in path[5:] and not path.endswith("/"):
                name = path[5:]
                if name and not name.startswith(".") and name not in (".DS_Store", "README.md"):
                    out.append(
                        Violation(
                            "DOCS_ROOT_DISALLOWED",
                            f"docs root file '{path}' must live in a docs/<type>/ subdirectory",
                            file_path=path,
                            detail={"path": path},
                        )
                    )
                    continue
            spec_domain = manifest.domain_for_spec(path)
            if spec_domain is not None:
                specs_touched.add(spec_domain)
                continue
            if not manifest.under_package_root(path):
                continue
            domain = manifest.domain_for_src(path)
            if domain is None:
                out.append(
                    Violation(
                        "UNREGISTERED_DOMAIN",
                        f"'{path}' lives under package_root but no domain maps it",
                        file_path=path,
                        detail={"path": path},
                    )
                )
                continue
            modified_domains.add(domain)
        return modified_domains, specs_touched, out

    def _run_affected_tests(self, modified_domains: Set[str], manifest: Manifest) -> List[Violation]:
        """批量跑 touched 域测试；跨域：公开哈希变化时带 depends_on 该域的消费方（ADR-0001 决策点 6）。"""
        affected = set(modified_domains)
        for d in sorted(manifest.domains):
            if set(manifest.depends_on(d)) & affected:
                affected.add(d)
        batch_refs: dict[str, set[str]] = {}
        for domain in sorted(affected):
            ref = manifest.domains.get(domain, {}).get("tests", "")
            if ref and (self.workspace_root / ref).exists():
                batch_refs.setdefault(ref, set()).add(domain)
        return _run_batch_tests(self.workspace_root, manifest, batch_refs)

    def _check_version_consistency(self) -> List[Violation]:
        """pyproject ↔ manifest ↔ __init__ 版本同值；异常即 VERSION_MISMATCH。"""
        try:
            from k3dge.engine.version import validate_versions

            return list(validate_versions(self.workspace_root))
        except Exception as exc:
            return [
                Violation(
                    "VERSION_MISMATCH",
                    f"validation failed: {exc}",
                    file_path=str(self.workspace_root / "pyproject.toml"),
                    detail={"drift": f"版本校验未能完成：{exc}"},
                )
            ]

    def _check_template_drift(self, manifest: Manifest) -> List[Violation]:
        """脚手架镜像漂移：assets ↔ 本仓文件一致（仅 self_hosting=true，ADR-0001）。"""
        out: List[Violation] = []
        try:
            is_self_host = bool(getattr(manifest, "self_hosting", False))
            if is_self_host:
                # Prefer installed package assets, fallback to workspace assets for editable install
                try:
                    assets_root = Path(__file__).resolve().parents[1] / "templates" / "assets"
                    if not assets_root.is_dir():
                        assets_root = self.workspace_root / "src/k3dge/templates/assets"
                except Exception:
                    assets_root = self.workspace_root / "src/k3dge/templates/assets"
                for asset, rel in PAIRS:
                    try:
                        asset_path = assets_root / asset
                        if not asset_path.is_file():
                            continue
                        asset_text = _without_pins(asset_path.read_text(encoding="utf-8")).rstrip("\n")
                        repo_path = self.workspace_root / rel
                        if not repo_path.is_file():
                            continue
                        repo_text = _without_pins(repo_path.read_text(encoding="utf-8")).rstrip("\n")
                        if asset_text != repo_text:
                            out.append(
                                Violation(
                                    "TEMPLATE_DRIFT",
                                    f"assets/{asset} != {rel}",
                                    file_path=rel,
                                    detail={"asset": f"src/k3dge/templates/assets/{asset}", "repo": rel},
                                )
                            )
                    except (OSError, UnicodeDecodeError):
                        continue
                # Budget warning: AGENTS.md microkernel should stay <80 lines (self-host only, not a gate)
                try:
                    agent_tpl = assets_root / "agents.md"
                    if agent_tpl.is_file():
                        n_lines = len(agent_tpl.read_text(encoding="utf-8").splitlines())
                        if n_lines > 80:
                            import sys

                            print(
                                f"[WARN] AGENTS.md template exceeds micro-kernel budget: {n_lines} > 80 lines",
                                file=sys.stderr,
                            )
                except Exception:
                    pass
        except Exception as exc:
            out.append(
                Violation(
                    "TEMPLATE_DRIFT",
                    f"check failed: {exc}",
                    file_path="src/k3dge/engine/pairs.py",
                    detail={"asset": "src/k3dge/templates/assets/", "repo": f"比对未完成：{exc}"},
                )
            )
        return out

    def _check_pipeline(self) -> List[Violation]:
        """pipeline.toml 语义硬门控（纯静态；文件不存在则优雅跳过）。"""
        out: List[Violation] = []
        try:
            from k3dge.engine.pipeline_schema import validate_pipeline_config

            for code, msg in validate_pipeline_config(self.workspace_root):
                out.append(
                    Violation(code, msg, domain="pipelines", file_path=".agent/pipeline.toml")
                )
        except Exception as exc:
            out.append(
                Violation(
                    "PIPELINE_SCHEMA_INVALID",
                    f"pipeline validation crashed: {exc}",
                    domain="pipelines",
                    file_path=".agent/pipeline.toml",
                    detail={"path": ".agent/pipeline.toml", "reason": str(exc)},
                )
            )
        return out

    def _check_audit_trail(self) -> List[Violation]:
        """`ADR-0008`：审计痕迹只可追加。静态扫 `src/**` 里对 `logs/` 的**覆写式**写入（write_text / open 'w'）。

        只判盘上事实（AST 字符串常量 + 写模式），不跑进程。追加式（`open(...,'a')` / 无 `write_text`）不报。
        """
        import ast

        src = self.workspace_root / "src"
        out: List[Violation] = []
        if not src.is_dir():
            return out
        for path in src.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, ValueError):
                continue
            rel = path.relative_to(self.workspace_root).as_posix()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                msg = self._logs_overwrite(node)
                if msg:
                    out.append(Violation("AUDIT_TRAIL_APPEND_ONLY", msg, file_path=rel,
                                         detail={"path": rel, "reason": msg}))
        return out

    @staticmethod
    def _logs_literal(node) -> bool:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                if "logs" in sub.value.replace("\\", "/").split("/") or "logs/" in sub.value.replace("\\", "/"):
                    return True
        return False

    @classmethod
    def _logs_overwrite(cls, node) -> str:
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else "")
        if name == "write_text" and cls._logs_literal(node):
            return "对 logs/ 的 write_text 覆写：审计痕迹只可追加（ADR-0008），改用追加写入。"
        if name == "open" and node.args:
            target = node.args[0]
            mode = node.args[1] if len(node.args) > 1 else None
            if mode is None:
                mode = next((kw.value for kw in node.keywords if kw.arg == "mode"), None)
            wr = isinstance(mode, ast.Constant) and isinstance(mode.value, str) and any(c in mode.value for c in "wx")
            if cls._logs_literal(target) and wr:
                return "对 logs/ 的 open(...,'w') 覆写：审计痕迹只可追加（ADR-0008），改用 'a'。"
        return ""

    def _check_docs(self, files, force_full: bool) -> List[Violation]:
        """docs 目录结构/索引校验（force_full 或本批触 docs 时）。"""
        docs_touched = any(str(p).replace("\\", "/").startswith("docs/") for p in files)
        if not (force_full or docs_touched):
            return []
        try:
            from k3dge.engine.doc_catalog import validate_docs, validate_docs_index

            types = None
            if not force_full:
                types = sorted(
                    {
                        Path(p).parts[1]
                        for p in files
                        if str(p).replace("\\", "/").startswith("docs/")
                        and len(Path(p).parts) > 1
                    }
                )
            return list(validate_docs(self.workspace_root, types=types)) + list(
                validate_docs_index(self.workspace_root)
            )
        except Exception as extra:
            return [
                Violation(
                    "DOC_SCHEMA_INVALID",
                    f"docs catalog check crashed: {extra}",
                    file_path="docs",
                    detail={"path": "docs"},
                )
            ]

    def _check_domain(self, domain: str, manifest: Manifest) -> List[Violation]:
        out, spec_path, content = self._load_domain_spec(domain, manifest)
        if content is None:
            return out
        out.extend(self._check_verification_matrix(domain, manifest, spec_path, content))
        contract_out, fatal = self._check_domain_contract(domain, manifest, spec_path, content)
        out.extend(contract_out)
        if fatal:
            return out
        out.extend(self._check_domain_imports(domain, manifest))
        return out

    def _load_domain_spec(self, domain: str, manifest: Manifest):
        """Spec content, or the NOT_FOUND/DECODE violations that block it (content=None)."""
        spec_rel = manifest.spec_path(domain)
        if not spec_rel:
            return [
                Violation(
                    "SPEC_NOT_FOUND",
                    f"domain '{domain}' has no spec path in manifest",
                    domain=domain,
                    detail={"domain": domain, "spec": "(manifest 未声明 spec 路径)"},
                )
            ], None, None

        spec_path = self.workspace_root / spec_rel
        if not spec_path.exists():
            return [
                Violation(
                    "SPEC_NOT_FOUND",
                    f"spec missing for domain '{domain}': {spec_rel}",
                    domain=domain,
                    file_path=str(spec_path),
                    detail={"domain": domain, "spec": spec_rel},
                )
            ], None, None

        try:
            content = spec_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            return [
                Violation(
                    "SPEC_DECODE_FAILED",
                    f"spec is not UTF-8 for domain '{domain}': {exc}",
                    domain=domain,
                    file_path=str(spec_path),
                    detail={"domain": domain, "spec": str(spec_path), "reason": str(exc)},
                )
            ], None, None
        return [], spec_path, content

    def _check_verification_matrix(
        self, domain: str, manifest: Manifest, spec_path: Path, content: str
    ) -> List[Violation]:
        out: List[Violation] = []
        for err in spec_schema.validate_structure(content):
            out.append(
                Violation("SPEC_MISSING_SECTION", err, domain=domain, file_path=str(spec_path),
                          detail={"domain": domain, "spec": str(spec_path), "reason": err})
            )
        for m in _TEST_REF_RE.finditer(_verification_matrix_section(content)):
            ref = m.group(1).strip().rstrip(".,)")
            # 跨域引用标注：tests/unit/<other>/ 不属于本域矩阵，仅提示不计入 selective L2 执行
            tests_root = manifest.domains.get(domain, {}).get("tests", "")
            foreign = bool(tests_root) and not (
                ref == tests_root or ref.startswith(tests_root.rstrip("/") + "/")
            )
            if "::" in ref:
                fpath, _, tname = ref.partition("::")
            else:
                fpath, tname = ref, ""
            target = self.workspace_root / fpath
            if not target.exists():
                out.append(
                    Violation(
                        "MISSING_TEST_FILE",
                        f"Verification Matrix references missing test '{ref}'"
                        + (" (cross-domain reference)" if foreign else ""),
                        domain=domain,
                        file_path=str(spec_path),
                        detail={"domain": domain, "ref": ref},
                    )
                )
                continue
            # 行级绑定：矩阵行须可解析到具体测试（文件在、场景不在 = 红，ADR-0001 决策点 6）
            try:
                _t_src = target.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                _t_src = ""
            if tname:
                if not re.search(rf"(?:async\s+def|def)\s+{re.escape(tname)}\b", _t_src):
                    out.append(
                        Violation(
                            "MATRIX_TEST_UNRESOLVED",
                            f"Verification Matrix row binds '{ref}' but no test '{tname}' in {fpath}"
                            + (" (cross-domain reference)" if foreign else ""),
                            domain=domain,
                            file_path=str(spec_path),
                            detail={"domain": domain, "ref": ref,
                                    "reason": f"{fpath} 里没有名为 {tname} 的测试"},
                        )
                    )
            elif not re.search(r"\bdef\s+test_", _t_src):
                out.append(
                    Violation(
                        "MATRIX_TEST_UNRESOLVED",
                        f"Verification Matrix row references '{fpath}' which contains no test functions",
                        domain=domain,
                        file_path=str(spec_path),
                        detail={"domain": domain, "ref": fpath,
                                "reason": "该文件里没有任何测试函数"},
                    )
                )
        return out

    def _check_domain_contract(
        self, domain: str, manifest: Manifest, spec_path: Path, content: str
    ):
        """Contract check. Returns (violations, fatal); fatal=True stops further checks."""
        out: List[Violation] = []
        src_rel = manifest.src_path(domain)
        if not src_rel:
            return out, False
        src_dir = self.workspace_root / src_rel
        try:
            ok, expected, actual = contract.verify_contract(
                src_dir, content, manifest, self.workspace_root
            )
        except _ExtractError as exc:
            out.append(
                Violation(
                    "CONTRACT_EXTRACT_FAILED",
                    str(exc),
                    domain=domain,
                    file_path=str(spec_path),
                    detail={"domain": domain, "spec": str(spec_path), "reason": str(exc)},
                )
            )
            return out, True
        if expected is None:
            out.append(
                Violation(
                    "CONTRACT_HASH_MISSING",
                    "no contract hash in spec",
                    domain=domain,
                    file_path=str(spec_path),
                    detail={"domain": domain, "spec": str(spec_path)},
                )
            )
        elif not ok:
            detail = None
            try:
                detail = contract.symbol_diff(content, src_dir, manifest, self.workspace_root)
            except Exception:
                detail = None
            if detail and any(detail.get(k) for k in ("added", "removed", "changed")):
                if not _shape_change_documented(self.workspace_root, domain, content, detail):
                    import sys

                    print(
                        f"[WARN][CONTRACT_SHAPE_NO_TRACE] domain '{domain}' changed contract symbols "
                        f"{detail} but no CHANGELOG '## [Unreleased]' line or spec §1 boundary mentions it; "
                        f"sync still required and a human trace is expected (ADR-0001 decision 6)",
                        file=sys.stderr,
                    )
            out.append(
                Violation(
                    "CONTRACT_DRIFT",
                    # 事实摘要（非文案）：措辞/选项/指针归 gate_facts 声明面
                    f"spec={expected[:12]} code={actual[:12]}",
                    domain=domain,
                    file_path=str(spec_path),
                    detail={
                        "symbol_diff": detail,
                        "expected_hash": expected,
                        "actual_hash": actual,
                    },
                )
            )
        return out, False

    def _check_generated_projections(self, manifest: Manifest) -> List[Violation]:
        """生成物的新鲜度闸：符号索引 / `docs/generated/{api,domains}.md` / `.mcp.json`。

        这三件（加上已被 `DOC_INDEX_STALE` 罩住的 `docs-index.json`）都是**可重算的投影**，
        但此前只有 docs-index 有闸 ⇒ 其余三件“写了就没人管旧”（本仓 2026-09-21 盘点：悬空）。
        与 `DOC_INDEX_STALE` 同形：重建与盘上比，不等即红，修法＝重生它的那条命令。
        纯静态、不写盘、不联网。
        """
        out: List[Violation] = []

        # ① 符号索引（`k3dge where` 的判据面：旧索引会静默返回错位置）
        try:
            from k3dge.engine import search

            idx_path = search.index_path(self.workspace_root)
            if idx_path.is_file():
                try:
                    actual = json.loads(idx_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    actual = None
                if actual != search.build_symbol_index(self.workspace_root):
                    rel = str(idx_path.relative_to(self.workspace_root)).replace("\\", "/")
                    out.append(
                        Violation(
                            "SYMBOL_INDEX_STALE",
                            "symbol index is stale (rebuild differs)",
                            file_path=rel,
                            detail={"path": rel, "reason": "盘上内容与重建结果不同"},
                        )
                    )
        except Exception as exc:  # 工具坏不得静默：报一次而非吞掉
            out.append(
                Violation(
                    "SYMBOL_INDEX_STALE",
                    f"symbol index check crashed: {exc}",
                    file_path="docs/generated/symbol-index.json",
                    detail={"path": "docs/generated/symbol-index.json", "reason": str(exc)},
                )
            )

        # ② docs/generated/{api,domains}.md（`k3dge sync` 的产物）
        try:
            from k3dge.engine.generated_docs import render_manual_docs_content

            for path, expected in render_manual_docs_content(self.workspace_root, manifest).items():
                if not path.is_file():
                    continue  # 缺文件不是“陈旧”（与 `validate_docs_index` 同口径：缺 ⇒ 不报）
                rel = str(path.relative_to(self.workspace_root)).replace("\\", "/")
                if path.read_text(encoding="utf-8") != expected:
                    out.append(
                        Violation(
                            "DOCS_GENERATED_STALE",
                            "generated doc is stale (re-render differs)",
                            file_path=rel,
                            detail={"path": rel, "reason": "与 `k3dge sync` 的重建结果不同"},
                        )
                    )
        except Exception as exc:
            out.append(
                Violation(
                    "DOCS_GENERATED_STALE",
                    f"generated docs check crashed: {exc}",
                    file_path="docs/generated",
                    detail={"path": "docs/generated", "reason": str(exc)},
                )
            )

        # ③ .mcp.json：声明 enabled 的 peer（能探到 sibling MCP 模块的）必须在 mcpServers 里
        try:
            out.extend(self._check_mcp_json())
        except Exception as exc:
            out.append(
                Violation(
                    "MCP_JSON_PEER_MISSING",
                    f".mcp.json check crashed: {exc}",
                    file_path=".mcp.json",
                    detail={"path": ".mcp.json", "reason": str(exc)},
                )
            )
        return out

    def _check_mcp_json(self) -> List[Violation]:
        """`.mcp.json` 的 peer 面 vs `.agent/pipeline.toml` 声明（同一探测函数，不开第二判据）。"""
        from k3dge.engine import mcp_json as mj

        cfg_path = self.workspace_root / ".agent" / "pipeline.toml"
        doc = mj.load_mcp_document(self.workspace_root)
        if not cfg_path.is_file() or doc is None:
            return []  # 无声明/无文件 ⇒ 不造违例（缺文件归 PIPELINE_* 与 init 面）
        try:
            import tomllib as _toml
        except ModuleNotFoundError:  # py3.10
            try:
                import tomli as _toml  # type: ignore
            except ModuleNotFoundError:
                return []
        try:
            cfg = _toml.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            return []  # 语法错由 PIPELINE_SCHEMA_INVALID 报，不在这里凑第二份
        servers = doc.get("mcpServers")
        if not isinstance(servers, dict):
            return [
                Violation(
                    "MCP_JSON_PEER_MISSING",
                    "`.mcp.json` has no mcpServers map",
                    file_path=".mcp.json",
                    detail={"path": ".mcp.json", "reason": "缺 mcpServers"},
                )
            ]
        out: List[Violation] = []
        if "k3dge" not in servers:
            out.append(
                Violation(
                    "MCP_JSON_PEER_MISSING",
                    "`.mcp.json` does not declare the k3dge server itself",
                    file_path=".mcp.json",
                    detail={"path": ".mcp.json", "peer": "k3dge"},
                )
            )
        for pid, pcfg in (cfg.get("peers") or {}).items():
            if not isinstance(pcfg, dict) or not pcfg.get("enabled", True) or pid == "k3dge":
                continue
            probe, mod, _pp = mj.probe_peer_mcp(self.workspace_root, pid)
            if pid in servers or probe is None or mod is None:
                continue  # 已声明 / sibling 不在（写侧本就会跳过，见 cli.mcp_peers 的回退告警）
            out.append(
                Violation(
                    "MCP_JSON_PEER_MISSING",
                    f"peer '{pid}' is declared enabled and resolvable but missing from `.mcp.json`",
                    file_path=".mcp.json",
                    detail={"path": ".mcp.json", "peer": pid},
                )
            )
        return out

    def _check_state_doc_coverage(self) -> List[Violation]:
        """`docs/architecture/overview.md` 必须列全两个**闭集**：`[NEXT]` 态与 task 态。

        2026-09-21 盘点：这两个闭集是代码里的唯一源，文档里此前只零星出现几个名字 ⇒ 新增/改名
        状态时文档静默过时。只做**标识符级出现性**检查（要求反引号形式，避免撞普通英文词），
        不解析表格格式。
        """
        rel = "docs/architecture/overview.md"
        path = self.workspace_root / rel
        if not path.is_file():
            return []
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        from k3dge.engine import nextstep, state_machine

        states = sorted(nextstep.STATE_OPTIONS) + [s.value for s in state_machine.TaskState]
        # 「要么不写、要么写全」：一个状态名都没列 ⇒ 本文件没打算做状态总览（下游骨架即如此），
        # 不报；列了一部分 ⇒ 那才是会误导人的半张表（漏项＝新状态在总览里不存在）。
        if not any(f"`{s}`" in text for s in states):
            return []
        missing = [s for s in states if f"`{s}`" not in text]
        out: List[Violation] = []
        if missing:
            out.append(
                Violation(
                    "ARCH_STATE_DOC_DRIFT",
                    f"{rel} 未列全状态闭集（缺 {missing}）——状态源在 `engine/nextstep.STATE_OPTIONS` / "
                    f"`engine/state_machine.TaskState`，文档缺项等于静默过时",
                    file_path=rel,
                    detail={"path": rel, "missing": missing},
                )
            )
        # 表里写了 priority 就要与代码一致（**数字**也漂移过：2026-09-21 发现旧文写反了 ratchet_open）
        for prio, state in re.findall(r"^\|\s*(\d+)\s*\|\s*`([a-z_]+)`\s*\|", text, re.MULTILINE):
            want = nextstep.STATE_OPTIONS.get(state, {}).get("priority")
            if want is not None and int(prio) != int(want):
                out.append(
                    Violation(
                        "ARCH_STATE_DOC_DRIFT",
                        f"{rel} 的 `{state}` priority 写成 {prio}，代码是 {want}",
                        file_path=rel,
                        detail={"path": rel, "state": state, "got": int(prio), "want": int(want)},
                    )
                )
        return out

    def _check_architecture_tables(self, manifest: Manifest) -> List[Violation]:
        """设计文档里的**域表**必须与 manifest 对齐（表行是事实，不是散文）。

        `docs/architecture/overview.md` 头部自称“人写常驻 + `k3dge sync` 聚合校验”——
        但那道“聚合校验”此前**不存在**（2026-09-21 盘点：`grep architecture evaluator|pure_refs` 零命中）：
        改 manifest 的域/源码/spec/tests/depends_on 时，两张表可以静静地说着旧话。
        实质：Diátaxis 里 architecture＝解释（人写），**故意不把它变成生成物**；
        可机检的只是表里那几列事实 ⇒ 只比事实列，不比 description（散文）。
        """
        out: List[Violation] = []
        for rel, cols in (
            ("docs/architecture/overview.md", ("src", "spec")),
            ("docs/architecture/encyclopedia.md", ("src", "spec", "tests", "depends_on")),
        ):
            path = self.workspace_root / rel
            if not path.is_file():
                continue
            try:
                rows = _domain_table_rows(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
            if rows is None:
                continue  # 没找到域表（格式变了也不在这里报，归文档评审）
            missing = sorted(set(manifest.domains) - set(rows))
            extra = sorted(set(rows) - set(manifest.domains))
            detail: dict = {"path": rel}
            if missing or extra:
                out.append(
                    Violation(
                        "ARCH_TABLE_DRIFT",
                        f"{rel} 域表与 manifest 的域集不一致“missing={missing} extra={extra}” ",
                        file_path=rel,
                        detail={**detail, "missing": missing, "extra": extra},
                    )
                )
            for domain in sorted(set(rows) & set(manifest.domains)):
                cfg = manifest.domains[domain]
                for col in cols:
                    want = _norm_cell(cfg.get(col))
                    got = _norm_cell(rows[domain].get(col))
                    if want != got:
                        out.append(
                            Violation(
                                "ARCH_TABLE_DRIFT",
                                f"{rel} 域表 {domain} 的 {col} 与 manifest 不一致“{got} ≠ {want}” ",
                                domain=domain,
                                file_path=rel,
                                detail={**detail, "domain": domain, "col": col,
                                        "got": got, "want": want},
                            )
                        )
        return out

    def _check_extractor_plugins(self) -> List[Violation]:
        """`.agent/extractors/<lang>.py` 必须是 `.agent/extractors.toml` 的**当前渲染**（改了配置没 sync ⇒ 静默用过时插件）。"""
        try:
            from k3dge.engine import extractor_gen

            ws = self.workspace_root
            if not ((ws / ".agent" / "extractors.toml").is_file() or (ws / ".agent" / "extractors").is_dir()):
                return []
            missing = []
            for name, row in extractor_gen.resolve_languages(ws).items():
                dest = ws / extractor_gen.PLUGDIR_REL / f"{name}.py"
                want = extractor_gen.render_plugin(name, row)
                got = dest.read_text(encoding="utf-8") if dest.is_file() else None
                if got != want:
                    missing.append(name)
            if not missing:
                return []
            return [
                Violation(
                    "EXTRACTOR_PLUGIN_STALE",
                    f"抽取器插件与配置不一致（{missing}）——由 `k3dge extractor sync` 重生",
                    file_path=extractor_gen.PLUGDIR_REL,
                    detail={"path": extractor_gen.PLUGDIR_REL, "languages": missing},
                )
            ]
        except Exception as exc:
            return [
                Violation(
                    "EXTRACTOR_PLUGIN_STALE",
                    f"extractor plugin check crashed: {exc}",
                    file_path=".agent/extractors",
                    detail={"path": ".agent/extractors", "reason": str(exc)},
                )
            ]

    def _check_docs_toml(self) -> List[Violation]:
        """`.agent/docs.toml` 的 `= true` 键必须真的会被 `scripts/generate-docs.sh` 处理，且目标文件在。

        键表**不在这里另造一份**：直接从写脚本自己的 `gen "<key>" "<file>" "<title>"` 行读
        （写侧是唯一声明处）；读不到任何 `gen` 行 ⇒ 跳过（脚本形态变了不误报）。
        """
        cfg = self.workspace_root / ".agent" / "docs.toml"
        script = self.workspace_root / "scripts" / "generate-docs.sh"
        if not cfg.is_file() or not script.is_file():
            return []
        try:
            table = dict(
                (k, f) for k, f, _t in re.findall(r'gen\s+"([a-z_]+)"\s+"([^"]+)"\s+"([^"]*)"', script.read_text(encoding="utf-8"))
            )
            enabled = re.findall(r"^\s*([a-z_]+)\s*=\s*true\b", cfg.read_text(encoding="utf-8"), re.MULTILINE)
        except (OSError, UnicodeDecodeError):
            return []
        if not table:
            return []
        out: List[Violation] = []
        for key in enabled:
            target = table.get(key)
            if key == "readme":
                target = "README.md"   # readme 走专门分支（刷新布局/基础版），不在 gen 表里
            if target is None:
                out.append(
                    Violation(
                        "DOCS_TOML_KEY_UNKNOWN",
                        f"`.agent/docs.toml` 的 `{key} = true` 不会被 `scripts/generate-docs.sh` 处理（键表见该脚本的 gen 行）",
                        file_path=".agent/docs.toml",
                        detail={"path": ".agent/docs.toml", "key": key},
                    )
                )
                continue
            # 只查"键脚本认不认识"：`= true` 而文件尚未生成是**收尾流程的常态**（`generate-docs.sh` 在
            # 工程收尾时才落桩），报它会把每个刚 init 的仓都打红。
        return out

    def _check_domain_imports(self, domain: str, manifest: Manifest) -> List[Violation]:
        """Reverse-import ban: a domain may import another domain only if declared in depends_on (ADR-0001 decision 6)."""
        out: List[Violation] = []
        src_rel = manifest.src_path(domain)
        if not src_rel:
            return out
        src_dir = self.workspace_root / src_rel
        if not src_dir.exists():
            return out
        pkg = _package_prefix(manifest, domain)
        if not pkg:
            return out
        allowed = set(manifest.depends_on(domain))
        for py in sorted(src_dir.rglob("*.py")):
            if py.name == "__init__.py":
                continue
            try:
                text = py.read_text(encoding="utf-8")
                tree = ast.parse(text)
            except (OSError, SyntaxError, ValueError):
                continue
            chain = _pkg_chain(self.workspace_root, py, pkg)
            reported: Set[str] = set()
            for target in _imported_domains(tree, chain, pkg):
                if target == domain or target not in manifest.domains:
                    continue
                if target not in allowed and target not in reported:
                    reported.add(target)
                    out.append(
                        Violation(
                            "DOMAIN_IMPORT_VIOLATION",
                            f"domain '{domain}' imports '{target}' but does not declare depends_on",
                            domain=domain,
                            file_path=str(py),
                            detail={"domain": domain, "target": target, "path": str(py)},
                        )
                    )
        return out


#: 域表列名（两种写法）→ 归一列键。**只认事实列**；description/一句话 是散文，不比对。
_TABLE_COL_KEYS = {
    "domain": "domain",
    "source": "src", "源码": "src",
    "spec": "spec", "契约 spec": "spec",
    "tests": "tests", "测试": "tests",
    "depends_on": "depends_on",
}


def _norm_cell(value: object) -> str:
    """表格单元归一：去反引号/空白、空占位（—/-）归空、逗号列表排序（顺序不敏感）。"""
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        value = ", ".join(str(x) for x in value)
    s = str(value).strip().strip("`").strip()
    if s in {"—", "–", "-", "/", ""}:
        return ""
    if "," in s:
        s = ", ".join(sorted(p.strip() for p in s.split(",") if p.strip()))
    return re.sub(r"\s+", " ", s)


def _domain_table_rows(text: str) -> Optional[dict]:
    """抽出文档里的**域表**（表头含 Domain 且至少含一个事实列）→ {domain: {col: cell}}。

    找不到 ⇒ None（格式变了不当违例报：那是文档评审的事，不是这个闸的判据）。
    """
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            current.append(line.strip())
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)

    for block in blocks:
        header = [c.strip() for c in block[0].strip("|").split("|")]
        keys = [_TABLE_COL_KEYS.get(h.lower().strip("`")) for h in header]
        if "domain" not in keys or not {"src", "spec"} & set(k for k in keys if k):
            continue
        rows: dict = {}
        for raw in block[1:]:
            cells = [c.strip() for c in raw.strip("|").split("|")]
            if not cells or set("".join(cells)) <= set("-: "):
                continue
            name = _norm_cell(cells[0])
            if not name:
                continue
            rows[name] = {
                keys[i]: cells[i] for i in range(min(len(keys), len(cells))) if keys[i]
            }
        if rows:
            return rows
    return None
