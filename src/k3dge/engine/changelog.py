"""CHANGELOG `## [Unreleased]` 追加 + 草稿路径（task done 时），extracted from `engine/milestone.py`
(A-1 第八块). `milestone` re-exports for back-compat.
"""
from __future__ import annotations

import re
from pathlib import Path

from k3dge.engine.task_index import TITLE_RE


def _changelog_draft_path(workspace: Path) -> Path:
    return workspace / ".agent" / "changelog_draft.md"


def _append_to_unreleased(workspace: Path, task_path: Path) -> bool:
    """Append task's title to CHANGELOG.md ## [Unreleased] under the correct Keep a Changelog subsection.

    Returns True on success or no-op, False on failure (with stderr warning).
    """
    try:
        changelog = workspace / "CHANGELOG.md"
        if not changelog.is_file():
            return True
        content = task_path.read_text(encoding="utf-8") if task_path.is_file() else ""
        title_m = TITLE_RE.search(content)
        title = title_m.group(1).strip() if title_m else task_path.stem
        # Map task type to Keep a Changelog section
        type_m = re.search(r"docs/tasks/\d{4}-\d{2}-\d{2}-(?:M\d+-)?([a-z]+)-", str(task_path))
        task_type = type_m.group(1) if type_m else "fix"
        type_map = {"feat": "Added", "fix": "Fixed", "audit": "Fixed", "docs": "Changed", "chore": "Changed", "refactor": "Changed"}
        section = type_map.get(task_type, "Fixed")
        text = changelog.read_text(encoding="utf-8")
        unreleased = "## [Unreleased]"
        idx = text.find(unreleased)
        if idx == -1:
            return True
        next_idx = text.find("## [", idx + len(unreleased))
        unreleased_block = text[idx:next_idx] if next_idx != -1 else text[idx:]
        if title in unreleased_block:
            return True
        # Find or create the subsection header within Unreleased
        section_header = f"### {section}"
        sec_idx = text.find(section_header, idx, next_idx if next_idx != -1 else len(text))
        entry = f"- {title}\n"
        if sec_idx != -1:
            # Insert after the section header's next line
            header_end = text.find("\n", sec_idx) + 1
            # Find next section or next version
            next_sec = text.find("### ", header_end)
            next_ver = text.find("## [", header_end)
            insert_at = next_sec if next_sec != -1 and (next_ver == -1 or next_sec < next_ver) else next_ver
            if insert_at == -1 or (next_idx != -1 and insert_at > next_idx):
                insert_at = next_idx if next_idx != -1 else len(text)
            new_text = text[:insert_at] + entry + text[insert_at:]
        else:
            # Create new subsection after Unreleased header
            header_end = text.find("\n", idx) + 1
            if header_end == 0:
                header_end = idx + len(unreleased) + 1
            new_text = text[:header_end] + f"\n{section_header}\n{entry}" + text[header_end:]
        from k3dge.engine.version import _atomic_write

        _atomic_write(changelog, new_text)
        return True
    except Exception as exc:
        import sys

        print(f"[WARN] _append_to_unreleased failed for {task_path.name}: {exc}", file=sys.stderr)
        return False
