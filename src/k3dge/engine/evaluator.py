"""Consistency engine: orchestrates the gate evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Set

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
                Violation("MANIFEST_INVALID", f"test_command_template is invalid: {exc}")
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
                        f"Tests timed out after 300s (batch {refs})",
                        domain=d,
                        file_path=_spec_violation_path(workspace, manifest, d),
                    )
                )
        return violations
    except FileNotFoundError:
        for _ref, domains in batch_refs.items():
            for d in domains:
                violations.append(
                    Violation(
                        "TEST_ENV_MISSING",
                        "pytest not available; cannot run --with-tests",
                        domain=d,
                        file_path=_spec_violation_path(workspace, manifest, d),
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
                        "pytest not available; cannot run --with-tests",
                        domain=d,
                        file_path=_spec_violation_path(workspace, manifest, d),
                    )
                )
        return violations
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    failed = {ref for ref in refs if ref in output and ("FAILED" in output or "failed" in output.lower())}
    if not failed:
        failed = set(refs)
    for ref in sorted(failed):
        for d in sorted(batch_refs[ref]):
            violations.append(
                Violation(
                    "TEST_FAILURE",
                    f"Test '{ref}' failed (run with --with-tests)",
                    domain=d,
                    file_path=_spec_violation_path(workspace, manifest, d),
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

# k3dit:pending value-1 sev=中 prio=P2 type=结构 evaluate:182 god-method 283行/CC61，一个方法混居≥9类门控：manifest加载+git diff/staged+docs根策略+spec/src域映射+测试批跑/depends_on+版本一致+CHANGELOG done告警+模板漂移(self-host)+pipeline硬门+docs校验，各段自包 try/except 塞 Violation；远超 M7-quality Q-3 已接受带(CC11-19 argparse 派，不覆盖本函数)，应下沉为独立门控子检查（_check_domain 已有抽取先例可循）
    def evaluate(self, run_tests: bool = False, force_full: bool = False, staged: bool = False) -> GateReport:
        try:
            manifest = Manifest.load(self.workspace_root)
        except ManifestError as exc:
            return GateReport(
                passed=False,
                changed_files=(),
                modified_domains=(),
                violations=(Violation("MANIFEST_INVALID", str(exc)),),
            )
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
                        )
                    ]
                    if not manifest.domains:
                        git_vs.insert(
                            0,
                            Violation(
                                "NO_DOMAINS",
                                "manifest.domains is empty; register at least one domain "
                                "(src/spec/tests) so the gate can protect this repo",
                            ),
                        )
                    return GateReport(
                        passed=False,
                        changed_files=(),
                        modified_domains=(),
                        violations=tuple(git_vs),
                    )
                files = ()

        violations: List[Violation] = []
        if not manifest.domains:
            violations.append(
                Violation(
                    "NO_DOMAINS",
                    "manifest.domains is empty; register at least one domain "
                    "(src/spec/tests) so the gate can protect this repo",
                )
            )
        modified_domains: Set[str] = set()
        specs_touched: Set[str] = set()

        for path in files:
            if manifest.is_ignored(path):
                continue
            if path.endswith("__init__.py"):
                continue
            # 强制 docs/ 根下不直放文档；唯一例外是 docs/README.md（根索引/治理总纲）。其余需置于细分目录
            if path.startswith("docs/") and "/" not in path[5:] and not path.endswith("/"):
                name = path[5:]
                if name and not name.startswith(".") and name not in (".DS_Store", "README.md"):
                    violations.append(
                        Violation(
                            "DOCS_ROOT_DISALLOWED",
                            f"docs root file '{path}' must be in a subdirectory (e.g. docs/generated/, docs/guides/); create a new subdirectory if none fits",
                            file_path=path,
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
                violations.append(
                    Violation(
                        "UNREGISTERED_DOMAIN",
                        f"'{path}' lives under package_root but no domain maps it",
                        file_path=path,
                    )
                )
                continue
            modified_domains.add(domain)

        touched = modified_domains | specs_touched
        if force_full:
            touched = set(manifest.domains)
            modified_domains = set(manifest.domains)

        # 收集所有 touched 域的 tests 路径，去重后批量执行（直接基于 manifest，不爬 spec 表格）
        # 跨域影响：某域公开哈希变化时，跑声明 depends_on 该域的消费方域测试（ADR-0001 决策点 6）
        if run_tests:
            affected = set(modified_domains)
            for d in sorted(manifest.domains):
                if set(manifest.depends_on(d)) & affected:
                    affected.add(d)
            batch_refs: dict[str, set[str]] = {}
            for domain in sorted(affected):
                ref = manifest.domains.get(domain, {}).get("tests", "")
                if ref and (self.workspace_root / ref).exists():
                    batch_refs.setdefault(ref, set()).add(domain)
            violations.extend(_run_batch_tests(self.workspace_root, manifest, batch_refs))

        for domain in sorted(touched):
            violations.extend(self._check_domain(domain, manifest))

        # 版本一致性：pyproject.toml ↔ .agent/manifest.json ↔ src/k3dge/__init__.py 必须同值
        try:
            from k3dge.engine.version import validate_versions

            violations.extend(validate_versions(self.workspace_root))
        except Exception as exc:
            violations.append(
                Violation(
                    "VERSION_MISMATCH",
                    f"version validation failed: {exc}",
                    file_path=str(self.workspace_root / "pyproject.toml"),
                )
            )

        # 轻量 P3：任务手改 done 未进 CHANGELOG Unreleased 时 WARN（不硬卡，仅提示，避免漏记）
        # 仅检查 living tasks（docs/tasks/*.md），不含 archive/（已封板，其标题已在版本化历史中）
        try:
            from k3dge.engine.milestone import TITLE_RE as _MilestoneTitleRE, parse_frontmatter

            changelog_path = self.workspace_root / "CHANGELOG.md"
            if changelog_path.is_file():
                changelog_text = changelog_path.read_text(encoding="utf-8")
                unreleased_tag = "## [Unreleased]"
                u_idx = changelog_text.find(unreleased_tag)
                if u_idx != -1:
                    u_next = changelog_text.find("## [", u_idx + len(unreleased_tag))
                    unreleased_block = changelog_text[u_idx:u_next] if u_next != -1 else changelog_text[u_idx:]
                    for p in files:
                        if (
                            not p.startswith("docs/tasks/")
                            or p.startswith("docs/tasks/archive/")
                            or p.endswith("README.md")
                            or p.endswith("_template.md")
                        ):
                            continue
                        task_path = self.workspace_root / p
                        if not task_path.is_file():
                            continue
                        try:
                            t_content = task_path.read_text(encoding="utf-8")
                        except (OSError, UnicodeDecodeError):
                            continue
                        fm = parse_frontmatter(t_content)
                        st = fm.get("status", "").lower() if fm else ""
                        if not st:
                            m = re.search(r"-\s+\*\*Status\*\*:\s*([\w-]+)", t_content, re.IGNORECASE)
                            st = m.group(1).lower() if m else ""
                        if st != "done":
                            continue
                        tm = _MilestoneTitleRE.search(t_content)
                        title = tm.group(1).strip() if tm else task_path.stem
                        if title and title not in unreleased_block:
                            import sys

                            print(
                                f"[WARN][CHANGELOG] Task '{title}' marked done ({p}) not in CHANGELOG.md ## [Unreleased]; "
                                f"run 'k3dge task done' or ensure _append_to_unreleased succeeded",
                                file=sys.stderr,
                            )
        except Exception:
            pass

        # 脚手架镜像漂移：assets ↔ 本仓文件必须一致（仅 manifest.self_hosting=true 时，ADR-0014 显式声明）
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
                            violations.append(
                                Violation(
                                    "TEMPLATE_DRIFT",
                                    f"template drift: assets/{asset} != {rel}",
                                    file_path=rel,
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
            violations.append(
                Violation(
                    "TEMPLATE_DRIFT",
                    f"template drift check failed: {exc}",
                    file_path="src/k3dge/engine/pairs.py",
                )
            )

        # 生命周期总线治理：pipeline.toml 语义硬门控（纯静态；文件不存在则优雅跳过，存在则 100% 严格）
        try:
            from k3dge.engine.pipeline_schema import validate_pipeline_config

            for code, msg in validate_pipeline_config(self.workspace_root):
                violations.append(
                    Violation(
                        code,
                        msg,
                        domain="pipelines",
                        file_path=".agent/pipeline.toml",
                    )
                )
        except Exception as exc:
            violations.append(
                Violation(
                    "PIPELINE_SCHEMA_INVALID",
                    f"pipeline validation crashed: {exc}",
                    domain="pipelines",
                    file_path=".agent/pipeline.toml",
                )
            )

        docs_touched = any(str(p).replace("\\", "/").startswith("docs/") for p in files)
        if force_full or docs_touched:
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
                violations.extend(validate_docs(self.workspace_root, types=types))
                violations.extend(validate_docs_index(self.workspace_root))
            except Exception as extra:
                violations.append(
                    Violation(
                        "DOC_SCHEMA_INVALID",
                        f"docs catalog check crashed: {extra}",
                        file_path="docs",
                    )
                )

        return GateReport(
            passed=not violations,
            changed_files=tuple(files),
            modified_domains=tuple(sorted(modified_domains)),
            violations=tuple(violations),
        )

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
                )
            ], None, None
        return [], spec_path, content

    def _check_verification_matrix(
        self, domain: str, manifest: Manifest, spec_path: Path, content: str
    ) -> List[Violation]:
        out: List[Violation] = []
        for err in spec_schema.validate_structure(content):
            out.append(
                Violation("SPEC_MISSING_SECTION", err, domain=domain, file_path=str(spec_path))
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
                        )
                    )
            elif not re.search(r"\bdef\s+test_", _t_src):
                out.append(
                    Violation(
                        "MATRIX_TEST_UNRESOLVED",
                        f"Verification Matrix row references '{fpath}' which contains no test functions",
                        domain=domain,
                        file_path=str(spec_path),
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
                )
            )
            return out, True
        if expected is None:
            out.append(
                Violation(
                    "CONTRACT_HASH_MISSING",
                    "no contract hash in spec; run 'k3dge sync'",
                    domain=domain,
                    file_path=str(spec_path),
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
                    f"public interface changed (spec={expected[:12]}..., code={actual[:12]}...); "
                    "run 'k3dge sync'",
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

    def _check_domain_imports(self, domain: str, manifest: Manifest) -> List[Violation]:
        """Reverse-import ban: a domain may import another domain only if declared in depends_on (ADR-0001 decision 6)."""
        out: List[Violation] = []
        src_rel = manifest.src_path(domain)
        if not src_rel:
            return out
        src_dir = self.workspace_root / src_rel
        if not src_dir.exists():
            return out
# k3dit:pending code-6 sev=中 prio=P2 type=隐蔽 _check_domain_imports:645 正则把包前缀硬编码为 "k3dge."：下游仓（不同包名，如 k3dit/k3che）任何跨域导入都不匹配 → ADR-0001 决策6 的反向导入禁令对下游静默空转、check 常绿（downstream-first 是 ADR-0015 主用途），且只认一级 `k3dge.<domain>`，`from k3dge.engine.sub import` 之类也只取 engine。前缀应取自 manifest（package_root/域 src 公共段推导）。evidence=python3 -c "import re;print(bool(re.match(r'^\s*(?:from\s+k3dge\.([a-z_]+)|import\s+k3dge\.([a-z_]+))','from k3dit.engine import x')))" 出 False
        import_re = re.compile(r"^\s*(?:from\s+k3dge\.([a-z_]+)|import\s+k3dge\.([a-z_]+))")
        allowed = set(manifest.depends_on(domain))
        for py in sorted(src_dir.rglob("*.py")):
            if py.name == "__init__.py":
                continue
            try:
                text = py.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for line in text.splitlines():
                m = import_re.match(line)
                if not m:
                    continue
                target = m.group(1) or m.group(2)
                if target == domain or target not in manifest.domains:
                    continue
                if target not in allowed:
                    out.append(
                        Violation(
                            "DOMAIN_IMPORT_VIOLATION",
                            f"domain '{domain}' imports '{target}' but does not declare depends_on ('{target}')",
                            domain=domain,
                            file_path=str(py),
                        )
                    )
        return out
