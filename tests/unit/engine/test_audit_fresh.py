"""`audit_fresh` 前置闸：闭环报告的基线必须覆盖当前内容（#2）。

病灶：`audit_closed` 只问"有没有该里程碑的报告且待修=0"，不比对内容 —— 实测本仓 M10 的
报告基线 `0cb1b42` 之后 188 处改动照样"闭环"。锚点用报告里的 `- **基线**: <sha>`
（durable，随报告入库；`.agent/audit_jobs.json` 是 gitignored 本地状态，不能作判据）。
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase

from k3dge.engine.seal import _audit_fresh_error

_ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
_HEADER = ("| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")


class TestAuditFresh(TestCase):
    def _git(self, ws: Path, *args: str) -> str:
        r = subprocess.run(["git", "-C", str(ws), *args], check=True, capture_output=True, text=True, env=_ENV)
        return r.stdout.strip()

    def _commit(self, ws: Path, rel: str, body: str, msg: str = "c") -> str:
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        self._git(ws, "add", "-A")
        self._git(ws, "commit", "-qm", msg)
        return self._git(ws, "rev-parse", "HEAD")

    def _ws(self) -> Path:
        ws = Path(tempfile.mkdtemp())
        self._git(ws, "init", "-qb", "main")
        return ws

    def _report(self, ws: Path, base: str, mid: str = "M10") -> None:
        d = ws / "docs" / "reviews"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"2026-09-13-{mid}-audit.md").write_text(
            f"# 审计：src（milestone {mid}）\n\n- **基线**: {base}\n"
            "- **审计人**: k3dit\n- **透镜来源**: k3dit 工单\n\n" + _HEADER,
            encoding="utf-8")

    def test_fresh_when_nothing_changed_since_baseline(self):
        ws = self._ws()
        base = self._commit(ws, "src/a.py", "x = 1\n")
        self._report(ws, base)
        self.assertIsNone(_audit_fresh_error(ws, "M10"))

    def test_stale_after_src_change(self):
        ws = self._ws()
        base = self._commit(ws, "src/a.py", "x = 1\n")
        self._report(ws, base)
        self._commit(ws, "src/a.py", "x = 2\n")
        err = _audit_fresh_error(ws, "M10")
        self.assertIsNotNone(err)
        self.assertIn("审计已过期", err)
        self.assertIn("src/a.py", err)

    def test_stale_after_task_change(self):
        """用户裁定：`docs/tasks/**`（票状态变化）**算**未审改动——票是里程碑的事实源。"""
        ws = self._ws()
        base = self._commit(ws, "src/a.py", "x = 1\n")
        self._report(ws, base)
        self._commit(ws, "docs/tasks/2026-09-19-M10-fix-x.done.md", "# x\n")
        err = _audit_fresh_error(ws, "M10")
        self.assertIsNotNone(err)
        self.assertIn("docs/tasks/", err)

    def test_review_and_agent_paths_are_ignored(self):
        """豁免面：`docs/reviews/`（审计自家产物，否则报告一落地就算未审改动）+ `.agent/`（隐藏配置）。"""
        ws = self._ws()
        base = self._commit(ws, "src/a.py", "x = 1\n")
        self._report(ws, base)
        self._commit(ws, "docs/reviews/2026-09-14-other.md", "# other\n")
        self._commit(ws, ".agent/pipeline.toml", "[x]\n")
        self.assertIsNone(_audit_fresh_error(ws, "M10"))

    def test_non_ancestor_baseline_rejected(self):
        ws = self._ws()
        self._commit(ws, "src/a.py", "x = 1\n")
        self._git(ws, "checkout", "-qb", "side")
        side = self._commit(ws, "src/side.py", "y = 1\n")
        self._git(ws, "checkout", "-q", "main")
        self._report(ws, self._commit(ws, "src/b.py", "z = 1\n"), "M10")
        (ws / "docs" / "reviews" / "2026-09-13-M10-audit.md").write_text(
            f"# 审计：src（milestone M10）\n\n- **基线**: {side}\n- **审计人**: k3dit\n"
            "- **透镜来源**: k3dit 工单\n\n" + _HEADER, encoding="utf-8")
        err = _audit_fresh_error(ws, "M10")
        self.assertIsNotNone(err)
        self.assertIn("不是 HEAD 的祖先", err)

    def test_unresolvable_baseline_rejected(self):
        ws = self._ws()
        self._commit(ws, "src/a.py", "x = 1\n")
        self._report(ws, "deadbeef" * 5)
        err = _audit_fresh_error(ws, "M10")
        self.assertIsNotNone(err)
        self.assertIn("不可解析", err)

    def test_missing_report(self):
        ws = self._ws()
        self._commit(ws, "src/a.py", "x = 1\n")
        err = _audit_fresh_error(ws, "M10")
        self.assertIsNotNone(err)
        self.assertIn("无 12 列报告", err)

    def test_ignore_list_is_declared_and_overridable(self):
        """豁免面在声明面（`[checks.audit].fresh_ignore`）⇒ 下游可加自己的派生态。"""
        from k3dge.engine import gates

        ws = self._ws()
        self._commit(ws, "src/a.py", "x = 1\n")
        self.assertIn("docs/reviews/",
                      gates.load(ws).get("checks", {}).get("audit", {}).get("fresh_ignore"))
