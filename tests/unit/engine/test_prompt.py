"""`Prompt.ask` 的两条边界：`countdown=0` 是有效值、读输入失败不得当作确认（ocr-289/290）。"""

import contextlib
import io
import os
import unittest
from unittest import mock

from k3dge.engine.prompt import Prompt


class _TtyPipe:
    """真实 fd（isatty 谎报 True 的管道）：让 `select.select([...], [], 0)` 真能被调。"""

    def __init__(self, f) -> None:
        self._f = f

    def isatty(self) -> bool:
        return True

    def fileno(self) -> int:
        return self._f.fileno()

    def readline(self) -> str:
        return self._f.readline()


class TestCountdownZero(unittest.TestCase):
    def test_zero_countdown_takes_default_instead_of_blocking(self) -> None:
        # 旧实现 `if countdown:` ⇒ 0 被当"没设"，走阻塞 readline；空流上 select 也救不了
        #
        # （t-224）旧夹具是 `io.StringIO()`：isatty()==False ⇒ `ask` 第一步就回退默认，
        # countdown 支路**从没进**——`"0s default Y"` 只证明后缀写了。换"写入端敞着、
        # 无数据"的真实 fd：select(timeout=0) 立即返回空 ⇒ 只有倒计时超时支路会回显 "Y"。
        r_fd, w_fd = os.pipe()
        try:
            in_stream = _TtyPipe(os.fdopen(r_fd, "r", encoding="utf-8"))
            buf = io.StringIO()
            p = Prompt(in_stream=in_stream, out_stream=buf)
            self.assertTrue(p.ask("封板?", countdown=0, default_yes=True))
            out = buf.getvalue()
            self.assertIn("0s default Y", out)
            self.assertTrue(out.endswith("Y\n"), f"超时支路的回显缺失（走了别的路径？）：{out!r}")
        finally:
            os.close(w_fd)

    def test_none_countdown_still_prints_plain_hint(self) -> None:
        class Tty(io.StringIO):
            def isatty(self) -> bool:
                return True

        buf = io.StringIO()
        p = Prompt(in_stream=Tty("y\n"), out_stream=buf)
        self.assertTrue(p.ask("q", countdown=None, default_yes=False))
        self.assertIn("[y/N]", buf.getvalue())


class _Boom:
    """tty 形状、带答案的输入流。

    **失败源只有一个**（t-225）：`Prompt.ask` 调的是模块级 `select.select(...)`，从不
    `self.in_stream.select(...)`——旧类上那个 select 方法永不被告知的"死夹具"，让读者
    以为失败来自流。OSError 由 patch 进 sys.modules 的假 select 抛（见用它的测）。
    """

    def isatty(self) -> bool:
        return True

    def readline(self) -> str:
        return "y\n"


class TestReadFailureIsNotConfirmation(unittest.TestCase):
    def test_oserror_fails_closed_and_is_loud(self) -> None:
        """（t-226）换 `patch.dict(sys.modules, {"select": …})`。

        旧形状整进程替换 `builtins.__import__`：①只覆盖**函数内** `import select`——哪天
        hoist 到模块级就静默 no-op，而真 select 在无句柄对象上碰巧也抛 OSError，
        假通过与真通过不可分辨；②全局机制在并发/惰性导入窗口里不安全。sys.modules
        置换有作用域、可还原，模块级与函数级两条 import 路径同样被截。
        """
        import sys

        class _S:
            @staticmethod
            def select(*args, **kwargs):
                raise OSError("not supported on this platform")

        err = io.StringIO()
        with mock.patch.dict(sys.modules, {"select": _S}):
            p = Prompt(in_stream=_Boom(), out_stream=io.StringIO())
            with contextlib.redirect_stderr(err):
                ans = p.ask("封板?", countdown=5, default_yes=True)
        self.assertFalse(ans, "读输入失败被兜成 default_yes ⇒ 通道坏了仍判'确认'")
        # 判别"是被截的 select 抛的"而非真 select 顺手抛（t-226 的假两难）：
        # WARN 消息里必须带着 _S 的专属错文。
        self.assertIn("WARN", err.getvalue())
        self.assertIn("not supported on this platform", err.getvalue())


if __name__ == "__main__":
    unittest.main()
