"""`Prompt.ask` 的两条边界：`countdown=0` 是有效值、读输入失败不得当作确认（ocr-289/290）。"""
from __future__ import annotations

import io
import unittest

from k3dge.engine.prompt import Prompt


class TestCountdownZero(unittest.TestCase):
    def test_zero_countdown_takes_default_instead_of_blocking(self) -> None:
        # 旧实现 `if countdown:` ⇒ 0 被当"没设"，走阻塞 readline；空流上 select 也救不了
        buf = io.StringIO()
        p = Prompt(in_stream=io.StringIO(), out_stream=buf)
        self.assertTrue(p.ask("封板?", countdown=0, default_yes=True))
        self.assertIn("0s default Y", buf.getvalue())

    def test_none_countdown_still_prints_plain_hint(self) -> None:
        class Tty(io.StringIO):
            def isatty(self) -> bool:
                return True

        buf = io.StringIO()
        p = Prompt(in_stream=Tty("y\n"), out_stream=buf)
        self.assertTrue(p.ask("q", countdown=None, default_yes=False))
        self.assertIn("[y/N]", buf.getvalue())


class _Boom:
    """`select` 在不支持普通句柄的平台上抛 OSError（Windows 即如此）。"""

    def isatty(self) -> bool:
        return True

    def select(self, *a, **k):
        raise OSError("Wenot supported")

    def readline(self) -> str:
        return "y\n"


class TestReadFailureIsNotConfirmation(unittest.TestCase):
    def test_oserror_fails_closed_and_is_loud(self) -> None:
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "select":
                class _S:
                    @staticmethod
                    def select(*args, **kwargs):
                        raise OSError("not supported on this platform")
                return _S
            return real_import(name, *a, **k)

        err = io.StringIO()
        builtins.__import__ = fake_import
        try:
            p = Prompt(in_stream=_Boom(), out_stream=io.StringIO())
            with __import__("contextlib").redirect_stderr(err):
                ans = p.ask("封板?", countdown=5, default_yes=True)
        finally:
            builtins.__import__ = real_import
        self.assertFalse(ans, "读输入失败被兜成 default_yes ⇒ 通道坏了仍判'确认'")
        self.assertIn("WARN", err.getvalue())


if __name__ == "__main__":
    unittest.main()
