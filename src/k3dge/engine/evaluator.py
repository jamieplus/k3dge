"""Consistency engine: orchestrates the gate evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Set

import re

from k3dge.engine import diff
from k3dge.engine.diff import GitError
from k3dge.engine.manifest import Manifest, ManifestError
from k3dge.engine.models import GateReport, Violation


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
            parts = shlex.split(str(template))
        except ValueError as exc:
            parts = None
            bad = exc
        if parts is None:
            return [
                Violation("MANIFEST_INVALID", f"test_command_template invalid: {bad}",
                          detail={"path": ".agent/manifest.json",
                                  "reason": f"test_command_template 不是合法模板：{bad}"})
            ]
        # 先分词模板、再把 refs 作为**独立 argv 元素**插入：`format(refs=" ".join(refs))` 会把多个
        # ref 拼成一个串再重新分词 ⇒ 含空格/引号的测试路径被拆成多参数（ocr-240）。
        cmd: list[str] = []
        placed = False
        for tok in parts:
            if "{refs}" in tok:
                pre, _, post = tok.partition("{refs}")
                if pre:
                    cmd.append(pre)
                cmd.extend(refs)
                if post:
                    cmd.append(post)
                placed = True
            else:
                cmd.append(tok)
        if not placed:
            cmd.extend(refs)
        for tok in parts:            # 未知占位符以前靠 .format() 抛 KeyError 兜住；现在显式拒
            for ph in re.finditer(r"\{(\w*)\}", tok):
                if ph.group(1) != "refs":
                    return [
                        Violation("MANIFEST_INVALID",
                                  f"test_command_template invalid: unknown placeholder {ph.group(0)}",
                                  detail={"path": ".agent/manifest.json",
                                          "reason": f"模板只认 {{refs}}，出现 {ph.group(0)}"})
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
                        detail={"domain": d, "target": refs, "reason": "300s 超时",
                                "pytest_tail": "（超时被 killpg，无 pytest 输出）"},
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
                ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRD"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            raise GitError("git 不可用（staged 变更检测）")
        if out.returncode != 0:
            # 不再折叠成空列表（那样 evaluate 会当"无变更"跳过域级门控）；抛出由 caller 转 GIT_UNAVAILABLE（ocr-072）。
            raise GitError(f"git diff --cached 失败：{(out.stderr or '').strip()[:200]}")
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
            try:
                files = self._staged_files()
            except GitError as exc:
                # staged 模式的 git 失败此前只在非 staged 分支捕获，staged 失败会逃逸成调用方崩栈（ocr2-059）。
                # 与非 staged 同口径：报闸，不抛。
                events.emit(self.workspace_root, "gate_fail", violations=1)
                return GateReport(
                    passed=False,
                    violations=(Violation("GIT_UNAVAILABLE", f"git unavailable: {exc}",
                                          file_path="",
                                          detail={"reason": str(exc)}),),
                )
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

        violations.extend(self._check_assert_tautology(files, force_full))

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
        """pyproject ↔ manifest ↔ __init__ 版本同值；异常即 VERSION_MISMATCH（实现见 checks/version）。"""
        from k3dge.engine.checks import version as _c

        return _c.check_version_consistency(self.workspace_root)

    def _check_template_drift(self, manifest: Manifest) -> List[Violation]:
        """脚手架镜像漂移（仅 self_hosting=true，ADR-0001）。实现见 checks/template_drift。"""
        from k3dge.engine.checks import template_drift as _c

        return _c.check_template_drift(self.workspace_root, manifest)

    def _check_pipeline(self) -> List[Violation]:
        """pipeline.toml 语义硬门控（纯静态；文件不存在则优雅跳过）。实现见 checks/pipeline。"""
        from k3dge.engine.checks import pipeline as _c

        return _c.check_pipeline(self.workspace_root)

    def _check_audit_trail(self) -> List[Violation]:
        """`ADR-0008`：审计痕迹只可追加（静态扫覆写式写入）。实现见 checks/audit_trail。"""
        from k3dge.engine.checks import audit_trail as _c

        return _c.check_audit_trail(self.workspace_root)

    def _check_assert_tautology(self, files, force_full: bool) -> List[Violation]:
        """真值已写死的测试断言。实现见 checks/assert_tautology。"""
        from k3dge.engine.checks import assert_tautology as _c

        return _c.check_assert_tautology(self.workspace_root, files, force_full)

    def _check_docs(self, files, force_full: bool) -> List[Violation]:
        """docs 目录结构/索引校验。实现见 checks/docs。"""
        from k3dge.engine.checks import docs as _c

        return _c.check_docs(self.workspace_root, files, force_full)

    def _check_domain(self, domain: str, manifest: Manifest) -> List[Violation]:
        """一个域的全套检查：spec 结构/矩阵/契约/反向 import。实现见 checks/domain。"""
        from k3dge.engine.checks import domain as _c

        return _c.check_domain(self.workspace_root, domain, manifest)

    def _check_generated_projections(self, manifest: Manifest) -> List[Violation]:
        """生成物新鲜度闸：符号索引 / generated docs / `.mcp.json`。实现见 checks/projections。"""
        from k3dge.engine.checks import projections as _c

        return _c.check_generated_projections(self.workspace_root, manifest)

    def _check_mcp_json(self) -> List[Violation]:
        """`.mcp.json` 的 peer 面 vs `pipeline.toml` 声明（同一探测函数）。实现见 checks/mcp_json。"""
        from k3dge.engine.checks import mcp_json as _c

        return _c.check_mcp_json(self.workspace_root)

    def _check_state_doc_coverage(self) -> List[Violation]:
        """`overview.md` 状态闭集覆盖。实现见 checks/state_doc。"""
        from k3dge.engine.checks import state_doc as _c

        return _c.check_state_doc_coverage(self.workspace_root)

    def _check_architecture_tables(self, manifest: Manifest) -> List[Violation]:
        """设计文档域表 vs manifest（表行是事实）。实现见 checks/architecture_tables。"""
        from k3dge.engine.checks import architecture_tables as _c

        return _c.check_architecture_tables(self.workspace_root, manifest)

    def _check_extractor_plugins(self) -> List[Violation]:
        """`.agent/extractors/<lang>.py` 必须是 `extractors.toml` 的当前渲染。实现见 checks/extractors。"""
        from k3dge.engine.checks import extractors as _c

        return _c.check_extractor_plugins(self.workspace_root)

    def _check_docs_toml(self) -> List[Violation]:
        """`.agent/docs.toml` 的 `= true` 键必须被 `generate-docs.sh` 处理。实现见 checks/docs_toml。"""
        from k3dge.engine.checks import docs_toml as _c

        return _c.check_docs_toml(self.workspace_root)

    def _check_domain_imports(self, domain: str, manifest: Manifest) -> List[Violation]:
        """反向 import 禁令（ADR-0001 决策点 6）。实现见 checks/domain。"""
        from k3dge.engine.checks import domain as _c

        return _c._check_domain_imports(self.workspace_root, domain, manifest)
