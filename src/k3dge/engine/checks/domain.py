"""域级检查：spec 结构 / 验证矩阵 / 契约哈希 / 反向 import 禁令。自 `ConsistencyEngine` 拆出。"""

import ast
import re
from pathlib import Path
from typing import List, Optional, Set

from k3dge.engine import contract, spec_schema
from k3dge.engine.contract import _ExtractError
from k3dge.engine.manifest import Manifest
from k3dge.engine.models import Violation

_TEST_REF_RE = re.compile(r"`(tests/[^\s`]+)`")
_VERIFICATION_MATRIX_RE = re.compile(r"^#{2,3}\s+.*Verification Matrix", re.MULTILINE)


def _verification_matrix_section(content: str) -> str:
    m = _VERIFICATION_MATRIX_RE.search(content)
    return content[m.start():] if m else content


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
        nxt = re.search(r"\n#{2,3}\s+", spec_content[m.start() + 1:])
        sec = spec_content[m.start(): nxt.start() if nxt else len(spec_content)]
        if any(n in sec for n in needles):
            return True
    return False


def _load_domain_spec(workspace: Path, domain: str, manifest: Manifest):
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

    spec_path = workspace / spec_rel
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
    workspace: Path, domain: str, manifest: Manifest, spec_path: Path, content: str
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
        target = workspace / fpath
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
    workspace: Path, domain: str, manifest: Manifest, spec_path: Path, content: str
):
    """Contract check. Returns (violations, fatal); fatal=True stops further checks."""
    out: List[Violation] = []
    src_rel = manifest.src_path(domain)
    if not src_rel:
        return out, False
    src_dir = workspace / src_rel
    try:
        ok, expected, actual = contract.verify_contract(
            src_dir, content, manifest, workspace
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
            detail = contract.symbol_diff(content, src_dir, manifest, workspace)
        except Exception:
            detail = None
        if detail and any(detail.get(k) for k in ("added", "removed", "changed")):
            if not _shape_change_documented(workspace, domain, content, detail):
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


def _check_domain_imports(workspace: Path, domain: str, manifest: Manifest) -> List[Violation]:
    """Reverse-import ban: a domain may import another domain only if declared in depends_on (ADR-0001 decision 6)."""
    out: List[Violation] = []
    src_rel = manifest.src_path(domain)
    if not src_rel:
        return out
    src_dir = workspace / src_rel
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
        chain = _pkg_chain(workspace, py, pkg)
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


def check_domain(workspace: Path, domain: str, manifest: Manifest) -> List[Violation]:
    """一个域的全套检查：spec 结构 → 验证矩阵 → 契约哈希 → 反向 import。"""
    out, spec_path, content = _load_domain_spec(workspace, domain, manifest)
    if content is None:
        return out
    out.extend(_check_verification_matrix(workspace, domain, manifest, spec_path, content))
    contract_out, fatal = _check_domain_contract(workspace, domain, manifest, spec_path, content)
    out.extend(contract_out)
    if fatal:
        return out
    out.extend(_check_domain_imports(workspace, domain, manifest))
    return out
