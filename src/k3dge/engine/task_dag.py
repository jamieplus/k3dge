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
    from k3dge.engine.milestone import _is_doc_aux, parse_frontmatter

    d = Path(workspace) / "docs" / "tasks"
    g: Dict[str, List[str]] = {}
    if not d.is_dir():
        return g
    files = [p for p in sorted(d.glob("*.md")) if not _is_doc_aux(p.name)]
    stems = {p.stem for p in files}
    for p in files:
        try:
            fm = parse_frontmatter(p.read_text(encoding="utf-8")) or {}
        except OSError:
            fm = {}
        deps = [x for x in _SPLIT.split(str(fm.get("blocking", "")).strip()) if x]
        g[p.stem] = [x for x in deps if x in stems]
    return g


def blocking_cycles(workspace: Path) -> Dict[str, object]:
    """互阻工单＝死锁队列：出事实（`cyclic` + 首个环路径）。"""
    ts = TopologicalSorter(blocking_graph(workspace))
    try:
        tuple(ts.static_order())
        return {"cyclic": False}
    except CycleError as exc:
        return {"cyclic": True, "detail": str(exc.args[0])[:200]}


def critical_path(workspace: Path) -> Dict[str, object]:
    """最长阻塞链（按节点数）。有环 ⇒ 退化为空（由 `blocking_cycles` 报环）。"""
    g = blocking_graph(workspace)
    if blocking_cycles(workspace)["cyclic"]:
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
    """观测件：环 + 关键路径（不判定）。"""
    cp = critical_path(workspace)
    return {
        "blocking_cycles": blocking_cycles(workspace),
        "critical_path": cp["path"],
        "critical_length": cp["length"],
    }
