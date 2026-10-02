"""Milestone cursor + id validation."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

# 上限 64：id 是**路径分量**（archive/<id>、报告名），无上限时一个 5000 字符的游标
# 会一路拼进文件名（t-185）。真实形态（M1…M11）远在限内。
_SAFE_MILESTONE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


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
    try:
        p.lstat()
    except FileNotFoundError:
        return "M0"
    except OSError as exc:
        raise MilestoneError(f"{p} 无法 stat（{exc}）——请人工修复，勿当 M0") from exc
    if not p.is_file():
        # 存在但**不是普通文件**（目录/指目录的符号链接/FIFO）：`is_file()` 为假会走
        # "缺省 M0"，随后 bump 以 M0 为基数重写真实游标位——ocr-086 说的正是"不得静默回落"
        # （t-183：旧代码只挡了"内容坏"，没挡"形状坏"）。
        raise MilestoneError(f"{p} 存在但不是普通文件（目录/符号链接/FIFO？）——请人工修复，勿当 M0")
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
        # 游标失败一律 `MilestoneError`（公开错误类）：读侧/`bump` 都抛它，写侧曾抛裸
        # `ValueError`——`except MilestoneError` 的调用方恰恰接不住不安全 id（t-182）。
        # `MilestoneError ⊂ ValueError`，只按 ValueError 捕获的旧调用方不受影响。
        raise MilestoneError(err)
    p = _milestone_file(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    # 符号链接游标：rename 到链接位会替换链接本身、留下真实目标 stale（ocr2-491）。
    # 写穿目标，链接保持不动。
    dest = p.resolve() if p.is_symlink() else p
    dest.parent.mkdir(parents=True, exist_ok=True)
    # 原子写：游标留下半行（`M1`→`M`）会让下次读走"内容非法"分支，与 bump 的读-改-写
    # 叠加成不可恢复的回退（ocr-270）。
    # 固定 `.tmp` 名可预测：`.agent/` 可被同仓其他进程写时，预置同名 symlink 可把写带到别处
    # （CWE-59，ocr2-065）。用 `mkstemp`（O_EXCL 独占建，不跟随 symlink）再 replace。
    import os as _os
    import tempfile as _tf

    _fd, _name = _tf.mkstemp(dir=str(dest.parent), prefix=dest.name + ".", suffix=".tmp")
    try:
        with _os.fdopen(_fd, "w", encoding="utf-8") as _f:
            _f.write(milestone_id + "\n")
        Path(_name).replace(dest)
    except Exception:
        try:
            Path(_name).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _cursor_lock(workspace: Path):
    """Exclusive advisory lock around the cursor's read-modify-write.

    `bump_milestone` runs from the CLI, git hooks and the persistent MCP server
    against one workspace — two overlapping seals both read M10 and both write
    M11 (lost update). No fcntl (Windows) ⇒ no-op context manager.
    """
    import contextlib
    import os
    try:
        import fcntl
    except ImportError:  # pragma: no cover - non-POSIX
        fcntl = None

    @contextlib.contextmanager
    def _cm():
        fd = None
        if fcntl is not None:
            lock_path = _milestone_file(workspace).with_name("milestone.lock")
            try:
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
                fcntl.flock(fd, fcntl.LOCK_EX)
            except OSError:
                if fd is not None:
                    with contextlib.suppress(OSError):
                        os.close(fd)
                fd = None
        try:
            yield
        finally:
            if fd is not None:
                with contextlib.suppress(OSError):
                    os.close(fd)          # 关闭即释放
    return _cm()


def bump_milestone(workspace: Path) -> str:
    """M0 → M1 → M2 …; writes new cursor and returns it."""
    with _cursor_lock(workspace):
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
    if not isinstance(milestone_id, str):
        return (
            f"Invalid milestone id {milestone_id!r}: must be str, "
            "got non-string (MCP JSON-RPC/ frontmatter 不做类型校验， traceback 不得外泄）"
        )
    if milestone_id and ".." in Path(str(milestone_id)).parts:
        return f"Invalid milestone id '{milestone_id}': 不得含 '..'（它是路径分量）"
    if not milestone_id or not _SAFE_MILESTONE_ID_RE.fullmatch(milestone_id):
        return (
            f"Invalid milestone id '{milestone_id}': use a letter/digit start, "
            "then letters, digits, '.', '_' or '-' only (no path separators)."
        )
    return None
