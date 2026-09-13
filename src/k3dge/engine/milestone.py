"""Compatibility facade — `engine.milestone` re-exports the decomposed modules (A-1).

The original god-module (`milestone.py`, ~1700 lines, 6+ concerns) was split into:
  prompt / milestone_pointer / milestone_files / audit_report / doc_audit /
  review_archive / task_index / changelog / task_write / align / seal / seal_flow /
  milestone_audit
Every name below was previously defined here; callers keep importing from `engine.milestone`.
"""
from __future__ import annotations

from k3dge.engine.align import (
    _ALIGN_STUB_MARKER,
    _align_pass_marker,
    run_milestone_alignment,
)
from k3dge.engine.audit_report import (
    _AUDIT_HEADER,
    _QUALITY_MARKER_RE,
    _find_audit_report,
    _find_report,
    _parse_audit_stats,
    _report_kind,
)
from k3dge.engine.changelog import (
    _append_to_unreleased,
    _changelog_draft_path,
)
from k3dge.engine.doc_audit import (
    _attach_k3che_hints,
    _changed_docs,
    _ensure_doc_audit_task,
    _new_archive_without_note,
    _related_doc_hints,
    _similar_task_hints,
    run_doc_audit,
)
from k3dge.engine.milestone_audit import (
    _audit_mode,
    _ensure_leftovers,
    _ratchet_audit_step,
    persist_external_audit_report,
    run_audit_flow,
    scan_pending_findings,
)
from k3dge.engine.milestone_files import (
    _DOC_AUX_NAMES,
    _FILENAME_MILESTONE_RE,
    _REVIEW_AUX,
    _filename_milestone,
    _has_milestone_token,
    _is_doc_aux,
    _is_review_aux,
)
from k3dge.engine.milestone_pointer import (
    _SAFE_MILESTONE_ID_RE,
    _validate_milestone_id,
    bump_milestone,
    get_current_milestone,
    set_current_milestone,
)
from k3dge.engine.prompt import Prompt as _Prompt
from k3dge.engine.review_archive import (
    _living_review_files,
    _reviews_to_archive,
    _rewrite_leftover_links,
    _safe_archive_dir,
)
from k3dge.engine.seal import (
    GUIDE_STUB_RE,
    _seal_archive,
    _seal_review_gate,
    seal_milestone,
    seal_preconditions_error,
    scan_unfilled_guides,
)
from k3dge.engine.seal_flow import (
    _align_review_path,
    _strip_align_stub,
    _write_closure_note,
    run_seal_flow,
)
from k3dge.engine.task_index import (
    _ALLOWED_STATUS,
    MILESTONE_RE,
    PRIORITY_RE,
    STATUS_RE,
    TITLE_RE,
    MilestoneTask,
    TaskIndex,
    list_tasks,
    parse_frontmatter,
    scan_milestone_tasks,
)
from k3dge.engine.task_write import (
    _append_task_changelog,
    _auto_backfill_reviews,
    _backfill_task_reviews,
    _finalize_task_done,
    _rename_task_done,
    _report_open_findings,
    _resolve_task_target,
    _task_report_pointer,
    create_task,
    mark_task_done,
)

__all__ = [
    "create_task", "mark_task_done", "list_tasks", "scan_milestone_tasks",
    "run_milestone_alignment", "run_seal_flow", "run_audit_flow", "run_doc_audit",
    "seal_milestone", "seal_preconditions_error", "scan_unfilled_guides",
    "persist_external_audit_report", "scan_pending_findings",
    "get_current_milestone", "set_current_milestone", "bump_milestone",
    "parse_frontmatter", "MilestoneTask", "TaskIndex",
]
