"""Quantifiable audit-suggestion ruler (ADR-0004 §2.1.7).

`k3dge` can suggest an audit on conditions it measures itself — no MCP, no LLM:
  - 账齐    : current milestone top tasks N>0 and none in-progress/idea
  - C2 嵌套 : max control-flow AST depth (if/for/while/try/with) in touched src/ >= 5
  - 体积    : changed files under src/ + docs/specs/ >= 8 since last audit
  - 文档不同步: src/ changed while overview.md not changed

Seal is NOT suggested here — seal is only offered after the audit loop has closed
(待修==0). There is no ruler for "is it time to end the milestone"; the only real
boundary is the audit closing. Empty window / zero tasks / just a green gate are
not quantitative events, so they trigger nothing.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from typing import List, Tuple

from k3dge.engine import gates
from k3dge.engine.audit_report import _find_audit_report
from k3dge.engine.milestone_pointer import get_current_milestone
from k3dge.engine.task_index import scan_milestone_tasks

_CTRL_NODES = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith,
)


# k3dit:leftover F-7 @line 与 cli 重复 git status（有意留）
def _git_changed_files(workspace: Path) -> List[str]:
    try:
        out = subprocess.run(
            # `-z`（NUL 分隔、不 quote 非 ASCII）；`--untracked-files=all` 展开新目录为文件
            # （否则整包只算 1 个 `?? src/x/`、且不以 .py 结尾 ⇒ C2 触发条件系统性漏判，ocr-052）。
            ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
            cwd=workspace, capture_output=True, text=True,
        )
    except Exception:
        return []
    if out.returncode != 0:
        return []
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
        files.append(path.strip())
    return files


def _max_control_depth(path: Path) -> int:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    best = 0

    def walk(node, depth):
        nonlocal best
        d = depth + (1 if isinstance(node, _CTRL_NODES) else 0)
        if isinstance(node, _CTRL_NODES):
            best = max(best, d)
        for child in ast.iter_child_nodes(node):
            walk(child, d)

    walk(tree, 0)
    return best


def compute_audit_suggestion(workspace: Path) -> Tuple[bool, List[str]]:
    """Return (suggested, reasons). Only fires on a quantitative event."""
    mid = get_current_milestone(workspace)
    # An audit report already exists for this milestone -> audit already happened
    # (or is in progress); do not re-suggest within this snapshot.
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
    srcs = [workspace / f for f in files if f.startswith("src/") and f.endswith(".py")]
    if srcs:
        depth = max((_max_control_depth(p) for p in srcs), default=0)
        if depth >= c2_max:
            reasons.append(f"C2 嵌套：触及 src/ 控制流 AST 深度最大 {depth} ≥ {c2_max}")
    vol = [f for f in files if f.startswith("src/") or f.startswith("docs/specs/")]
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
    return _parse_audit_stats(found[1])["待修"] == 0
