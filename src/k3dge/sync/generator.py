"""Deterministic spec synchronization: generate interfaces + contract hash from code."""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from k3dge.engine import contract, spec_schema
from k3dge.engine.manifest import Manifest

HASH_LINE_RE = re.compile(r"(\*\*Contract Hash\*\*:).*$", re.MULTILINE)
DATE_LINE_RE = re.compile(r"(\*\*Last Updated\*\*:).*$", re.MULTILINE)
PUBLIC_INTERFACES_RE = re.compile(r"^#{2,3}\s+.*Public Interfaces", re.MULTILINE)

LAYOUT_START = "<!-- k3dge:layout-start -->"
LAYOUT_END = "<!-- k3dge:layout-end -->"


def _interface_block(interface: str) -> str:
    body = interface or "# (no public interface)"
    return f"{contract.INTERFACE_START}\n```python\n{body}\n```\n{contract.INTERFACE_END}"


def _layout_block(manifest: Manifest) -> str:
    header = "| Domain | Source | Spec | Description |\n| --- | --- | --- | --- |"
    rows = []
    for domain in sorted(manifest.domains):
        cfg = manifest.domains[domain]
        src = cfg.get("src", "")
        spec = cfg.get("spec", "")
        desc = cfg.get("description", "")
        rows.append(f"| {domain} | `{src}` | `{spec}` | {desc} |")
    return f"{LAYOUT_START}\n{header}\n" + "\n".join(rows) + f"\n{LAYOUT_END}"


def _replace_between_all(content: str, start: str, end: str, replacement: str) -> Optional[str]:
    """Replace every start..end span with a single replacement (first occurrence position)."""
    if start not in content or end not in content:
        return None
    s = content.index(start)
    # remove all further duplicate spans (search from after the first start)
    while True:
        s2 = content.find(start, s + len(start))
        if s2 == -1:
            break
        e2 = content.find(end, s2)
        if e2 == -1:
            break
        content = content[:s2] + content[e2 + len(end):]
        # do not advance s; keep scanning from first marker
    e = content.find(end, s)
    if e == -1:
        return None
    e += len(end)
    return content[:s] + replacement + content[e:]


def _insert_after_heading(content: str, pattern: "re.Pattern[str]", block: str) -> str:
    match = pattern.search(content)
    if not match:
        return content
    idx = match.end()
    nl = content.find("\n", idx)
    idx = nl + 1 if nl != -1 else len(content)
    return content[:idx] + block + "\n" + content[idx:]


def sync_domain(
    workspace: Path, manifest: Manifest, domain: str, iface: str | None = None
) -> Optional[Path]:
    spec_rel = manifest.spec_path(domain)
    src_rel = manifest.src_path(domain)
    if not spec_rel or not src_rel:
        return None

    spec_path = workspace / spec_rel
    src_dir = workspace / src_rel
    if not spec_path.exists():
        return None

    if iface is None:
        interface = contract.collect_domain_interface(src_dir, manifest, workspace)
    else:
        interface = iface
    new_hash = contract.compute_hash(interface)
    today = datetime.date.today().isoformat()

    try:
        original = spec_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        # Spec is not valid UTF-8 — treat as missing and let next sync retry, don't crash
        return None
    current_hash = spec_schema.extract_contract_hash(original)
    # 防抖：哈希未变则不触碰接口块与日期，避免无意义脏提交
    if current_hash == new_hash:
        return None
    content = original

    replaced = _replace_between_all(
        content, contract.INTERFACE_START, contract.INTERFACE_END, _interface_block(interface)
    )
    if replaced is not None:
        content = replaced
    else:
        content = _insert_after_heading(content, PUBLIC_INTERFACES_RE, _interface_block(interface))

    content = HASH_LINE_RE.sub(
        lambda m: f"{m.group(1)} `sha256:{new_hash}`", content
    )
    content = DATE_LINE_RE.sub(lambda m: f"{m.group(1)} {today}", content)
    spec_path.write_text(content, encoding="utf-8")
    return spec_path


def render_readme_layout(workspace: Path, manifest: Manifest) -> Optional[Path]:
    """Regenerate the README layout block from the manifest (no-op if README lacks markers)."""
    readme = workspace / "README.md"
    if not readme.exists():
        return None
    content = readme.read_text(encoding="utf-8")
    rendered = _replace_between_all(content, LAYOUT_START, LAYOUT_END, _layout_block(manifest))
    if rendered is None or rendered == content:
        return None
    readme.write_text(rendered, encoding="utf-8")
    return readme


def render_manual_docs(
    workspace: Path, manifest: Manifest, doc_cache: dict[str, str] | None = None
) -> List[Path]:
    """Generate machine docs under docs/generated/ (no agent needed, Diátaxis Reference)."""
    manual_dir = workspace / "docs" / "generated"
    manual_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []

    # api.md — aggregated public interfaces per domain (docstrings included for readability)
    api_path = manual_dir / "api.md"
    lines = ["# API Reference", "", "> Auto-generated by `k3dge sync` — do not edit.", ""]
    for domain in sorted(manifest.domains):
        src = manifest.domains[domain].get("src", "")
        if not src:
            continue
        if doc_cache is not None and domain in doc_cache:
            iface = doc_cache[domain]
        else:
            iface = contract.collect_domain_interface(workspace / src, manifest, workspace, include_doc=True)
        lines.append(f"## {domain} — `{src}`")
        lines.append("")
        if iface.strip():
            lines.append("```python")
            lines.append(iface)
            lines.append("```")
        else:
            lines.append("_No public interface._")
        lines.append("")
    api_content = "\n".join(lines)
    if not api_path.exists() or api_path.read_text(encoding="utf-8") != api_content:
        api_path.write_text(api_content, encoding="utf-8")
        written.append(api_path)

    # domains.md — manifest snapshot (human-readable projection; NOT the consistency source of truth, which is docs/architecture/overview.md)
    arch_path = manual_dir / "domains.md"
    arch_lines = ["# Domains Reference", "", "> Auto-generated from `.agent/manifest.json` — do not edit.", "> For cross-domain consistency rules see `docs/architecture/overview.md`.", ""]
    arch_lines.append("| Domain | Source | Spec | Description |")
    arch_lines.append("| --- | --- | --- | --- |")
    for domain in sorted(manifest.domains):
        cfg = manifest.domains[domain]
        arch_lines.append(
            f"| {domain} | `{cfg.get('src','')}` | `{cfg.get('spec','')}` | {cfg.get('description','')} |"
        )
    arch_content = "\n".join(arch_lines) + "\n"
    if not arch_path.exists() or arch_path.read_text(encoding="utf-8") != arch_content:
        arch_path.write_text(arch_content, encoding="utf-8")
        written.append(arch_path)

    return written


def sync_all(workspace: Path, domains: Optional[Sequence[str]] = None) -> Tuple[List[str], bool]:
    manifest = Manifest.load(workspace)
    # Pre-collect once per domain: clean interfaces for the contract hash (spec),
    # doc-included for display (api.md). Docstring churn must NOT touch the hash.
    iface_cache: dict[str, str] = {}
    doc_cache: dict[str, str] = {}
    for d, cfg in manifest.domains.items():
        src = cfg.get("src", "")
        if src:
            src_dir = workspace / Path(src)
            iface_cache[d] = contract.collect_domain_interface(src_dir, manifest, workspace)
            doc_cache[d] = contract.collect_domain_interface(src_dir, manifest, workspace, include_doc=True)
    targets = list(domains) if domains else list(manifest.domains)
    changed: List[str] = []
    for domain in targets:
        if domain not in manifest.domains:
            continue
        result = sync_domain(workspace, manifest, domain, iface=iface_cache.get(domain))
        if result is not None:
            changed.append(domain)
    # README 由收尾脚本（docs 生成）经 agent 更新，不再由 sync 触碰；基础版本始终存在于仓库
    manual_written = render_manual_docs(workspace, manifest, doc_cache)
    from k3dge.engine.doc_catalog import write_docs_index

    write_docs_index(workspace)
    docs_updated = bool(manual_written)
    return changed, docs_updated