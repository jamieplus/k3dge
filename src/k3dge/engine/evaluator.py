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


def _verification_matrix_section(content: str) -> str:
    m = _VERIFICATION_MATRIX_RE.search(content)
    return content[m.start():] if m else content


def _spec_violation_path(workspace: Path, manifest: Manifest, domain: str) -> Optional[str]:
    rel = manifest.spec_path(domain)
    return str(workspace / rel) if rel else None


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
        if run_tests:
            batch_refs: dict[str, set[str]] = {}
            for domain in sorted(touched):
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
                        if not p.startswith("docs/tasks/") or p.startswith("docs/tasks/archive/") or p.endswith("README.md"):
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

        # 脚手架镜像漂移：assets ↔ 本仓文件必须一致（仅 manifest.self_hosting=true 时，ADR 0018 显式声明）
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
                        asset_text = asset_path.read_text(encoding="utf-8").rstrip("\n")
                        repo_path = self.workspace_root / rel
                        if not repo_path.is_file():
                            continue
                        repo_text = repo_path.read_text(encoding="utf-8").rstrip("\n")
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

        # 协议调度注册表治理：.agent/protocols.toml 语义硬门控（纯静态；文件不存在则优雅跳过，存在则 100% 严格）
        try:
            from k3dge.engine.protocol import validate_protocols_config

            for code, msg in validate_protocols_config(self.workspace_root):
                violations.append(
                    Violation(
                        code,
                        msg,
                        domain="protocols",
                        file_path=".agent/protocols.toml",
                    )
                )
        except Exception as exc:
            violations.append(
                Violation(
                    "PROTOCOL_REGISTRY_INVALID",
                    f"protocol validation crashed: {exc}",
                    domain="protocols",
                    file_path=".agent/protocols.toml",
                )
            )

        return GateReport(
            passed=not violations,
            changed_files=tuple(files),
            modified_domains=tuple(sorted(modified_domains)),
            violations=tuple(violations),
        )

    def _check_domain(self, domain: str, manifest: Manifest) -> List[Violation]:
        spec_rel = manifest.spec_path(domain)
        src_rel = manifest.src_path(domain)
        out: List[Violation] = []

        if not spec_rel:
            return [
                Violation(
                    "SPEC_NOT_FOUND",
                    f"domain '{domain}' has no spec path in manifest",
                    domain=domain,
                )
            ]

        spec_path = self.workspace_root / spec_rel
        if not spec_path.exists():
            return [
                Violation(
                    "SPEC_NOT_FOUND",
                    f"spec missing for domain '{domain}': {spec_rel}",
                    domain=domain,
                    file_path=str(spec_path),
                )
            ]

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
            ]
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
            if not (self.workspace_root / ref).exists():
                out.append(
                    Violation(
                        "MISSING_TEST_FILE",
                        f"Verification Matrix references missing test '{ref}'"
                        + (" (cross-domain reference)" if foreign else ""),
                        domain=domain,
                        file_path=str(spec_path),
                    )
                )
        if src_rel:
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
                return out
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
                out.append(
                    Violation(
                        "CONTRACT_DRIFT",
                        f"public interface changed (spec={expected[:12]}..., code={actual[:12]}...); "
                        "run 'k3dge sync'",
                        domain=domain,
                        file_path=str(spec_path),
                    )
                )

        return out
