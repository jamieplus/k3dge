"""Interactive prompter (extracted from `engine/milestone.py`, A-1 首块).

Tiny, dependency-free; testable via `answers` injection. `milestone` re-imports it as
`_Prompt` for back-compat with existing callers/tests.
"""
from __future__ import annotations


def _has_countdown(countdown) -> bool:
    """`countdown=0` 是**有效值**（"不等输入，立刻取默认"），真值判断会把它当"没设"⇒ 永久阻塞（ocr-289）。"""
    return countdown is not None


class Prompt:
    """Tiny interactive prompter; testable via `answers` injection."""

    def __init__(self, in_stream=None, out_stream=None, answers=None):
        self.in_stream = in_stream
        self.out_stream = out_stream
        self.answers = answers
        self._ai = 0

    @classmethod
    def default(cls) -> "Prompt":
        import sys

        return cls(sys.stdin, sys.stdout)

    def _write(self, s: str) -> None:
        if self.out_stream is not None:
            print(s, file=self.out_stream, end="", flush=True)

    def isatty(self) -> bool:
        if self.answers is not None:
            return False  # injected answers => deterministic, never block
        return bool(getattr(self.in_stream, "isatty", lambda: False)())

    def _parse(self, ans, default_yes: bool) -> bool:
        """注入答案与实时输入的**同一解析口径**：空输入＝采纳默认（ocr2-296）。

        旧注入分支 `str(ans) in ("y","yes")` 把"直接回车"恒判为否，与实时路径
        （line 81 空回车取默认）语义相反 ⇒ 测的是另一套逻辑。
        """
        s = str(ans).strip().lower()
        if not s:
            return default_yes
        return s in ("y", "yes")

    def ask(self, question: str, *, countdown=None, default_yes=False) -> bool:
        default = "Y/n" if default_yes else "y/N"
        if _has_countdown(countdown):
            suffix = f" [{default}, {countdown}s default {'Y' if default_yes else 'N'}]"
        else:
            suffix = f" [{default}]"
        self._write(question + suffix + ": ")
        if self.answers is not None:
            if self._ai >= len(self.answers):
                # 注入答案耗尽还继续"按默认走" ⇒ 问题数多于答案数的测试会**假通过**（451）
                import sys

                print(f"[PROMPT] WARN: 注入答案已用尽（第 {self._ai + 1} 问）⇒ 按默认 "
                      f"{'Y' if default_yes else 'N'} 继续；测试需补齐 answers", file=sys.stderr)
                ans = "y" if default_yes else "n"
            else:
                ans = self.answers[self._ai]
            self._ai += 1
            return self._parse(ans, default_yes)
        if not self.isatty():
            # 非交互通道自动取默认是**代用户作答**（ocr2-297）：必须出声，
            # 否则无人值守的封板/审计确认在日志里不留痕。
            import sys

            print(f"[PROMPT] WARN: 非交互输入 ⇒ 按默认 {'Y' if default_yes else 'N'} "
                  f"回答：{question[:120]}", file=sys.stderr)
            return default_yes
        try:
            if _has_countdown(countdown):
                import select

                rlist, _, _ = select.select([self.in_stream], [], [], countdown)
                if not rlist:
                    self._write(("Y" if default_yes else "N") + "\n")
                    return default_yes
                ans = self.in_stream.readline().strip().lower()
            else:
                ans = self.in_stream.readline().strip().lower()
        except EOFError:
            return default_yes        # 输入流到头＝非交互，取提示里声明的默认
        except OSError as exc:
            # `select` 在不支持普通文件句柄的平台上抛 OSError：以前和 EOF 同一支兜底 ⇒
            # 交互通道坏了却按"确认"走（封板这类判据不能靠猜）。降级出声 + fail-closed（ocr-290）。
            import sys

            print(f"[PROMPT] WARN: 读取输入失败（{type(exc).__name__}: {exc}）⇒ 视为未确认",
                  file=sys.stderr)
            return False
        if not ans:
            return default_yes    # 空回车＝采纳提示里的默认（[Y/n] ⇒ True），与非 tty 路径一致（ocr-098）
        return ans in ("y", "yes")
