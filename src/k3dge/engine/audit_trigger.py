"""Quantifiable audit-suggestion ruler (ADR-0004 §2.1.7).

`k3dge` can suggest an audit on conditions it measures itself — no MCP, no LLM:
  - 账齐    : current milestone top tasks N>0 and none in-progress/idea
  - C2 嵌套 : max control-flow AST depth (if/for/while/try/with) in touched src/ >= 5
  - 体积    : changed files under src/ + docs/specs/ >= 8 since last audit

Seal is NOT suggested here — seal is only offered after the audit loop has closed
(待修==0). There is no ruler for "is it time to end the milestone"; the only real
boundary is the audit closing. Empty window / zero tasks / just a green gate are
not quantitative events, so they trigger nothing.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from k3dge.engine import gates
from k3dge.engine.audit_report import _find_audit_report
from k3dge.engine.milestone_pointer import get_current_milestone
from k3dge.engine.task_index import scan_milestone_tasks

_CTRL_NODES = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith,
)


# k3dit:leftover F-7 @line 与 cli 重复 git status（有意留）
def _git_changed_files(workspace: Path) -> Optional[List[str]]:
    try:
        out = subprocess.run(
            # `-z`（NUL 分隔、不 quote 非 ASCII）；`--untracked-files=all` 展开新目录为文件
            # （否则整包只算 1 个 `?? src/x/`、且不以 .py 结尾 ⇒ C2 触发条件系统性漏判，ocr-052）。
            ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
            cwd=workspace, capture_output=True, text=True, timeout=60,
        )
    except Exception:
        return None                      # git 不可用/异常：与"干净工作区"区分开（ocr-215）
    if out.returncode != 0:
        return None                      # 非仓库 / index.lock / safe.directory ⇒ 未知，不是"没变更"

    toks = out.stdout.split("\0")
    files: List[str] = []
    i = 0
    while i < len(toks):
        e = toks[i]
        i += 1
        if not e:
            continue
        xy, path = e[:2], e[3:]
        if "R" in xy or "C" in xy:
            # rename/copy：`-z` 下下一 token 是**原路径**（跳过），本 token 是新路径（取它）。
            if i < len(toks):
                i += 1
        files.append(path)
    return files


def _max_control_depth(path: Path) -> Optional[int]:
    """None ⇒ **取不到/解析不了**（与"深度 0"不同：这类文件恰恰最可疑，记 0 会让 C2 对它失明，ocr-216）。"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError, RecursionError):
        return None
    best = 0

    def walk(node, depth):
        nonlocal best
        d = depth + (1 if isinstance(node, _CTRL_NODES) else 0)
        if isinstance(node, _CTRL_NODES):
            best = max(best, d)
        for child in ast.iter_child_nodes(node):
            walk(child, d)

    try:
        walk(tree, 0)
    except RecursionError:               # 超深 AST：也不能当成"没嵌套"
        return None
    return best


def compute_audit_suggestion(workspace: Path) -> Tuple[bool, List[str]]:
    """Return (suggested, reasons). Only fires on a quantitative event."""
    mid = get_current_milestone(workspace)
    # 本里程碑已有审计报告 ⇒ 不再**建议**（本轮已审/在审）。口径说明：这里判的是"报告在不在"，
    # 不是 `audit_closed`（待修=0）——**带待修的报告同样抑制建议**，这是有意的：
    # "有待修"由 `check` 的 12 列计数与 `[NEXT] audit_open` 负责递到操作者面前，
    # 建议面（本函数）只管"要不要再开一轮审计"，两处各判各的，别再让文档说它调 `audit_closed`（408）。
    if _find_audit_report(workspace, mid) is not None:
        return False, []

    reasons: List[str] = []
    tasks = scan_milestone_tasks(workspace, mid)
    n = len(tasks)
    if n > 0 and all(t.status == "done" for t in tasks):
        # 正向判"全 done"：`deferred`/`unknown`（状态写错）不得被当成"账齐"（ocr-053）。
        reasons.append(f"账齐：本里程碑 {n} 个任务全 done，建议过一遍透镜")

    c2_max = int(gates.get(workspace, "audit_trigger", "c2_nesting_max"))
    vol_max = int(gates.get(workspace, "audit_trigger", "volume_max"))
    files = _git_changed_files(workspace)
    if files is None:
        # 取不到变更集 ⇒ C2/体积本轮**不可判定**，出声而不是静默少两个触发器（ocr-215）。
        reasons.append("C2/体积不可判定：git 变更集取不到（非仓库/锁/异常）")
        return (True, reasons)
    srcs = [workspace / f for f in files if f.startswith("src/") and f.endswith(".py")]
    if srcs:
        # 已删除/移走的路径（`D src/foo.py`）不在盘上：`_max_control_depth` 会回 None ⇒
        # 纯删除也会报"C2 盲区"（ocr2-215/217）。只扫存在的文件；缺失的不计入盲区。
        existing = [p for p in srcs if p.is_file()]
        depths = [_max_control_depth(p) for p in existing]
        unparsed = sum(1 for d in depths if d is None)
        depth = max((d for d in depths if d is not None), default=0)
        if depth >= c2_max:
            reasons.append(f"C2 嵌套：触及 src/ 控制流 AST 深度最大 {depth} ≥ {c2_max}")
        if unparsed:
            reasons.append(f"C2 盲区：{unparsed} 个触及文件不可解析（语法未过/读失败）")
    try:
        from k3dge.engine.diff import get_changed_files as _committed_changed

        vol_files: Optional[List[str]] = _committed_changed(workspace)
    except Exception:
        vol_files = None
    # "体积"是"自上次审计以来的改动量"：只看未提交工作区会让每次 commit 把计数清零 ⇒
    # 按任务提交的里程碑永远攒不够阈值（ocr2-216）。用 committed 窗口 + 工作区的并集。
    vol = [f for f in (vol_files if vol_files is not None else files)
           if f.startswith("src/") or f.startswith("docs/specs/")]
    if len(vol) >= vol_max:
        reasons.append(f"体积：变更 {len(vol)} 个 src/specs 文件 ≥ {vol_max}")
    # NOTE: overview.md staleness is intentionally NOT an audit trigger —
    # updating architecture is handled inside the milestone closure note, not a hook.

    return (len(reasons) > 0, reasons)


def audit_closed(workspace: Path, milestone_id: str) -> bool:
    """True iff the single audit report exists with 待修==0（报告的**合格性**）。

    One "audit pass" = the merged audit module (ADR-0025) produces ONE 12-col
    report; there is no independent quality peer/report any more.

    **不是封板前置**（ADR-0004 §2.1.3/§2.1.10 🅰1）：报告＝可选产物（存在则须合格，
    不存在不卡流程）；封板资格由 `seal` 相位 2 的**审计正常返回**（闭集，§2.1.11）与
    边界 `tag <M>=<B>` 决定。现在只在两处消费：`audit_checklist`（运行态投影）与
    `compute_audit_suggestion`（"本里程碑已有报告即视为已审"，提醒用）。
    """
    from k3dge.engine.audit_report import _find_report, _parse_audit_stats

    found = _find_report(workspace, milestone_id, "audit")
    if found is None:
        return False
    if "<!-- k3dge:incomplete -->" in found[1]:
        return False   # 未尽项报告永不构成闭环
    stats = _parse_audit_stats(found[1])
    # 截断/畸形行走"解析跳过"口径 ⇒ `待修` 数得出 0 却不代表没有未关项（t-252，ocr-009 同族）
    if stats.get("malformed"):
        return False
    # 未知/空白状态只进 `_ids_未知状态` 不进数字桶：不查它，"状态写错一行"也能 `待修==0` 假闭环（ocr2-074）。
    if stats.get("_ids_未知状态"):
        return False
    return stats["待修"] == 0
