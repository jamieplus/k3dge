"""CHANGELOG `## [Unreleased]` 追加 + 草稿路径（task done 时）。

Extracted from `engine/milestone.py` (A-1 第八块).
"""
from __future__ import annotations

import re
from pathlib import Path

from k3dge.engine.task_index import TITLE_RE
from k3dge.engine.version import _CT_MAP

_UNRELEASED = "## [Unreleased]"
_TYPE_SECTION = _CT_MAP
_TYPE_RE = re.compile(r"docs/tasks/\d{4}-\d{2}-\d{2}-(?:M\d+-)?([a-z]+)-")


def _changelog_draft_path(workspace: Path) -> Path:
    return workspace / ".agent" / "changelog_draft.md"


def _title_and_section(task_path: Path) -> tuple[str, str]:
    """从 task 文件抽 title + 对应的 Keep a Changelog subsection 名。"""
    content = task_path.read_text(encoding="utf-8") if task_path.is_file() else ""
    m = TITLE_RE.search(content)
    title = m.group(1).strip() if m else task_path.stem
    tm = _TYPE_RE.search(str(task_path))
    return title, _TYPE_SECTION.get(tm.group(1) if tm else "fix", "Fixed")


def _insert_entry(text: str, idx: int, next_idx: int, section: str, entry: str) -> str:
    """在 Unreleased 段内插入条目，已有 `### <section>` 就尾插，否则在 Unreleased 后新建 subsection。"""
    header = f"### {section}"
    search_end = next_idx if next_idx != -1 else len(text)
    sec_idx = text.find(header, idx, search_end)
    if sec_idx != -1:
        # 已有 subsection：在 subsection 内找"下一 ### 或 ## ["作为插入点，不越 [Unreleased] 边界
        header_end = text.find("\n", sec_idx) + 1
        next_sec = text.find("### ", header_end)
        next_ver = text.find("## [", header_end)
        insert_at = next_sec if next_sec != -1 and (next_ver == -1 or next_sec < next_ver) else next_ver
        if insert_at == -1 or (next_idx != -1 and insert_at > next_idx):
            insert_at = next_idx if next_idx != -1 else len(text)
        return text[:insert_at] + entry + text[insert_at:]
    # 未有 subsection：在 [Unreleased] header 之后插入新 subsection
    header_end = text.find("\n", idx) + 1
    if header_end == 0:
        header_end = idx + len(_UNRELEASED) + 1
    return text[:header_end] + f"\n{header}\n{entry}" + text[header_end:]


def _append_to_unreleased(workspace: Path, task_path: Path) -> bool:
    """Append task's title to CHANGELOG.md ## [Unreleased] under the correct subsection.

    Returns True on success/no-op, False on failure（带 stderr 警告）。
    """
    try:
        changelog = workspace / "CHANGELOG.md"
        if not changelog.is_file():
            return True
        title, section = _title_and_section(task_path)
        text = changelog.read_text(encoding="utf-8")
        idx = text.find(_UNRELEASED)
        if idx == -1:
            return True
        next_idx = text.find("## [", idx + len(_UNRELEASED))
        block_end = next_idx if next_idx != -1 else len(text)
        if title in text[idx:block_end]:
            return True
        new_text = _insert_entry(text, idx, next_idx, section, f"- {title}\n")
        from k3dge.engine.version import _atomic_write

        _atomic_write(changelog, new_text)
        return True
    except Exception as exc:
        import sys

        print(f"[WARN] _append_to_unreleased failed for {task_path.name}: {exc}", file=sys.stderr)
        return False
