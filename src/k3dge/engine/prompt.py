"""Interactive prompter (extracted from `engine/milestone.py`, A-1 首块).

Tiny, dependency-free; testable via `answers` injection. `milestone` re-imports it as
`_Prompt` for back-compat with existing callers/tests.
"""
from __future__ import annotations


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

    def ask(self, question: str, *, countdown=None, default_yes=False) -> bool:
        default = "Y/n" if default_yes else "y/N"
        if countdown:
            suffix = f" [{default}, {countdown}s default {'Y' if default_yes else 'N'}]"
        else:
            suffix = f" [{default}]"
        self._write(question + suffix + ": ")
        if self.answers is not None:
            ans = (
                self.answers[self._ai]
                if self._ai < len(self.answers)
                else ("y" if default_yes else "n")
            )
            self._ai += 1
            return str(ans).strip().lower() in ("y", "yes")
        if not self.isatty():
            return default_yes
        try:
            if countdown:
                import select

                rlist, _, _ = select.select([self.in_stream], [], [], countdown)
                if not rlist:
                    self._write(("Y" if default_yes else "N") + "\n")
                    return default_yes
                ans = self.in_stream.readline().strip().lower()
            else:
                ans = self.in_stream.readline().strip().lower()
        except (EOFError, OSError):
            return default_yes
        return ans in ("y", "yes")
