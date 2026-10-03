
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


def _repo_root(test: unittest.TestCase) -> Path:
    """仓根＝向上找 `docs/adr/.schema.json` 标记（t-105）。

    旧写法 `parents[3]` 只在这个文件的规范位置成立——摊平复制（scan_in/…）或换深度
    就指到仓根**之外**：`list_docs`/`where_doc` 返回空 ⇒ 报"没有 ADR"这种误导话，
    而不是"fixture 路径错"。找不到标记 ⇒ 显式 skip，不空转绿。
    """
    cur = Path(__file__).resolve()
    for cand in cur.parents:
        if (cand / "docs" / "adr" / ".schema.json").is_file():
            return cand
    test.skipTest("找不到带 docs/adr/.schema.json 的仓根（文件被复制到别处？）")
    raise AssertionError  # unreachable


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
            # 正对照（t-104）：真 ADR 必须**在**列表里——否则过滤过狠/布局不认时
            # `list_docs` 返回 [] ，下面全部 all() 恒真，本测什么都没排除也"通过"。
            self.assertIn("docs/adr/0001-a.md", paths, paths)
            for name in ("README.md", "AUTHORING.md", "LEFTOVERS.md", "_template.md"):
                self.assertNotIn(f"docs/adr/{name}", paths, name)
            # `archive` 用**路径分量**判，不用子串（t-104）：一个真叫
            # `0002-archive-policy.md` 的现行 ADR 不该被误当归档件排除。
            for pth in paths:
                parts = Path(pth).parts
                self.assertNotIn("archive", parts, pth)


class TestDocGrep(unittest.TestCase):
    def test_unreadable_card_uses_canonical_id(self):
        """读不出的卡片与可读时拿同一个 id（ocr2-604）。

        读不出（此处用目录冒充不可读文件）时 `path.stem` 会给出 `0042-foo`，
        而可读时 `_card_id` 给出 `ADR-0042` ⇒ 同一份文档两种身份，`where_doc`
        按规范 id 找不着它。不可读分支也走 `_card_id`（只看文件名，不读内容）。
        """
        from k3dge.engine.doc_catalog import build_card

        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            bad = ws / "docs" / "adr" / "0042-foo.md"
            bad.mkdir(parents=True)
            card = build_card(ws, "adr", bad)
            self.assertEqual(card["id"], "ADR-0042")
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
        ws = _repo_root(self)
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
        ws = _repo_root(self)
        rows = where_doc(ws, "ADR-0020")
        self.assertEqual(len(rows), 1)
        c = rows[0]
        self.assertTrue(c["retired"])
        self.assertEqual(c["id"], "ADR-0020")
        self.assertIn("harness-responsibility-split", c["title"])
        self.assertIn("ADR-0005", c["dest"])                  # 去向量可读

    def test_live_id_still_resolves_to_live_file(self):
        ws = _repo_root(self)
        rows = where_doc(ws, "ADR-0025")
        self.assertEqual([c["path"] for c in rows], ["docs/adr/0025-hall-harness-topology.md"])
        self.assertFalse(rows[0].get("retired"))

    def test_default_list_excludes_retired(self):
        ws = _repo_root(self)
        live = list_docs(ws, typ="adr")                      # 各扫一遍全仓索引（t-106）：算一次
        # ocr2-454：现行视图必须**非空**（真发现到活 ADR）——否则发现机制坏成 [] 时，
        # `any(retired)` 恒假，负断言的"排除"语义全空转。
        self.assertTrue(live, "live ADR 发现为空 ⇒ 本测未证明任何排除")
        self.assertFalse(any(c.get("retired") for c in live))
        with_retired = list_docs(ws, typ="adr", include_retired=True)
        retired = [c for c in with_retired if c.get("retired")]
        self.assertTrue(retired)
        # 不钉死"13"这个魔法数（t-106）：一次常规退役/恢复就会打断测——**增量**由账本自己定义：
        # 带 retired 标记的卡数 == 两个视图的差，且现行视图一张不漏。
        self.assertEqual(len(with_retired) - len(live), len(retired),
                         "退役面/现行面差不等于退役卡数")

    def test_stored_projection_stays_live_only(self):
        """存盘投影（docs-index.json）保持现行视图，不被退役面污染（DOC_INDEX_STALE 语义不变）。"""
        ws = _repo_root(self)
        docs = build_docs_index(ws)["docs"]
        # ocr2-455：投影为空时 `any(...)` 恒假——先证明真的发现了文档（t-104/106 口径）。
        self.assertTrue(docs, "docs-index 投影为空 ⇒ '保持现行视图' 无从谈起")
        self.assertFalse(any(c.get("retired") for c in docs))

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

    # ocr2-732：旧 `parents[3]` 只在规范位置成立——摊平复制/换深度就静默指错靶，
    # 漂了的路径恰好含 docs 树时还会验错树。与本文件 `_repo_root`（t-105）同规则：向上找标记。
    repo = None
    for cand in Path(__file__).resolve().parents:
        if (cand / "docs" / "adr" / ".schema.json").is_file():
            repo = cand
            break
    assert repo is not None, f"仓根标记找不到（文件被复制到别处？）：{Path(__file__).resolve()}"
    assert (repo / "docs").is_dir(), f"仓根解析错误：{repo}（标记漂了？）"
    schema_files = sorted((repo / "docs").glob("*/.schema.json"))
    # 正对照（同 t-105 的病）：一份 schema 都没扫到时循环空转、undeclared 恒空＝假绿
    assert len(schema_files) >= 5, f"只扫到 {len(schema_files)} 份 .schema.json——判据在空转"
    undeclared = []
    for f in schema_files:
        codes = (json.loads(f.read_text(encoding="utf-8")).get("codes") or {})
        undeclared += [(f.parent.name, k, v) for k, v in codes.items()
                       if not is_declared(v)]
    # 已知债（2026-09-30，LEFTOVERS「schema 未声明码」）：这些码是 schema 专用别名，
    # 需要各自写 fact/options 才能进声明表 ⇒ 独立批次。本测试兜住"别再新增"。
    # ocr2-686 已还：INCIDENT_FORM_INVALID 进 GATE_FACTS 后从本集合移除。
    known_debt = {"ADR_AMEND_FORMAT",
                  "TASK_STATUS_INVALID", "TASK_SECTION_MISSING"}
    # 直接对**结构化值**过滤（旧写 `u.split("=")[-1]` 再比——值里含 `=` 即错配，
    # 且 type/key 改名会静默把新债当旧债、或把旧债当新违例，t-108）；展示时才拼串。
    fresh = [u for u in undeclared if u[2] not in known_debt]
    # ocr2-731：GATE_FACTS 此前只 import 不用——失败信息里报出声明表规模，定位"哪边漏声明"。
    assert not fresh, ("未声明的 schema 码（回执降级，声明表共 "
                       f"{len(GATE_FACTS)} 项）：" + str([f"{t}:{k}={v}" for t, k, v in fresh]))
