
import json
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.doc_catalog import (
    analyze_adr_coverage,
    build_docs_index,
    check_section_order,
    grep_docs,
    list_docs,
    validate_docs,
    where_doc,
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


class TestSectionOrder(unittest.TestCase):
    def test_valid_outline_ok(self):
        text = "## 1. a\n### 1.1 b\n### 1.2 c\n## 2. d\n### 2.1 e\n## 3. f\n"
        self.assertIsNone(check_section_order(text))

    def test_out_of_order_detected(self):
        # a subsection appended out of position: 2.1.8 then 2.1.5 (the 0004 regression)
        text = "### 2.1.4 a\n### 2.1.7 b\n### 2.1.8 c\n### 2.1.5 d\n"
        bad = check_section_order(text)
        self.assertIsNotNone(bad)
        self.assertEqual(bad, ("2.1.8", "2.1.5"))

    def test_duplicate_detected(self):
        text = "## 2. a\n## 2. b\n"
        self.assertEqual(check_section_order(text), ("2", "2"))

    def test_unnumbered_doc_ok(self):
        text = "## Context\n## Decision\n"
        self.assertIsNone(check_section_order(text))

    def test_gate_emits_violation(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            import copy as _copy
            schema = _copy.deepcopy(ADR_SCHEMA)   # 浅拷贝会让 schema["codes"] 与全局同一个 dict
            schema["section_order"] = True
            schema.setdefault("codes", {})["section_order"] = "ADR_SECTION_ORDER"
            _write_schema(ws, "adr", schema)
            (ws / "docs" / "adr" / "_template.md").write_text("", encoding="utf-8")
            (ws / "docs" / "adr" / "0001-x.md").write_text(
                "---\nStatus: Accepted\nDate: 2026-01-01\n---\n# ADR-0001: x\n\n"
                "## 1. 上下文 (Context)\n## 2. 决策 (Decision)\n### 2.1 a\n### 2.2 b\n### 2.1 c\n"
                "## 3. 产生后果 (Consequences)\n",
                encoding="utf-8",
            )
            codes = [v.rule_id for v in validate_docs(ws, ["adr"])]
            self.assertIn("ADR_SECTION_ORDER", codes)


class TestCardTitleSkipsFrontmatter(unittest.TestCase):
    """回归守卫：frontmatter 里的 YAML 注释不得被当成 H1 标题。

    实测病灶：12/14 条 ADR 的 frontmatter 带 `# Append-only after Accepted…` 注释，
    `_TITLE_RE` 全文搜索 ⇒ `doc list` 与 docs-index.json 的 title 全变成那行注释。
    """

    def _card(self, text: str):
        from k3dge.engine.doc_catalog import build_card

        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            p = ws / "docs" / "adr" / "0001-x.md"
            p.parent.mkdir(parents=True)
            p.write_text(text, encoding="utf-8")
            return build_card(ws, "adr", p)

    def test_yaml_comment_is_not_the_title(self):
        card = self._card(
            "---\nStatus: Accepted\n"
            "# Append-only after Accepted. Revise via Amended-by — do NOT rewrite.\n"
            "Date: 2026-09-01\n---\n\n# ADR-0001: 真标题\n\n正文\n"
        )
        self.assertEqual(card["title"], "ADR-0001: 真标题")
        self.assertEqual(card["status"], "Accepted")

    def test_no_frontmatter_still_finds_h1(self):
        self.assertEqual(self._card("# ADR-0002: 裸标题\n")["title"], "ADR-0002: 裸标题")

    def test_unterminated_frontmatter_does_not_swallow_body(self):
        """`---` 未闭合 ⇒ 不当 frontmatter 处理，正文 H1 仍可抽到。"""
        card = self._card("---\nStatus: Accepted\n\n# ADR-0003: 标题\n")
        self.assertIn("ADR-0003", card["title"])

    def test_repo_adr_titles_are_real_h1(self):
        """自举：本仓 ADR 的索引标题必须是 `ADR-NNNN: …`，不是注释残句。"""
        ws = Path(__file__).resolve().parents[3]
        cards = [c for c in list_docs(ws, typ="adr") if c["id"].startswith("ADR-")]
        self.assertTrue(cards)
        bad = [c["id"] for c in cards if not c["title"].startswith(c["id"])]
        self.assertEqual(bad, [])


class TestRetiredAdrVisibility(unittest.TestCase):
    """退役 ADR 必须**可寻址**（票 adr_number_cutline 的漏项）。

    病灶：账本里的 13 个号没有墓碑文件，`doc where ADR-0020` 只说 "not found"
    ⇒ 退役号在寻址面彻底隐身，人只能靠闸报错时偶然得知去向。
    """

    def test_repo_retired_ledger_is_resolvable(self):
        ws = Path(__file__).resolve().parents[3]
        rows = where_doc(ws, "ADR-0020")
        self.assertEqual(len(rows), 1)
        c = rows[0]
        self.assertTrue(c["retired"])
        self.assertEqual(c["id"], "ADR-0020")
        self.assertIn("harness-responsibility-split", c["title"])
        self.assertIn("ADR-0005", c["dest"])                  # 去向量可读

    def test_live_id_still_resolves_to_live_file(self):
        ws = Path(__file__).resolve().parents[3]
        rows = where_doc(ws, "ADR-0025")
        self.assertEqual([c["path"] for c in rows], ["docs/adr/0025-hall-harness-topology.md"])
        self.assertFalse(rows[0].get("retired"))

    def test_default_list_excludes_retired(self):
        ws = Path(__file__).resolve().parents[3]
        self.assertFalse(any(c.get("retired") for c in list_docs(ws, typ="adr")))
        with_retired = list_docs(ws, typ="adr", include_retired=True)
        self.assertTrue(any(c.get("retired") for c in with_retired))
        self.assertEqual(len(with_retired) - len(list_docs(ws, typ="adr")), 13)   # 账本 13 号

    def test_stored_projection_stays_live_only(self):
        """存盘投影（docs-index.json）保持现行视图，不被退役面污染（DOC_INDEX_STALE 语义不变）。"""
        ws = Path(__file__).resolve().parents[3]
        self.assertFalse(any(c.get("retired") for c in build_docs_index(ws)["docs"]))

    def test_obsolete_file_is_marked_with_destination(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            obs = ws / "docs" / "adr" / "obsolete"
            obs.mkdir(parents=True)
            (obs / "0042-old.md").write_text(
                "---\nStatus: Superseded\nmerged-into: ADR-0005 §2.7\n---\n\n# ADR-0042: 旧决策\n",
                encoding="utf-8")
            # `where` 默认含退役面（退役号要查得到），且标 retired + 去向
            rows = where_doc(ws, "ADR-0042")
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["retired"])
            self.assertIn("ADR-0005", rows[0]["dest"])
            # 但默认**列表**不含退役面（现行视图不被污染）
            self.assertEqual(list_docs(ws, typ="adr"), [])
            self.assertEqual(len(list_docs(ws, typ="adr", include_retired=True)), 1)


def test_shipped_schema_codes_are_declared() -> None:
    """`.schema.json` 里的每个码都必须在 `gate_facts` 声明（342）。

    未声明码走 `doc_gate._add` 的兜底分支 ⇒ 只输出 `[CODE] 原始消息`，
    拿不到 fact/options/pointers——同一不变量在别处有声明码就是两套回执面。
    """

    from k3dge.engine.gate_facts import GATE_FACTS, is_declared

    repo = Path(__file__).resolve().parents[3]
    undeclared = []
    for f in sorted((repo / "docs").glob("*/.schema.json")):
        codes = (json.loads(f.read_text(encoding="utf-8")).get("codes") or {})
        undeclared += [f"{f.parent.name}:{k}={v}" for k, v in codes.items()
                       if not is_declared(v)]
    # 已知债（2026-09-30，LEFTOVERS「schema 未声明码」）：这四码是 schema 专用别名，
    # 需要各自写 fact/options 才能进声明表 ⇒ 独立批次。本测试兜住"别再新增第五个"。
    known_debt = {"ADR_AMEND_FORMAT", "INCIDENT_FORM_INVALID",
                  "TASK_STATUS_INVALID", "TASK_SECTION_MISSING"}
    fresh = [u for u in undeclared if u.split("=")[-1] not in known_debt]
    assert not fresh, "未声明的 schema 码（回执降级）：" + str(fresh)
