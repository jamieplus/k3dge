"""Audit-condition checklist (ADR-0004 §2.1.5; reframed from the old seal gate).

Records whether the *audit conditions* are met for the current milestone and the
state of the audit loop — not "can I seal". The checklist holds:
  - the quantifiable suggestion snapshot (audit_trigger: 账齐 / C2 / 体积) -> reasons
  - report closure: the single audit 12-col report's 待修 (merged audit module, ADR-0025)
  - verify_attempts: the >3-loop escalation counter (reset on each audit initiation)
  - audit_started_at: when the current audit pass was initiated (manual or auto)

Caching: keyed by a hash of the current milestone's task statuses so `check` need
not re-scan when nothing changed. **Initiating an audit (`k3dge milestone audit`)
resets the checklist** (fresh verify budget + new started_at).

**这是运行态投影，不是判据**（ADR-0004 §2.1.10 🅰1）：文件在 `.agent/`（本地、可删、可重建）；
判据只认 git 事实（基线 hash / 边界 `tag <M>=<B>` / 封版提交 trailer，见
`audit_flow.audit_evidence`），两者冲突**以 git 为准**。`[NEXT] seal_ready` 的判据在
`cli/status.lifecycle_next`（预审＝形式闸），也不在此。
"""

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
from typing import Optional

CHECK_LIST_PATH = ".agent/audit_checklist.json"


def _path(workspace: Path) -> Path:
    return workspace / CHECK_LIST_PATH


def _tasks_hash(workspace: Path, milestone_id: str) -> str:
    from k3dge.engine.task_index import scan_milestone_tasks

    tasks = scan_milestone_tasks(workspace, milestone_id)
    h = hashlib.sha256()
    for t in sorted(tasks, key=lambda x: x.path.name):
        h.update(f"{t.path.name}:{t.status}".encode("utf-8"))
    return h.hexdigest()


def _snapshot(workspace: Path, milestone_id: str) -> dict:
    from k3dge.engine.audit_trigger import audit_closed, compute_audit_suggestion
    from k3dge.engine.audit_report import _find_report, _parse_audit_stats

    suggested, reasons = compute_audit_suggestion(workspace)
    found = _find_report(workspace, milestone_id, "audit")
    # **升级计入 pending**：k3dge 自己写的升级标记在报告**验证**列（`待验：未闭环` / `升级：本次未落`）——
    # 判定面（封板前置闸 / `[NEXT]`）读的是本清单的 `pending` ⇒ 不计它就会**虚报已审**（用户裁定：
    # 升级由 k3dge 的审后闸报出；报告"状态"列保持产出方原样，所以这里必须自己数）。
    escalated = 0
    if found is not None:
        from k3dge.engine.audit_bundle import ESCALATION_MARKERS
        from k3dge.engine.report_table import parse_rows

        _, rows = parse_rows(found[1])
        escalated = sum(1 for _i, r in rows
                        if any(m in str(r.get("验证") or "") for m in ESCALATION_MARKERS))
    pending_total = 0
    if found:
        from k3dge.engine.audit_report import _parse_audit_stats
        from k3dge.engine.report_table import _OPEN_ALIASES

        _st = _parse_audit_stats(found[1])
        # 状态列与验证列可以是**同一条** finding（reconcile 明写"不动状态列"）⇒ 相加会双计（ocr-207）。
        # 空白 ID 会坍缩成同一个 `""` 成员 ⇒ pending 少报（ocr2-201）：一律用
        # `(ID or 报告行号)` 做键——同一行两列同键仍只计一次，空白行互不相撞。
        _ids = set()
        if rows:
            for idx, r in rows:
                _rid = str(r.get("ID", "")).strip() or f"line{idx + 1}"
                _stv = str(r.get("状态") or "").strip()
                if _stv == "待修" or _stv in _OPEN_ALIASES:
                    _ids.add(_rid)
                if any(m in str(r.get("验证") or "") for m in ESCALATION_MARKERS):
                    _ids.add(_rid)
        else:
            _ids = set(str(i).strip() or f"line{_n}" for _n, i in enumerate(_st.get("_ids_待修") or []))
        pending_total = len(_ids)
    closure = {
        "audit": {
            "present": found is not None,
            "pending": (pending_total if found else None),
            "escalated": escalated,
        },
    }
    return {
        "audit_suggested": suggested,
        "reasons": reasons,
        "closure": closure,
        "closed": audit_closed(workspace, milestone_id),
    }


def _coerce_attempts(v: object) -> int:
    """投影数字字段的手工/损坏值（null/字符串）⇒ 退化成 0，不让审计环崩（ocr2-203）。"""
    try:
        n = int(str(v).strip() if isinstance(v, str) else v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return max(0, n)


def build_checklist(workspace: Path, milestone_id: Optional[str] = None) -> dict:
    """Recompute the audit-condition snapshot and persist it (keeps counters if the
    task set is unchanged)."""
    from k3dge.engine.milestone_pointer import get_current_milestone

    mid = milestone_id or get_current_milestone(workspace)
    h = _tasks_hash(workspace, mid)
    prev = _read_raw(workspace)
    # 计数器生命周期与快照刷新**解耦**：只要还是同一里程碑就保留——否则审计环内"修→重审"改了任务集就把
    # verify 预算清零，`attempts >= max` 永不成立、escalated 转人工不可达（ocr-043）。
    keep = prev is not None and prev.get("milestone_id") == mid
    data = {
        "milestone_id": mid,
        "tasks_hash": h,
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "audit_started_at": (prev or {}).get("audit_started_at") if keep else None,
        "verify_attempts": _coerce_attempts((prev or {}).get("verify_attempts", 0)) if keep else 0,
    }
    data.update(_snapshot(workspace, mid))
    _write(workspace, data)
    return data


def _read_raw(workspace: Path) -> Optional[dict]:
    """读快照文件**不做新鲜度判定**（供 `build_checklist` 保留计数器——计数器不该因任务集变了就丢，ocr-043）。"""
    p = _path(workspace)
    if not p.is_file():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def read_checklist(workspace: Path, milestone_id: Optional[str] = None) -> Optional[dict]:
    p = _path(workspace)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        # `[]`/`"x"`/`null` 是**合法但非 object** 的 JSON：旧版 `except Exception` 之外还会让
        # `data.get` 抛 AttributeError 逸出（ensure_checklist → 全流程崩，ocr-208）。
        return None
    if not isinstance(data, dict):
        return None
    mid = data.get("milestone_id")
    if mid is None:
        return None
    from k3dge.engine.milestone_pointer import get_current_milestone

    # 快照必须属于**当前里程碑**：否则上一里程碑的 present/pending/预算会被当 fresh（ocr-044）。
    if mid != (milestone_id or get_current_milestone(workspace)):
        return None
    if data.get("tasks_hash") != _tasks_hash(workspace, mid):
        return None  # stale: task set changed
    return data


def ensure_checklist(workspace: Path, milestone_id: Optional[str] = None) -> dict:
    return read_checklist(workspace, milestone_id) or build_checklist(workspace, milestone_id)


def reset_for_audit(workspace: Path, milestone_id: Optional[str] = None) -> dict:
    """Called when an audit pass is initiated (manual `milestone audit` or auto):
    fresh snapshot + verify budget reset + stamp started_at."""
    from k3dge.engine.milestone_pointer import get_current_milestone

    mid = milestone_id or get_current_milestone(workspace)
    data = build_checklist(workspace, mid)
    data["verify_attempts"] = 0
    data["audit_started_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    _write(workspace, data)
    return data


def get_verify_attempts(workspace: Path, milestone_id: Optional[str] = None) -> int:
    return _coerce_attempts(ensure_checklist(workspace, milestone_id).get("verify_attempts", 0))


def bump_verify_attempt(workspace: Path, milestone_id: Optional[str] = None) -> int:
    # 计数器 read-modify-write 在并发调用下会丢增量（ocr2-204）：尽力拿进程间锁串行化；
    # 拿不到锁（无 fcntl/Windows）时仍按旧路径走（预算可能少计，但不崩）。
    from contextlib import contextmanager

    @contextmanager
    def _locked():
        try:
            import fcntl

            _lp = _path(workspace).with_name(_path(workspace).name + ".lock")
            with open(_lp, "a+b") as _lf:
                fcntl.flock(_lf.fileno(), fcntl.LOCK_EX)
                yield
        except (ImportError, OSError):
            yield

    with _locked():
        data = ensure_checklist(workspace, milestone_id)
        data["verify_attempts"] = _coerce_attempts(data.get("verify_attempts", 0)) + 1
        _write(workspace, data)
        return int(data["verify_attempts"])


def reset_verify_attempts(workspace: Path, milestone_id: Optional[str] = None) -> None:
    data = ensure_checklist(workspace, milestone_id)
    data["verify_attempts"] = 0
    _write(workspace, data)


def _write(workspace: Path, data: dict) -> None:
    import os
    import tempfile

    p = _path(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    # 原子写：半截 JSON 会被 read_checklist 当"文件不存在"⇒ 状态/预算静默归零（ocr-209）。
    # 固定名 `.tmp` 在并发调用下互抢（先 replace 者搬走文件，后者 FileNotFoundError，ocr2-204）⇒
    # 唯一临时名。
    fd, name = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        Path(name).replace(p)
    except BaseException:
        try:
            Path(name).unlink(missing_ok=True)
        except OSError:
            pass
        raise
