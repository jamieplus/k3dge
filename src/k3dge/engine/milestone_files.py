"""Milestone file-name / review-file helpers (extracted from `engine/milestone.py`, A-1 第三块).

Pure, low-coupling predicates/regexes.
"""
from __future__ import annotations

import re

# Docs that live inside a docs/<type>/ directory but are never content items:
# scaffolding/authoring files. Single source — task scanning and review scanning
# used to keep their own copies and drifted (AUTHORING.md leaked into `task list`).
_DOC_AUX_NAMES = frozenset({"README.md", "AUTHORING.md", "_template.md"})

_REVIEW_AUX = _DOC_AUX_NAMES | frozenset({"LEFTOVERS.md", "leftovers.md"})

_FILENAME_MILESTONE_RE = re.compile(r"(?:^|[._-])(M\d+)(?:[._-]|$)", re.IGNORECASE)


def _has_milestone_token(text: str, milestone_id: str) -> bool:
    """True iff `milestone_id` appears as a path/word token, not a substring of a longer id.

    `M1` must not match `M10` in filenames (`2026-08-23-M10-align.md`) or review body text.
    """
    if not milestone_id:
        return False
    return (
        re.search(
            rf"(?:^|[-_./\s]){re.escape(milestone_id)}(?:[-_./\s]|$)",
            text,
        )
        is not None
    )


def _is_doc_aux(name: str) -> bool:
    """True for structural files inside docs/<type>/ that are never items."""
    return name in _DOC_AUX_NAMES or name.startswith(".")


def _is_review_aux(name: str) -> bool:
    return name in _REVIEW_AUX or name.startswith(".")


def _filename_milestone(name: str) -> str | None:
    m = _FILENAME_MILESTONE_RE.search(name)
    return m.group(1) if m else None
