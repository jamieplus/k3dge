"""CHANGELOG 生成：**提交区间**（封版时一次生成）——不再是每张票 done 各写一行。

ADR-0004 §2.1.12（🅰1）：来源＝`<上一里程碑 tag>..HEAD` 的**非机械提交**，类型取
conventional 前缀；闸只验**不漏项**，写得好归人。理由：提交**不可漏**（每次改动必有提交），
票可漏（没开票也能改）；且区间由边界 tag 界定，"发布说明收哪一段"不再靠"谁记得写"。

`_append_to_unreleased` 保留为**降级路径**（首个里程碑尚无上一个 tag 时用），不再由
`task done` 调用（那正是双写的来源）。
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


# ── 提交区间 → 版本段条目（ADR-0004 §2.1.12）──────────────────────────────
#: conventional 提交前缀 → Keep a Changelog 小节（与 `version._CT_MAP` 同口径；多取几个前缀
#: 是为了"提交闸允许的类型"都能落进某节，不被静默丢掉）。
_RANGE_TYPES = {
    "feat": "Added", "add": "Added",
    "fix": "Fixed", "audit": "Fixed", "perf": "Fixed", "sec": "Security",
    "docs": "Changed", "refactor": "Changed", "chore": "Changed",
    "style": "Changed", "build": "Changed", "ci": "Changed", "test": "Changed",
    "revert": "Removed", "remove": "Removed", "deprecate": "Deprecated",
}
_SUBJECT_RE = re.compile(r"^([a-z]+)(?:\([^)]*\))?!?:\s*(.+)$", re.IGNORECASE)
_TRAILER_SEAL = "seal-milestone"


def _tag_number(tag: str) -> tuple:
    """里程碑 tag 的排序键：先按数字、再按原串（`M10` > `M9`；非数字 id 退化为字典序）。"""
    digits = re.findall(r"\d+", tag)
    return (int(digits[-1]) if digits else -1, tag)


def _git(workspace: Path, *args: str) -> str:
    import subprocess

    try:
        r = subprocess.run(["git", "-C", str(workspace), *args], capture_output=True, text=True)
    except OSError:
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def mechanical_commit(sha: str, subject: str, body: str) -> bool:
    """**机器造的**提交（不该进 CHANGELOG，也不算"漏项"）：

    - `round work <job>`：`worktree.advance` 的进程提交（审计线现场）
    - 带 `Seal-milestone:` trailer：封版提交（归档/提版/收摊，不是人的工作内容）

    注意**不包含**"subject 不是 conventional"那种：那种要进 `uncovered`（**漏项信号**），
    静默滤掉等于把"没写清类型的提交"变成看不见——那正是本票要治的病。
    """
    if subject.startswith("round work ") or subject.startswith("round work\t"):
        return True
    return f"{_TRAILER_SEAL}:" in (body or "").lower()


def build_notes_from_range(workspace: Path, previous_tag: str = "") -> tuple:
    """`<previous_tag>..HEAD` 的非机械提交 → `(notes, uncovered)`。

    `previous_tag` 为空时自动取**编号最大且是 HEAD 祖先**的里程碑 tag（排除 HEAD 自身所在
    的封版提交）；找不到 ⇒ `("", [])`（首个里程碑：调用方回落 `consume_unreleased`）。
    `uncovered` 是"解析不出类型"的提交 subject（供告警；正常应被 `mechanical_commit` 过滤）。
    """
    from k3dge.engine.milestone_files import milestone_tags

    if not previous_tag:
        import subprocess

        cands = []
        for tag in milestone_tags(workspace):
            r = subprocess.run(["git", "-C", str(workspace), "merge-base", "--is-ancestor",
                                tag, "HEAD"], capture_output=True, text=True)
            if r.returncode == 0:      # 只认是 HEAD 祖先的边界（别的分支的 tag 不算）
                cands.append(tag)
        if not cands:
            return "", []
        previous_tag = max(cands, key=_tag_number)
    raw = _git(workspace, "log", "--no-merges", "--format=%H%x1f%s%x1f%b%x1e",
               f"{previous_tag}..HEAD")
    by_section: dict = {}
    uncovered: list = []
    for rec in raw.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        parts = rec.split("\x1f")
        sha, subject = parts[0], (parts[1] if len(parts) > 1 else "")
        body = parts[2] if len(parts) > 2 else ""
        if mechanical_commit(sha, subject, body):
            continue
        m = _SUBJECT_RE.match(subject)
        if not m:
            uncovered.append(subject)
            continue
        kind = m.group(1).lower()
        text = m.group(2).strip()
        section = _RANGE_TYPES.get(kind)
        if section is None:
            uncovered.append(subject)
            continue
        by_section.setdefault(section, []).append(text)
    lines = []
    for section in ("Added", "Changed", "Fixed", "Deprecated", "Removed", "Security"):
        items = by_section.get(section)
        if not items:
            continue
        lines.append(f"### {section}")
        lines.extend(f"- {item}" for item in items)
        lines.append("")
    return "\n".join(lines).rstrip("\n"), uncovered
