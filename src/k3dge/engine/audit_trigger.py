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

from k3dge.engine.milestone import (
    _find_audit_report,
    get_current_milestone,
    scan_milestone_tasks,
)

_C2_THRESHOLD = 5
_VOLUME_THRESHOLD = 8
_CTRL_NODES = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith,
)


def _git_changed_files(workspace: Path) -> List[str]:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace, capture_output=True, text=True,
        )
        return [ln[3:].strip() for ln in out.stdout.splitlines() if ln.strip()]
    except Exception:
        return []


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
    if n > 0 and not any(t.status in ("in-progress", "idea") for t in tasks):
        reasons.append(f"账齐：本里程碑 {n} 个任务全 done，建议过一遍透镜")

    files = _git_changed_files(workspace)
    srcs = [workspace / f for f in files if f.startswith("src/") and f.endswith(".py")]
    if srcs:
        depth = max((_max_control_depth(p) for p in srcs), default=0)
        if depth >= _C2_THRESHOLD:
            reasons.append(f"C2 嵌套：触及 src/ 控制流 AST 深度最大 {depth} ≥ {_C2_THRESHOLD}")
    vol = [f for f in files if f.startswith("src/") or f.startswith("docs/specs/")]
    if len(vol) >= _VOLUME_THRESHOLD:
        reasons.append(f"体积：变更 {len(vol)} 个 src/specs 文件 ≥ {_VOLUME_THRESHOLD}")
    # NOTE: overview.md staleness is intentionally NOT an audit trigger —
    # updating architecture is handled inside the milestone closure note, not a hook.

    return (len(reasons) > 0, reasons)


def audit_closed(workspace: Path, milestone_id: str) -> bool:
    """True iff BOTH the audit (k3dit) and quality (k3lity) reports exist with 待修==0.

    One "audit pass" = audit + quality each produce a 12-col report and each reach
    待修==0; the fix cycle re-verifies audit→audit report, quality→quality report.
    """
    from k3dge.engine.milestone import _find_report, _parse_audit_stats

    for kind in ("audit", "quality"):
        found = _find_report(workspace, milestone_id, kind)
        if found is None or _parse_audit_stats(found[1])["待修"] != 0:
            return False
    return True
