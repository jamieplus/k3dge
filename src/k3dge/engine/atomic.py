"""文本文件的**原子写**：同目录临时文件 + `os.replace`。

为何单列：`version` 与 `sync/generator` 都要"要么完整要么不动"——就地 `write_text` 先截断，
崩溃/断电/并发会把受管事实源（spec 接口块、`docs/generated/*`）留在半截状态（341）。
固定名临时文件也不行：并发写者共用同一个 `.x.tmp`，后来者的内容会被别人的 `replace` 搬走（336）。
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    import contextlib
    import stat

    path = Path(path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    # 继承目标 mode：`mkstemp` 以 0600 建档，`os.replace` 把源 inode 的 mode 带到目标上 ⇒
    # 不显式继承会把 0644 的受管事实源悄悄降成 0600。用目标现 mode；不存在时用 0666 & ~umask。
    try:
        want_mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        _umask = os.umask(0)
        os.umask(_umask)
        want_mode = 0o666 & ~_umask
    fd, name = tempfile.mkstemp(dir=str(parent), prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(name)
    try:
        # 直接用 mkstemp 返回的 fd 写：关掉再按名重开会丢掉独占创建的保护窗口
        # （两条指令之间可被换成符号链接 ⇒ write_text 跟随截断任意文件）。
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            f.write(text)
        os.chmod(tmp, want_mode)
        # 光 `rename` 只保证原子性，不保证落盘：page cache 里的数据 + 延迟分配下，
        # rename 的元数据可先于数据块持久化 ⇒ 断电丢数据（ocr2-034）。先 fsync 文件，
        # rename 后再 fsync 目录（目录项落盘），才是崩溃安全的原子写。
        with open(tmp, "rb") as _f:
            os.fsync(_f.fileno())
        tmp.replace(path)
        try:
            _dfd = os.open(str(parent), os.O_RDONLY)
            try:
                os.fsync(_dfd)
            finally:
                os.close(_dfd)
        except OSError:
            pass
    except BaseException:
        # `except Exception` 接不住 KeyboardInterrupt/SystemExit/CancelledError ⇒
        # Ctrl-C 后 `.spec.md.*.tmp` 永久躺在受管目录里污染 git 快照；放 BaseException。
        # 清理尽力而为：unlink 自身失败不得覆盖原始写失败。
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        raise
