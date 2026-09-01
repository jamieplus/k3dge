from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.doc_catalog import (
    analyze_adr_coverage,
    grep_docs,
    list_docs,
    validate_docs,
)


def _write_schema(ws: Path, typ: str, schema: dict) -> None:
    d = ws / "docs" / typ
    d.mkdir(parents=True, exist_ok=True)
    (d / ".schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8"
    )


ADR_SCHEMA = {
    "filename": r"^(\d{4})-[\w-]+\.md$",
    "h1": r"^#\s+ADR-{id}\s*[:—-]",
    "sections": [
        "## 1. 上下文 (Context)",
        "## 2. 决策 (Decision)",
        "## 3. 产生后果 (Consequences)",
    ],
    "frontmatter": {
        "Status": [
            "Accepted",
            "Draft",
            "Proposed",
            "Deprecated",
            "Rejected",
            "Amended by ADR-\\d{4}",
            "Superseded by ADR-\\d{4}",
        ],
        "Date": "date",
    },
    "codes": {
        "filename": "ADR_FILENAME_MISMATCH",
        "h1": "ADR_FILENAME_MISMATCH",
        "frontmatter": "ADR_FRONTMATTER_MISSING",
        "sections": "ADR_SECTIONS_MISSING",
        "unique": "ADR_NUMBER_COLLISION",
    },
}


class TestDocSchemaCollision(unittest.TestCase):
    def test_collision(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            _write_schema(ws, "adr", ADR_SCHEMA)
            p = ws / "docs" / "adr"
            p.mkdir(parents=True, exist_ok=True)
            for name in ("0001-a.md", "0001-b.md"):
                (p / name).write_text(
                    "---\nStatus: Accepted\nDate: 2026-08-19\n---\n\n# ADR-0001: x\n\n"
                    "## 1. 上下文 (Context)\n\nc\n\n## 2. 决策 (Decision)\n\nd\n\n"
                    "## 3. 产生后果 (Consequences)\n\ne\n",
                    encoding="utf-8",
                )
            vs = validate_docs(ws, types=["adr"])
            self.assertIn("ADR_NUMBER_COLLISION", [v.rule_id for v in vs])


class TestDocList(unittest.TestCase):
    def test_list_excludes_aux_and_archive(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            (ws / "docs" / "adr" / "archive").mkdir(parents=True, exist_ok=True)
            (ws / "docs" / "adr").mkdir(parents=True, exist_ok=True)
            (ws / "docs" / "adr" / "README.md").write_text("# ADR\n", encoding="utf-8")
            (ws / "docs" / "adr" / "AUTHORING.md").write_text("# Authoring\n\nx\n", encoding="utf-8")
            (ws / "docs" / "adr" / "LEFTOVERS.md").write_text("# leftovers\n", encoding="utf-8")
            (ws / "docs" / "adr" / "_template.md").write_text("tmpl\n", encoding="utf-8")
            (ws / "docs" / "adr" / "0001-a.md").write_text(
                "---\nStatus: Accepted\nDate: 2026-08-19\n---\n\n# ADR-0001: x\n",
                encoding="utf-8",
            )
            (ws / "docs" / "adr" / "archive" / "0000-old.md").write_text("old\n", encoding="utf-8")
            cards = list_docs(ws, typ="adr")
            paths = [c["path"] for c in cards]
            self.assertTrue(all("README.md" not in p for p in paths))
            self.assertTrue(all("AUTHORING.md" not in p for p in paths))
            self.assertTrue(all("LEFTOVERS.md" not in p for p in paths))
            self.assertTrue(all("_template.md" not in p for p in paths))
            self.assertTrue(all("archive" not in p for p in paths))


class TestDocGrep(unittest.TestCase):
    def test_grep_returns_path_only(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            (ws / "docs" / "adr").mkdir(parents=True, exist_ok=True)
            (ws / "docs" / "adr" / "0001-a.md").write_text(
                "# ADR-0001: needle\n\nbody with needle here\n", encoding="utf-8"
            )
            hits = grep_docs(ws, "needle")
            self.assertTrue(hits)
            self.assertIn("path", hits[0])
            self.assertNotIn("snippet", hits[0])
            hits_line = grep_docs(ws, "needle", line=True)
            self.assertIn("line", hits_line[0])
            self.assertNotIn("snippet", hits_line[0])


class TestAdrCoverage(unittest.TestCase):
    def _adr(self, ws, number, title, status="Accepted", body=""):
        p = ws / "docs" / "adr" / f"{number}-{title.lower().replace(' ', '-')}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        text = (
            f"---\nStatus: {status}\nDate: 2026-08-19\n---\n\n"
            f"# ADR-{number}: {title}\n\n## 1. 上下文 (Context)\n\nc\n\n"
            f"## 2. 决策 (Decision)\n\nd\n\n## 3. 产生后果 (Consequences)\n\ne\n\n{body}"
        )
        p.write_text(text, encoding="utf-8")

    def test_overlap_and_dangling_detected(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            self._adr(ws, "0001", "MCP Injection Harness Integration", body="see ADR-0002")
            self._adr(ws, "0002", "MCP Injection Sibling Harness", body="references ADR-9999")
            self._adr(ws, "0003", "Local First Layer Cuts")
            out = analyze_adr_coverage(ws)
            kinds = {f["type"] for f in out["findings"]}
            self.assertIn("scope_overlap", kinds)
            self.assertIn("pointer_dangling", kinds)
            self.assertTrue(any(f["b"] == "ADR-9999" for f in out["findings"]))

    def test_superseded_excluded_from_overlap(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            self._adr(ws, "0001", "MCP Injection Harness", status="Superseded by ADR-0002", body="")
            self._adr(ws, "0002", "MCP Sibling Harness", body="see ADR-0001")
            out = analyze_adr_coverage(ws)
            kinds = {f["type"] for f in out["findings"]}
            self.assertIn("pointer_stale", kinds)
            self.assertNotIn("scope_overlap", kinds)
