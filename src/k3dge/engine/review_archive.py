"""Review/archive 机械（reviews 归档选择 + 安全归档目录），extracted from `engine/milestone.py` (A-1 第六块).

纯文件机械、无判定。
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from k3dge.engine.milestone_files import (
    _filename_milestone,
    _has_milestone_token,
    _is_review_aux,
)


def _living_review_files(reviews_dir: Path) -> List[Path]:
    if not reviews_dir.is_dir():
        return []
    return sorted(
        f for f in reviews_dir.iterdir() if f.is_file() and f.suffix == ".md" and not _is_review_aux(f.name)
    )


def _reviews_to_archive(reviews_dir: Path, milestone_id: str, pass_mark: str) -> List[Path]:
    """Living reports for this milestone: filename token, or align-pass marker in body.

    Files named for another milestone stay at top-level.
    """
    out: List[Path] = []
    for path in _living_review_files(reviews_dir):
        named = _filename_milestone(path.name)
        if named and named.lower() != milestone_id.lower():   # 同上：大小写不敏感（ocr-267）
            continue
        if _has_milestone_token(path.name, milestone_id):
            out.append(path)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if pass_mark in text:
            out.append(path)
    return out


def _rewrite_leftover_links(workspace: Path, filename: str, new_href: str) -> None:
    leftovers = workspace / "docs" / "reviews" / "LEFTOVERS.md"
    if not leftovers.is_file():
        return
    try:
        text = leftovers.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    updated = text.replace(f"]({filename})", f"]({new_href})")
    updated = updated.replace(f"](./{filename})", f"]({new_href})")
    if updated != text:
        leftovers.write_text(updated, encoding="utf-8")


def _safe_archive_dir(workspace: Path, kind: str, milestone_id: str) -> Tuple[Optional[Path], str]:
    """Return (dir, error). dir is None on path escape."""
    root = (workspace / "docs" / kind / "archive").resolve()
    dest = (root / milestone_id).resolve()
    try:
        dest.relative_to(root)
    except ValueError:
        return None, (
            f"Invalid milestone id '{milestone_id}': archive path escapes docs/{kind}/archive/"
        )
    return dest, ""
