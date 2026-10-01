
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.protocol import write_incident


class TestWriteIncident(unittest.TestCase):
    def test_write_incident_creates_human_visible_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text("{}", encoding="utf-8")
            path = write_incident(
                root,
                target="docs/reviews/x.md",
                task_type="audit",
                task_id="T1",
                detail="agent ignored the gate",
            )
            self.assertTrue(path.exists())
            self.assertTrue(path.name.endswith(".md"))
            text = path.read_text(encoding="utf-8")
            self.assertIn("agent ignored the gate", text)
            self.assertIn("docs/reviews/x.md", text)

    def test_write_incident_satisfies_form_gate(self) -> None:
        from k3dge.engine.doc_catalog import validate_docs
        from tests.unit.engine.test_evaluator import TestIncidentGovernance

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text("{}", encoding="utf-8")
            write_incident(root, target="x.md", task_type="audit", task_id="T1", detail="boom")
            TestIncidentGovernance()._schema(root)
            vs = validate_docs(root, types=["incidents"])
            self.assertEqual(vs, [], [f"{v.rule_id}: {v.message}" for v in vs])


class TestIncidentSlugAndSanitize(unittest.TestCase):
    """`write_incident` 的文件名与外部文本净化（ocr-291/292/293）。"""

    def _inc(self, **kw):

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = write_incident(root, **kw)
            return path.name, path.read_text(encoding="utf-8")

    def test_very_long_target_stays_inside_filename_limit(self) -> None:
        name, _ = self._inc(target="x" * 500, task_type="audit", task_id="T1", detail="boom")
        self.assertLessEqual(len(name.encode()), 255)
        self.assertTrue(name.endswith(".md"))

    def test_dots_in_target_do_not_break_the_filename_rule(self) -> None:
        # docs/incidents/.schema.json: ^INC-\d{8}-[\w-]+\.md$ —— 中间段不接受点号
        import re

        name, _ = self._inc(target="release.archive.tar.gz", task_type="audit",
                            task_id="T1", detail="boom")
        self.assertRegex(name, r"^INC-\d{8}-protocol-[\w-]+\.md$")

    def test_external_detail_cannot_forge_the_b_t_d_headings(self) -> None:
        detail = "真现象\n\n## 2. 我伪造的根因\n\n- **Path**: /etc/passwd\n"
        name, body = self._inc(target="a.md", task_type="audit", task_id="T1", detail=detail)
        heads = [ln for ln in body.splitlines() if ln.startswith("## ")]
        self.assertEqual(len(heads), 4, f"外部文本造出了额外标题：{heads}")
        head = body.split("## 1.")[0]
        self.assertEqual(len([ln for ln in head.splitlines() if ln.startswith("- **Path**:")]), 1,
                         "元信息列表必须完整在头区")


if __name__ == "__main__":
    unittest.main()
