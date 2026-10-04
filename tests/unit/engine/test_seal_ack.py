"""审计确认（硬闸，主观）+ 封板增量（ADR-0004 §2.1.14）。

确认记本地、不防伪造、不限类型；增量排除审计自身 + 引用封版 hash；未确认给三出路提醒。
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from k3dge.engine import seal_ack


def _git(ws: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(ws), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{(r.stderr or r.stdout).strip()}")
    return r.stdout


def _repo(files=("a.txt",), _tc=None):
    ws = Path(tempfile.mkdtemp()).resolve()
    if _tc is not None:
        _tc.addCleanup(shutil.rmtree, ws, ignore_errors=True)
    (ws / ".agent").mkdir(parents=True)
    _git(ws, "init", "-q")
    _git(ws, "config", "user.email", "t@t.com")
    _git(ws, "config", "user.name", "t")
    for f in files:
        (ws / f).write_text("x\n", encoding="utf-8")
    _git(ws, "add", "-A")
    _git(ws, "commit", "-qm", "init")
    return ws


def _head(ws: Path) -> str:
    return _git(ws, "rev-parse", "HEAD").strip()


def _commit(ws: Path, name: str, msg: str) -> str:
    (ws / name).write_text("y\n", encoding="utf-8")
    _git(ws, "add", "-A")
    _git(ws, "commit", "-qm", msg)
    return _head(ws)


class TestSealAck(unittest.TestCase):
    def setUp(self):
        self.ws = _repo(_tc=self)
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        prev = os.environ.get("GIT_CEILING_DIRECTORIES")
        os.environ["GIT_CEILING_DIRECTORIES"] = str(self.ws.parent)

        def _restore():
            if prev is None:
                os.environ.pop("GIT_CEILING_DIRECTORIES", None)
            else:
                os.environ["GIT_CEILING_DIRECTORIES"] = prev

        self.addCleanup(_restore)

    def test_no_ack_is_unconfirmed(self):
        ok, reason, incr = seal_ack.audit_confirmed(self.ws, "M1", _head(self.ws))
        self.assertFalse(ok)
        self.assertIn("未确认", reason)
        self.assertEqual(incr, [])

    def test_ack_at_head_is_confirmed(self):
        h = _head(self.ws)
        seal_ack.save_ack(self.ws, "M1", h)
        ok, reason, incr = seal_ack.audit_confirmed(self.ws, "M1", h)
        self.assertTrue(ok, reason)
        self.assertEqual(incr, [])
        # 账落盘且可重读
        self.assertEqual(seal_ack.load_ack(self.ws)["M1"]["baseline"], h)

    def test_covered_only_changes_keep_confirmation(self):
        h0 = _head(self.ws)
        seal_ack.save_ack(self.ws, "M1", h0)
        # 引用封版 hash 的提交 ⇒ 豁免，不算增量
        _commit(self.ws, "b.txt", f"docs: follow-up\n\nAudit-covered: {h0}")
        ok, _, incr = seal_ack.audit_confirmed(self.ws, "M1", _head(self.ws))
        self.assertTrue(ok, incr)
        self.assertEqual(incr, [])

    def test_genuine_update_breaks_confirmation(self):
        h0 = _head(self.ws)
        seal_ack.save_ack(self.ws, "M1", h0)
        _commit(self.ws, "b.txt", "feat: real change")
        ok, reason, incr = seal_ack.audit_confirmed(self.ws, "M1", _head(self.ws))
        self.assertFalse(ok)
        self.assertIn("真更新", reason)
        self.assertEqual(len(incr), 1)
        self.assertIn("feat: real change", incr[0])

    def test_audit_own_commits_are_excluded(self):
        h0 = _head(self.ws)
        seal_ack.save_ack(self.ws, "M1", h0)
        _commit(self.ws, "b.txt", "chore(seal): seal milestone M1\n\nAudit-baseline: abc\nSeal-milestone: M1")
        ok, _, incr = seal_ack.audit_confirmed(self.ws, "M1", _head(self.ws))
        self.assertTrue(ok, incr)

    def test_reminder_has_three_ways_and_freeze_warning(self):
        msg = seal_ack.format_reminder(self.ws, "M1", ["abc123 feat: x"], "HEAD00")
        self.assertIn("k3dge milestone audit M1", msg)
        self.assertIn("--confirm-audit", msg)
        self.assertIn("不要再改源码", msg)
        self.assertIn("abc123", msg)

    def test_ack_is_gitignored_projection(self):
        import subprocess as _sp

        repo = Path(__file__).resolve().parents[3]
        for rel in (".agent/seal_ack.json",):
            r = _sp.run(["git", "-C", str(repo), "check-ignore", "-q", "--", rel],
                        capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{rel} 未被 .gitignore 覆盖")


if __name__ == "__main__":
    unittest.main()
