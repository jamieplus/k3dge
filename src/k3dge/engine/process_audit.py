"""过程审计面（SQA，ADR-0001 §2 第 8 条「硬闸契约」的一族）：里程碑证据链的完整性/可追溯。

k3dge 只持本仓工件，故此处判**可确定子集**：
- **完整性**：里程碑闭环 12 列报告存在，且 `审计人` / `透镜来源` 署名非空（报告被署名＝有来源）。
- **可追溯**：报告已入库（git 跟踪），证据是有序工件而非工作区草稿。

**不在本闸**（归 k3dit，待 peer 落地后扩展）：审计线的强时序事实
（`provenance.baseline` == 线头、`lens_version` == 当前、审计发生在 `fix_base` 之后）。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional

_SIGN_KEYS = ("审计人", "透镜来源")


def _field(text: str, key: str) -> str:
    m = re.search(rf"^-\s*\*\*{re.escape(key)}\*\*\s*[:：]\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def evidence_chain_error(workspace: Path, milestone_id: str) -> Optional[str]:
    """证据链（完整性 + 可追溯）不满足 ⇒ 返回拒因；满足 ⇒ None。"""
    from k3dge.engine.audit_report import _find_report

    found = _find_report(workspace, milestone_id, "audit")
    if found is None:
        return f"[SEAL REJECTED] 证据链断裂：里程碑 '{milestone_id}' 无 12 列审计报告。"
    path, text = found
    missing = [k for k in _SIGN_KEYS if not _field(text, k)]
    if missing:
        return f"[SEAL REJECTED] 证据链不完整：报告缺署名/来源 {missing}（{path.name}）。"
    try:
        rel = Path(path).resolve().relative_to(Path(workspace).resolve()).as_posix()
    except ValueError:
        rel = Path(path).name
    try:
        r = subprocess.run(["git", "-C", str(workspace), "ls-files", "--error-unmatch", rel],
                           capture_output=True, text=True)
        tracked = r.returncode == 0
    except OSError:
        tracked = False
    if not tracked:
        return f"[SEAL REJECTED] 证据链不可追溯：报告未入库（{rel}）。"
    return None
