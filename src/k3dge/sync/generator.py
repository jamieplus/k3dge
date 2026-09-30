"""Deterministic spec synchronization: generate interfaces + contract hash from code."""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from k3dge.engine import contract, spec_schema
from k3dge.engine.generated_docs import (
    LAYOUT_END,
    LAYOUT_START,
    _layout_block,
    _replace_between_all,
    render_manual_docs_content,
    render_readme_layout,
)
from k3dge.engine.manifest import Manifest

HASH_LINE_RE = re.compile(r"(\*\*Contract Hash\*\*:).*$", re.MULTILINE)
DATE_LINE_RE = re.compile(r"(\*\*Last Updated\*\*:).*$", re.MULTILINE)
PUBLIC_INTERFACES_RE = re.compile(r"^#{2,3}\s+.*Public Interfaces", re.MULTILINE)

def _interface_block(interface: str) -> str:
    body = interface or "# (no public interface)"
    return f"{contract.INTERFACE_START}\n```python\n{body}\n```\n{contract.INTERFACE_END}"


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

    if content == original:
        # 接口块**没落位**（既无 k3dge:interfaces markers、也无 Public Interfaces 标题）⇒ 不得写
        # 哈希/日期：否则闸拿"哈希行 == 现采"判绿，而 spec 接口块实际缺失且永不自愈（ocr-123）。
        return None
    content = HASH_LINE_RE.sub(
        lambda m: f"{m.group(1)} `sha256:{new_hash}`", content
    )
    content = DATE_LINE_RE.sub(lambda m: f"{m.group(1)} {today}", content)
    spec_path.write_text(content, encoding="utf-8")
    return spec_path


def render_manual_docs(
    workspace: Path, manifest: Manifest, doc_cache: dict[str, str] | None = None
) -> List[Path]:
    """Generate machine docs under docs/generated/ (no agent needed, Diátaxis Reference)."""
    manual_dir = workspace / "docs" / "generated"
    manual_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for path, content in render_manual_docs_content(workspace, manifest, doc_cache).items():
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
            written.append(path)
    return written


def _sync_registry():
    """sync 链的各步：`fn(ctx) -> (ok, msg)`；步间数据经 **ctx** 传递（＝节点声明的 produces）。

    分型（票 orch_node_table）：`sync_extractors` / `sync_domains` / `sync_manual_docs` /
    `sync_docs_index` 是**投影**（可幂等重算）；`reconcile_adrs` 是**事实源写入**
    （改 ADR frontmatter + 移文件 ⇒ 重跑是追加，不是重算）。此前这条链的顺序与失败语义
    都硬编码在本函数里，与声明面并存 ⇒ 现收进 `[checks.sync].actions` + `nodes.run_phase`。
    """
    from k3dge.engine import adr_gate, extractor_gen, nodes
    from k3dge.engine.doc_catalog import write_docs_index
    from k3dge.engine.nodes import on_error as _on_error  # noqa: F401  (声明可读性)

    def sync_extractors(ctx):
        ws = ctx["workspace"]
        if not ((ws / ".agent" / "extractors.toml").is_file() or (ws / ".agent" / "extractors").is_dir()):
            return True, ""      # opt-in：没有配置就不产生意外文件
        try:
            extractor_gen.sync_extractors(ws)
            return True, ""
        except extractor_gen.ExtractorConfigError as exc:
            return False, f"[SYNC] extractor config error: {exc}"

    def reconcile_adrs(ctx):
        ws = ctx["workspace"]
        try:
            report = adr_gate.reconcile_supersedes(ws)
        except Exception as exc:      # 归档失败不得阻断其余同步（on_error=continue）
            return False, f"[SYNC] ADR reconcile failed: {exc}"
        ctx["adr_report"] = report
        return True, (f"[SYNC] {report}" if report else "")

    def sync_domains(ctx):
        ws, manifest = ctx["workspace"], ctx["manifest"]
        # 每域只采一次接口：契约哈希用干净接口，api.md 用含 docstring 的版本
        # （docstring 变动不得动哈希）
        iface_cache: dict[str, str] = {}
        doc_cache: dict[str, str] = {}
        for d, cfg in manifest.domains.items():
            src = cfg.get("src", "")
            if src:
                src_dir = ws / Path(src)
                iface_cache[d] = contract.collect_domain_interface(src_dir, manifest, ws)
                doc_cache[d] = contract.collect_domain_interface(src_dir, manifest, ws, include_doc=True)
        ctx["doc_cache"] = doc_cache
        targets = list(ctx["domains"]) if ctx.get("domains") else list(manifest.domains)
        for domain in targets:
            if domain not in manifest.domains:
                continue
            if sync_domain(ws, manifest, domain, iface=iface_cache.get(domain)) is not None:
                ctx["changed"].append(domain)
        return True, ""

    def sync_manual_docs(ctx):
        # README 的**自动块**（`k3dge:layout-start/end`，域表）随 sync 一起刷——它由 manifest
        # 派生，属投影；README 的散文（markers 之外）仍归人。2026-09-21 前这块只在
        # `scripts/generate-docs.sh` 里刷 ⇒ 域表陈旧无人发现（悬空生成路径）。
        wrote = render_manual_docs(ctx["workspace"], ctx["manifest"], ctx.get("doc_cache") or {})
        if render_readme_layout(ctx["workspace"], ctx["manifest"]) is not None:
            wrote = list(wrote) + [ctx["workspace"] / "README.md"]
        ctx["docs_updated"] = bool(wrote)
        return True, ""

    def sync_docs_index(ctx):
        write_docs_index(ctx["workspace"])
        return True, ""

    return {"sync_extractors": sync_extractors, "reconcile_adrs": reconcile_adrs,
            "sync_domains": sync_domains, "sync_manual_docs": sync_manual_docs,
            "sync_docs_index": sync_docs_index}


def sync_all(workspace: Path, domains: Optional[Sequence[str]] = None) -> Tuple[List[str], bool]:
    """按 `[checks.sync].actions` 的**声明序**跑同步链；步间数据经 ctx 传递。

    返回值仍是 `(changed_domains, docs_updated)`（调用方契约不变），但两者来自
    ctx 的 `produces`（由节点写入），而不是本函数里的局部变量。
    """
    from k3dge.engine import nodes

    ctx = {"workspace": workspace, "manifest": Manifest.load(workspace),
           "domains": domains, "changed": [], "docs_updated": False}
    ok, out = nodes.run_phase(workspace, "sync", "actions", _sync_registry(), ctx)
    if out:
        print(out)
    if not ok:
        print(f"[SYNC] 中止：{out}")
    return ctx["changed"], ctx["docs_updated"]
