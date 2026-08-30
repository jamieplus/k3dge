import tempfile
import unittest
from pathlib import Path

from k3dge.engine import marker


class TestMarker(unittest.TestCase):
    def test_epoch_auto_generated_when_absent(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            epoch = marker.ensure_epoch(ws)
            self.assertEqual(len(epoch), 8)
            data = marker._read(ws)
            self.assertEqual(data["epoch_id"], epoch)
            self.assertTrue(SESSION_ID_RE_ok(data["session_id"]))

    def test_attendance_only_on_correct_answer(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            ok, epoch = marker.register_attendance(ws, "docs/x.md", answer="abc", expected="abc")
            self.assertTrue(ok)
            self.assertTrue(marker.is_attended(ws, "docs/x.md", epoch))
            # wrong answer: no record
            ok2, _ = marker.register_attendance(ws, "docs/y.md", answer="wrong", expected="right")
            self.assertFalse(ok2)
            self.assertFalse(marker.is_attended(ws, "docs/y.md", epoch))

    def test_session_reset_clears(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            marker.register_attendance(ws, "docs/x.md", answer="abc", expected="abc")
            marker.reset_session(ws)
            self.assertFalse((ws / ".agent" / "session.json").exists())

    def test_escape_path_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            with self.assertRaises(ValueError):
                marker.register_attendance(ws, "../escape.md", answer="a", expected="a")


def SESSION_ID_RE_ok(value: str) -> bool:
    import re

    return bool(re.match(r"^[A-Za-z0-9_-]{1,64}$", value))


if __name__ == "__main__":
    unittest.main()
