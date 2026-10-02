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
    path = Path(path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=str(parent), prefix=f".{path.name}.", suffix=".tmp")
    os.close(fd)
    tmp = Path(name)
    try:
        tmp.write_text(text, encoding=encoding)
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
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
