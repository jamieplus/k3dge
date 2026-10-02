"""Deterministic spec synchronization: generate interfaces + contract hash from code."""

from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from k3dge.engine import contract, spec_schema
from k3dge.engine.atomic import atomic_write_text
from k3dge.engine.generated_docs import (
    # LAYOUT_*/_layout_block 曾在：README 布局块改由 render_readme_layout 内部负责后就是死导入（470）
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

    from k3dge.engine.pure_refs import inside_workspace

    # `spec_rel`/`src_rel` 来自 manifest（下游可写）：绝对路径会让 `workspace / rel` **丢掉基路径**，
    # `..` 同理 ⇒ 读写跑到仓外（471）
    for label, rel in (("spec", spec_rel), ("src", src_rel)):
        if not inside_workspace(workspace, rel):
            print(f"[sync] WARN: 域 {domain} 的 {label} 路径越出仓外（{rel!r}）⇒ 跳过该域",
                  file=sys.stderr)
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
    except (UnicodeDecodeError, OSError) as exc:
        # 不是 UTF-8 / 读不出的 spec ⇒ 该域**每一轮 sync 都被无声跳过**，而 verify_contract
        # 持续以哈希不通过阻断提交，操作者拿不到任何定位信息（340）。跳过仍要出声。
        print(f"[sync] WARN: {spec_path} 读不出（{type(exc).__name__}: {exc}）⇒ 本轮跳过该域",
              file=sys.stderr)
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
        # 但 `_replace_between_all` 在"markers 在、生成块与现存逐字节相同"时也返回原串（ocr2-342）：
        # 此时落位成功、内容已是最新，只需刷哈希/日期行，不得静默 return None（否则 verify 永红、
        # sync 永不自愈的死锁，且无任何 WARN）。
        if (contract.INTERFACE_START in original and contract.INTERFACE_END in original) or \
                PUBLIC_INTERFACES_RE.search(original):
            content = original
        else:
            print(f"[sync] WARN: 域 {domain} 的接口块没落位（缺 k3dge:interfaces markers 与 Public Interfaces 标题）"
                  "⇒ 只跳过本域（哈希/日期不行）", file=sys.stderr)
            return None
    # 哈希/日期行必须真落位：`sub` 零匹配时静默无事发生，但接口块已重写、函数还返回
    # spec_path（成功形）⇒ 闸拿"哈希行 == 现采"判绿，而日期/哈希实际没更新（ocr2-090）。
    content, n_hash = HASH_LINE_RE.subn(
        lambda m: f"{m.group(1)} `sha256:{new_hash}`", content
    )
    content, n_date = DATE_LINE_RE.subn(lambda m: f"{m.group(1)} {today}", content)
    if n_hash == 0 or n_date == 0:
        return None
    atomic_write_text(spec_path, content)      # 就地截断写会把契约事实源留在半截状态（341）
    return spec_path


def render_manual_docs(
    workspace: Path, manifest: Manifest, doc_cache: dict[str, str] | None = None
) -> List[Path]:
    """Generate machine docs under docs/generated/ (no agent needed, Diátaxis Reference)."""
    manual_dir = workspace / "docs" / "generated"
    manual_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for path, content in render_manual_docs_content(workspace, manifest, doc_cache).items():
        try:
            same = path.exists() and path.read_text(encoding="utf-8") == content
        except (OSError, UnicodeDecodeError):
            same = False
        if not same:
            atomic_write_text(path, content)
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
        from k3dge.engine.pure_refs import inside_workspace

        targets = list(ctx["domains"]) if ctx.get("domains") else list(manifest.domains)
        # 只采本轮目标域：全量预采会让 `--domain x` 重扫整个仓库的 src 树（ocr2-343b）。
        wanted = {d for d in targets if d in manifest.domains}
        iface_cache: dict[str, str] = {}
        doc_cache: dict[str, str] = {}
        for d in wanted:
            cfg = manifest.domains[d]
            src = cfg.get("src", "")
            if src:
                # `sync_domain` 单域有 `inside_workspace` 守卫，这里批量预采也要同口径（ocr2-091）：
                # manifest 可被下游改，`..`/绝对路径不拦就扫到仓外。
                if not inside_workspace(ws, src):
                    print(f"[sync] WARN: 域 {d} 的 src 越出仓外（{src!r}）⇒ 跳过接口预采",
                          file=sys.stderr)
                    continue
                src_dir = ws / Path(src)
                #  clean 接口与 doc 版语义不同（后者逐文件前插 `# <name>` + docstring 首行），
                # 文本剥离不可靠 ⇒ 仍采两次，但只采本轮目标域（ocr2-343）。
                iface_cache[d] = contract.collect_domain_interface(src_dir, manifest, ws)
                doc_cache[d] = contract.collect_domain_interface(src_dir, manifest, ws, include_doc=True)
        ctx["doc_cache"] = doc_cache
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
        # 中止**不许**回落成"成功形"返回值：调用方看到 `(changed, docs_updated)` 无法区分
        # "跑完且无改动"与"中途掐断"，会把掐断报成成功（ocr2-005）。抛出来，各入口按失败处理。
        raise RuntimeError(f"sync 中止：{out}")
    return ctx["changed"], ctx["docs_updated"]
