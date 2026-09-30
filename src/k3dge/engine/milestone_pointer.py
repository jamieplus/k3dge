"""Milestone cursor + id validation."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

_SAFE_MILESTONE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class MilestoneError(ValueError):
    """游标损坏/不可读——**不得**静默回退成 M0（那会把真实游标永久改写，ocr-086）。"""


def _milestone_file(workspace: Path) -> Path:
    return workspace / ".agent" / "milestone"


def get_current_milestone(workspace: Path) -> str:
    """Current milestone cursor, default M0（**仅当文件不存在**）；损坏/不可读 ⇒ 抛错。

    旧行为把"文件不存在""内容非法/非 UTF-8""读取 OSError"三种情况都折成 M0 ⇒ `bump_milestone`
    以 M0 为基数把真实游标（如 M10）永久改成 M1，历史归档对不上（ocr-086）。
    """
    p = _milestone_file(workspace)
    if not p.is_file():
        return "M0"
    try:
        v = p.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise MilestoneError(f"{p} 存在但不可读：{exc}") from exc
    if not v:
        raise MilestoneError(f"{p} 为空（游标损坏）——请人工修复，勿当 M0")
    if not _SAFE_MILESTONE_ID_RE.fullmatch(v):
        raise MilestoneError(f"{p} 内容非法（{v!r}）——请人工修复，勿当 M0")
    return v


def set_current_milestone(workspace: Path, milestone_id: str) -> None:
    err = _validate_milestone_id(milestone_id)
    if err:
        raise ValueError(err)
    p = _milestone_file(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    # 原子写：游标留下半行（`M1`→`M`）会让下次读走"内容非法"分支，与 bump 的读-改-写
    # 叠加成不可恢复的回退（ocr-270）。
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(milestone_id + "\n", encoding="utf-8")
    tmp.replace(p)


def bump_milestone(workspace: Path) -> str:
    """M0 → M1 → M2 …; writes new cursor and returns it."""
    cur = get_current_milestone(workspace)
    m = re.match(r"^M(\d+)$", cur)
    if not m:
        # 不再生成 `-next` 链（可无界增长、且脱离 M<数字> 契约让扫描恒空，ocr-087）。
        raise MilestoneError(f"游标 '{cur}' 非 M<数字> 形态，拒绝推进（请人工修正游标）")
    nxt = f"M{int(m.group(1)) + 1}"
    set_current_milestone(workspace, nxt)
    return nxt


def _validate_milestone_id(milestone_id: str) -> Optional[str]:
    """Return an error message if `milestone_id` is unsafe as a path component."""
    if milestone_id and ".." in Path(str(milestone_id)).parts:
        return f"Invalid milestone id '{milestone_id}': 不得含 '..'（它是路径分量）"
    if not milestone_id or not _SAFE_MILESTONE_ID_RE.fullmatch(milestone_id):
        return (
            f"Invalid milestone id '{milestone_id}': use a letter/digit start, "
            "then letters, digits, '.', '_' or '-' only (no path separators)."
        )
    return None
