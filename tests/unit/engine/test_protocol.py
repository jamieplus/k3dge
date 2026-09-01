from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from k3dge.engine.protocol import write_incident


class TestWriteIncident(unittest.TestCase):
    def test_write_incident_creates_human_visible_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text("{}")
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
            (root / ".agent" / "manifest.json").write_text("{}")
            write_incident(root, target="x.md", task_type="audit", task_id="T1", detail="boom")
            TestIncidentGovernance()._schema(root)
            vs = validate_docs(root, types=["incidents"])
            self.assertEqual(vs, [], [f"{v.rule_id}: {v.message}" for v in vs])


if __name__ == "__main__":
    unittest.main()
