"""测试件自身的两条不变量（OCR 测试扫描 t-247/265/292/318 的防退化）。"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
GUARD_RE = re.compile(r'^if __name__ == "__main__":', re.M)


def _defs(text: str) -> list:
    return [(m.start(), m.group(0)) for m in re.finditer(r"^(?:def |class )\w+", text, re.M)]


def test_main_guard_is_last_statement_in_every_test_file() -> None:
    """守卫必须落在文件末尾。

    放在中间时 `unittest.main()` 会 `sys.exit()`：它**之后**的类/函数连定义都没发生，
    直跑该文件的命令仍然报 `OK`（退出码 0）⇒ 半套测试静默消失，比红更糟。
    """
    offenders = []
    for p in sorted((REPO / "tests").rglob("*.py")):
        text = p.read_text(encoding="utf-8")
        m = GUARD_RE.search(text)
        if not m:
            continue
        tail = text[m.end():]
        late = [d for pos, d in _defs(tail)]
        if late:
            offenders.append(f"{p.relative_to(REPO)}: 守卫之后还有 {len(late)} 个定义（首个＝{late[0]}）")
    assert not offenders, "测试文件的 __main__ 守卫不在末尾：" + "; ".join(offenders)
