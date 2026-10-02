"""任务 DAG 透镜（graph-lens §1.4/§6）：`blocking` 依赖环 WARN + CPM 关键路径。

`blocking:` 为 task frontmatter 可选字段（逗号/空格分隔的 task stem 列表＝本任务被谁阻塞）。
**事实，不判定**：环/关键路径只作观测，不进 `check` 判定集（环不阻断）。
"""
from __future__ import annotations

import re
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Dict, List

_SPLIT = re.compile(r"[,\s]+")


def blocking_graph(workspace: Path) -> Dict[str, List[str]]:
    """task → 其 `blocking` 依赖（只连仓内已知 task stem）。"""
    from k3dge.engine.milestone_files import _is_doc_aux
    from k3dge.engine.task_index import parse_frontmatter

    d = Path(workspace) / "docs" / "tasks"
    g: Dict[str, List[str]] = {}
    if not d.is_dir():
        return g
    # 已关票（`X.done.md`）**不作节点**：`p.stem` 对它是 `X.done`，于是关掉的票仍以节点身份
    # 进图、其 frontmatter 残留的 `blocking:` 仍是活边 ⇒ `critical_path` 把已关票报成关键链起点、
    # `blocking_cycles` 报出"互阻环"（已关票不可能阻塞任何人，326）。引用已关票由
    # `blocking_dangling` 单独出事实。
    files = [p for p in sorted(d.glob("*.md"))
             if not _is_doc_aux(p.name) and not p.name.endswith(".done.md")]
    stems = {p.stem for p in files}
    for p in files:
        try:
            fm = parse_frontmatter(p.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeDecodeError):     # 坏编码票不得炸掉整份 DAG 观测（327）
            fm = {}
        deps = [x for x in _SPLIT.split(str(fm.get("blocking", "")).strip()) if x]
        g[p.stem] = [x for x in deps if x in stems]
    return g


def blocking_dangling(workspace: Path) -> Dict[str, List[str]]:
    """`blocking:` 指向**已关票**或**不存在的票**——观测事实，不判定。

    为何需要：`blocking_graph` 只连"仓内已知 task stem"（`p.stem` 对 `X.done.md` 是 `X.done`）
    ⇒ 某票一关，引用它的票那条边被**静默丢弃**，DAG 只是"忘了"，没人知道该清理引用。
    实测（2026-09-19）：三张票的 `blocking` 漂了（两张指向已关票、一处写成 `-`），
    全靠人工扫才发现。

    返回 {"closed": [...引用已关票...], "unknown": [...引用不存在的 stem...]}，各自形如
    `"<referrer> → <target>"`。**进 status 观测，不进 check 判定集**（AUTHORING：blocking
    是事实不是闸）。
    """
    from k3dge.engine.milestone_files import _is_doc_aux
    from k3dge.engine.task_index import parse_frontmatter

    d = Path(workspace) / "docs" / "tasks"
    out: Dict[str, List[str]] = {"closed": [], "unknown": []}
    if not d.is_dir():
        return out
    open_stems, closed_stems = set(), set()
    # 已关票的常态是 `docs/tasks/archive/M*/X.done.md`（顶层只留未归档的几张）：
    # 只 glob 顶层 ⇒ 引用一张已归档票时两边都不在，被报成"不存在的票"而非"已关票"（465）
    files = [p for p in sorted(d.glob("*.md"))] + [p for p in sorted(d.glob("*/**/*.md"))]
    seen_p: set = set()
    for p in files:
        if str(p) in seen_p:
            continue
        seen_p.add(str(p))
        if _is_doc_aux(p.name):
            continue
        if p.name.endswith(".done.md"):
            closed_stems.add(p.name[: -len(".done.md")])
        else:
            open_stems.add(p.stem)
    for p in sorted(d.glob("*.md")):
        if _is_doc_aux(p.name) or p.name.endswith(".done.md"):
            continue
        try:
            fm = parse_frontmatter(p.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeDecodeError):      # 同 327：两个读环同判据
            continue
        for dep in [x for x in _SPLIT.split(str(fm.get("blocking", "")).strip()) if x]:
            if dep in open_stems:
                continue
            kind = "closed" if dep in closed_stems else "unknown"
            out[kind].append(f"{p.stem} → {dep}")
    return out


def _cycles_of(g: Dict[str, List[str]]) -> Dict[str, object]:
    """在**已建好的图**上找环（466：`critical_path`/`summary` 各自重扫一遍盘）。"""
    ts = TopologicalSorter(g)
    try:
        tuple(ts.static_order())
        return {"cyclic": False}
    except CycleError as exc:
        # CycleError.args == ("Cyclic dependencies exist among these items: ", "a -> b -> a")
        # **固定标签在 args[0]，环路径在最后** ⇒ 取 args[0] 只会重复标签、把真正的环丢掉（328）
        detail = str(exc.args[-1]) if exc.args else str(exc)
        return {"cyclic": True, "detail": detail[:200]}


def blocking_cycles(workspace: Path) -> Dict[str, object]:
    """互阻工单＝死锁队列：出事实（`cyclic` + 首个环路径）。"""
    return _cycles_of(blocking_graph(workspace))


def critical_path(workspace: Path) -> Dict[str, object]:
    """最长阻塞链（按节点数）。有环 ⇒ 退化为空（由 `blocking_cycles` 报环）。"""
    return _critical_path_of(blocking_graph(workspace))


def _critical_path_of(g: Dict[str, List[str]]) -> Dict[str, object]:
    """在**已建好的图**上求最长阻塞链（按节点数）。有环 ⇒ 退化为空。"""
    if _cycles_of(g)["cyclic"]:
        return {"path": [], "length": 0, "cyclic": True}
    memo: Dict[str, List[str]] = {}

    def longest(node: str) -> List[str]:
        if node in memo:
            return memo[node]
        best: List[str] = []
        for dep in g.get(node, []):
            p = longest(dep)
            if len(p) > len(best):
                best = p
        memo[node] = [node, *best]
        return memo[node]

    best: List[str] = []
    for n in g:
        p = longest(n)
        if len(p) > len(best):
            best = p
    return {"path": best, "length": len(best), "cyclic": False}


def summary(workspace: Path) -> Dict[str, object]:
    """观测件：环 + 关键路径（不判定）。**同一份图** ⇒ 单盘扫、自洽（ocr2-320）。"""
    g = blocking_graph(workspace)
    cyc = _cycles_of(g)
    cp = _critical_path_of(g)
    return {
        "blocking_cycles": cyc,
        "critical_path": cp["path"],
        "critical_length": cp["length"],
        # 观测事实：`blocking:` 指向已关/不存在的票（票一关边就被静默丢弃，得有人报）
        "blocking_dangling": blocking_dangling(workspace),
    }
