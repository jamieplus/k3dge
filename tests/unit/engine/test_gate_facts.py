"""gate_facts：闸红文案/档位/可修性的单一声明面（B 线：自动 → 自主）。

守的是内容/流程解耦的**内容侧形态**：档位闭集、block 必给成对选项、不出疑问句、
占位符可安全填、可修性显式分类、检查器真给出声明要的事实。
与 `test_nextstep.TestProjectionInvariants` 同口径——两个投影面（[NEXT] 与闸红）
必须同形，否则判断主体会收到两种形状。
"""

import ast
import functools
import unittest
from pathlib import Path

from k3dge.engine import gate_facts
from k3dge.engine.models import Violation

_SRC = Path(__file__).resolve().parents[3] / "src" / "k3dge"
# t-150① / ocr2-461：parents[3] 一旦指错，rglob 对不存在的目录**静默空转**（os.walk 吞
# OSError），三条 AST 守卫会集体假绿。用显式 raise 而非裸 assert——`python -O` 会剥掉 assert，
# 静默丢覆盖正是本守卫要防的失败模式。
if not (_SRC / "engine" / "gate_facts.py").is_file():
    raise RuntimeError(f"repo root mis-detected: {_SRC}")

# `Violation` 是 frozen dataclass：字段序＝位置参序（t-153 的"第 5 位置参"形状合法）。
_FIELDS = ("rule_id", "message", "domain", "file_path", "detail")


def _scan():
    """单点 AST 扫描（t-151）：三条守卫吃**同一份**站点表。

    旧形状是三份 ~25 行的近似拷贝（已漂移：一份要"首参字面量"、两份要"位置参≥2"），
    下一处"什么算构造点"的修法只会改进其中一份。这里两种形状都认（位置参/关键字），
    读不了/解不出的文件如实收集而非 traceback（t-150②）。
    """
    sites = []
    unreadable = []
    for py in sorted(_SRC.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except (SyntaxError, UnicodeDecodeError, OSError) as exc:
            unreadable.append(f"{py.relative_to(_SRC)}: {type(exc).__name__}: {exc}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name != "Violation":
                continue
            kws = {k.arg: k.value for k in node.keywords if k.arg}
            star = any(k.arg is None for k in node.keywords)

            def slot(i: int, key: str):
                if i < len(node.args):
                    return node.args[i]
                return kws.get(key)

            code_node = slot(0, "rule_id")
            if not (isinstance(code_node, ast.Constant) and isinstance(code_node.value, str)):
                continue          # 动态 code（变量拼表）不归本表管（GATE_FACTS 键闭集另测）
            sites.append({
                "rel": py.relative_to(_SRC).as_posix(), "lineno": node.lineno,
                "code": code_node.value,
                "message": slot(1, "message"), "domain": slot(2, "domain"),
                "file_path": slot(3, "file_path"), "detail": slot(4, "detail"),
                "star_kwargs": star,
            })
    return unreadable, sites


@functools.lru_cache(maxsize=1)
def _violation_sites():
    return _scan()


def _scan_sites_strict():
    """两只散文守卫共用的扫描入口（ocr2-464）：不可读文件必须**硬失败**（显式 raise，
    不被 `python -O` 剥掉，也不是某个类的私有静态法），否则站点会从棘轮里消失而非现形。"""
    unreadable, sites = _violation_sites()
    if unreadable:
        raise RuntimeError(f"AST 扫描有读不了的文件：{unreadable}")
    return sites


def _literal_text(node) -> "str | None":
    """message 里**静态可得**的字面文本：常量、f-string 的字面段、字面串相加。

    返回 None ＝ 值不可静态确定（变量/函数结果）——调用方按"不可核"棘轮处理，
    不得当作通过（t-151：旧守卫只看位置参常量，`Violation("X", message="…")`
    与 f"…" 全部绕过措辞棘轮）。
    """
    if node is None:
        return ""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values
                       if isinstance(v, ast.Constant) and isinstance(v.value, str))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_text(node.left)
        right = _literal_text(node.right)
        return (left + right) if left is not None and right is not None else None
    return None


def _empty_value_node(node) -> bool:
    """值为 `None`/`""` 的字面常量不算覆盖（ocr2-463）。

    `Violation.format()` 只在 `file_path`/`domain` **真值**时注入（models.py:32-35），
    `gate_facts.fill()` 丢弃值为 `None` 的事实（gate_facts.py:617/621）——所以
    `file_path=""`、`detail={"reason": None}` 这类站点会让渲染外漏 `{path}`/`{reason}`，
    但旧判据（"节点在场/键在场"）照样算覆盖。"""
    return isinstance(node, ast.Constant) and (node.value is None or node.value == "")


class TestDeclarationShape(unittest.TestCase):
    def test_severity_is_closed_set(self):
        for code, decl in gate_facts.GATE_FACTS.items():
            self.assertIn(decl.get("severity"), gate_facts.SEVERITIES, code)

    def test_blocking_codes_come_in_pairs(self):
        """block ⇒ ≥2 个 options（只给一条路＝下令，不是给判断主体）。"""
        bad = [c for c, d in gate_facts.GATE_FACTS.items()
               if d.get("severity") == "block" and len(d.get("options") or []) < 2]
        self.assertEqual(bad, [])

    def test_no_interrogative_in_declared_text(self) -> None:
        """疑问句会把预设嵌进句式 ⇒ 纯打印面一律陈述式（ADR-0026 §2.2 语法维）。

        扫描面＝`facts_of` 承认的全部四个字段（fact/fix_hint/options/pointers）——
        `render()` 对这四个都填占位，任何一个漏进 `？`/`y/N`/`倒计时` 都会直接
        渲染进闸红（t-152：旧守卫只看 fact+options，fix_hint 与 pointers 是盲区）。
        半角 `?` 同查（本表当前零命中，中英混排路径/标识符也不该出现问号）。
        """
        fields = ("fact", "fix_hint")
        bad = ("？", "?", "y/N", "Y/n", "倒计时")
        for code, decl in gate_facts.GATE_FACTS.items():
            texts = [str(decl.get(f, "")) for f in fields]
            texts += [str(x) for x in (decl.get("options") or [])]
            texts += [str(x) for x in (decl.get("pointers") or [])]
            for t in texts:
                for b in bad:
                    self.assertNotIn(b, t, f"{code}: {b!r} in {t!r}")

    def test_every_declared_code_has_fact_and_pointers(self):
        for code, decl in gate_facts.GATE_FACTS.items():
            self.assertTrue(decl.get("fact"), code)
            self.assertTrue(decl.get("pointers"), code)


class TestFixClassification(unittest.TestCase):
    """「进程能不能修」是本表的主要产出之一 ⇒ 分类必须显式，不得靠默认值。"""

    def test_every_declared_code_classifies_fix_explicitly(self):
        missing = [c for c, d in gate_facts.GATE_FACTS.items() if d.get("fix") not in gate_facts.FIX_KINDS]
        self.assertEqual(missing, [])

    def test_deterministic_codes_carry_a_hint(self):
        bad = [c for c, d in gate_facts.GATE_FACTS.items()
               if d.get("fix") == "deterministic" and not d.get("fix_hint")]
        self.assertEqual(bad, [])

    def test_deterministic_render_shows_fix_line(self):
        self.assertIn("fix: 确定性可修——k3dge sync",
                      gate_facts.render("DOC_INDEX_STALE", {"reason": "stale"}))
        # 需判断的 code 不得冒充可自动修
        self.assertNotIn("fix:", gate_facts.render("ADR_NUMBER_MISMATCH", {"path": "docs/adr/0001-x.md"}))

    def test_inventory_matches_rulings(self):
        """清单对齐用户裁定（2026-09-19）：已有命令即修法 ⇒ 确定性可修；
        方向不明 / 要读懂语义 / 会改史 ⇒ 需判断（ADR_NUMBER_MISMATCH、TEMPLATE_DRIFT 明写不自动修）。"""
        det = {c for c in gate_facts.GATE_FACTS if gate_facts.fix_kind(c) == "deterministic"}
        for code in ("TASK_BODY_META_REDUNDANT", "ADR_SUPERSEDE_UNRECONCILED", "DOC_INDEX_STALE",
                     "CONTRACT_DRIFT", "CONTRACT_HASH_MISSING", "VERSION_MISMATCH",
                     "MD_TRAILING_WS", "MD_CRLF", "MD_NO_FINAL_NEWLINE"):
            self.assertIn(code, det, code)
        for code in ("ADR_NUMBER_MISMATCH", "TEMPLATE_DRIFT", "MD_CONFLICT_MARKER", "MD_ENCODING",
                     "MD_FENCE_UNCLOSED", "DOC_SECTION_ORDER", "DOC_NEW_UNSCREENED",
                     "DOC_SCHEMA_INVALID", "DANGLING_ADR_REF", "TASK_STATUS_MISMATCH"):
            # ocr2-462：`fix_kind` 对**未声明** code 也回 "judgment"（fallback）——若某 code
            # 从 GATE_FACTS 被删掉，仅断言 fix_kind 会照样绿。先钉它在声明表里。
            self.assertIn(code, gate_facts.GATE_FACTS, f"{code} 已不在声明表里")
            self.assertEqual(gate_facts.fix_kind(code), "judgment", code)
        # 未声明的 code 保守按 judgment（不假装能自动修）
        self.assertEqual(gate_facts.fix_kind("SOMETHING_NEW"), "judgment")


class TestRendering(unittest.TestCase):
    def test_fill_leaves_missing_keys_intact(self):
        self.assertEqual(gate_facts.fill("a={x} b={y}", {"x": 1}), "a=1 b={y}")
        self.assertEqual(gate_facts.fill("no facts", None), "no facts")

    def test_fill_survives_literal_braces(self):
        """模板里有非占位花括号不得抛（工具坏不得阻断提交）。"""
        self.assertIn("{", gate_facts.fill("code={a} set={}", {"a": 1}))

    def test_render_shape(self):
        text = gate_facts.render("DOC_NEW_UNSCREENED", {"path": "docs/memo/x.md"})
        self.assertTrue(text.startswith("[DOC_NEW_UNSCREENED]"))
        self.assertIn("fact:", text)
        self.assertGreaterEqual(text.count("option:"), 2)
        self.assertIn("pointers:", text)
        self.assertIn("k3dge doc screen docs/memo/x.md", text)

    def test_render_carries_detail_and_where(self):
        text = gate_facts.render("CONTRACT_DRIFT",
                                 {"expected_hash": "abc", "actual_hash": "def"},
                                 where="<engine> [docs/specs/engine/spec.md]",
                                 detail="symbol diff: +foo -bar")
        self.assertIn("<engine>", text)
        self.assertIn("spec=abc", text)
        self.assertIn("detail: symbol diff: +foo -bar", text)

    def test_undeclared_code_is_safe(self):
        self.assertEqual(gate_facts.render("SOMETHING_NEW"), "")
        self.assertEqual(gate_facts.severity("SOMETHING_NEW"), gate_facts.DEFAULT_SEVERITY)
        self.assertFalse(gate_facts.is_declared("SOMETHING_NEW"))

    def test_projection_is_closed_set(self):
        """给进程的投影：只有 code/severity/declared/facts，无文案、无分支余地。"""
        d = gate_facts.projection("ORPHAN_ADR", {"path": "docs/adr/0099-x.md"})
        self.assertEqual(set(d), {"code", "severity", "declared", "facts"})
        self.assertEqual(d["severity"], "warn")
        self.assertTrue(d["declared"])

    def test_no_unfilled_placeholder_for_any_code(self):
        """全表自动覆盖：喂代表性事实后不得残留 `{key}`。"""
        for code in gate_facts.GATE_FACTS:
            facts = {k: f"<{k}>" for k in gate_facts.facts_of(code)}
            out = gate_facts.render(code, facts)
            self.assertNotIn("{", out, f"{code}: {out}")
            self.assertIn("fact:", out, code)


class TestViolationWiring(unittest.TestCase):
    def test_declared_code_renders_from_table(self):
        v = Violation("CONTRACT_DRIFT", "spec=abc code=def", domain="engine",
                      file_path="docs/specs/engine/spec.md",
                      detail={"expected_hash": "abc123", "actual_hash": "def456"})
        out = v.format()
        self.assertTrue(out.startswith("[GATE ERROR] [CONTRACT_DRIFT]"))
        self.assertIn("fact:", out)
        self.assertIn("option: k3dge sync", out)
        self.assertIn("abc123", out)

    def test_undeclared_code_keeps_legacy_shape(self):
        """增量迁移：未进表的 code 仍走旧形状（message 自带），不得变空。

        用一个刻意不存在的 code——迁移完成后本测试仍须成立（表的兜底路径不能被删）。
        """
        code = "ZZZ_NOT_DECLARED_YET"
        self.assertFalse(gate_facts.is_declared(code))
        v = Violation(code, "raw message", domain="engine", file_path="x.md")
        self.assertEqual(v.format(), f"[GATE ERROR] {code} <engine>: raw message [x.md]")

    def test_severity_tag_follows_declaration(self):
        self.assertTrue(Violation("ORPHAN_TEST", "t", file_path="tests/x.py").format()
                        .startswith("[GATE WARN]"))
        self.assertTrue(Violation("DUP_CHECK", "t").format().startswith("[GATE NOTE]"))

    def test_json_carries_severity(self):
        from k3dge.cli.main import _to_json
        from k3dge.engine.models import GateReport

        rep = GateReport(passed=False, violations=(Violation("ORPHAN_ADR", "a"),))
        self.assertEqual(_to_json(rep)["violations"][0]["severity"], "warn")


class TestProducersFeedDeclaredFacts(unittest.TestCase):
    """结构守卫：声明了占位符的 code，其 `Violation(...)` 构造点必须**真给出**那些事实。

    这是"内容/流程解耦"的接缝检查——表里写了 `{path}`，检查器就必须真给 `path`；
    否则文案永远缺字段，而这种漂移以前无人发现。静态扫 AST，不靠人记。

    判据强度与承诺对齐（t-153）："detail= 在场"远不够——`detail={}` 照样过闸、
    文案里 {expected_hash} 以字面量外漏。这里对**字面 dict** 逐键核对，覆盖
    `Violation.format()` 会注入的 `{path}`/`{domain}`（来源＝file_path/domain 在场）；
    不可静态核的形状（`**kwargs`、非字面 detail）按显式白名单棘轮，不许增。
    """

    def _scan_state(self):
        unreadable, sites = _violation_sites()
        self.assertEqual(unreadable, [], "AST 扫描有读不了的文件——守卫看不见它们（t-150②）")
        declared = [s for s in sites if gate_facts.is_declared(s["code"])]
        self.assertGreaterEqual(len(declared), 40,
                                f"只扫到 {len(declared)} 个已声明构造点——根/布局错了还是表空了（t-150③）")
        return declared

    def test_declared_codes_with_placeholders_pass_detail(self):
        missing = []
        unverifiable = []
        for s in self._scan_state():
            keys = set(gate_facts.facts_of(s["code"]))
            if not keys:
                continue
            if s["star_kwargs"]:
                unverifiable.append(f"{s['rel']}:{s['lineno']} {s['code']}（**kwargs 解不动）")
                continue
            injected = set()
            if s["file_path"] is not None and not _empty_value_node(s["file_path"]):
                injected.add("path")
            if s["domain"] is not None and not _empty_value_node(s["domain"]):
                injected.add("domain")
            detail = s["detail"]
            if detail is None:
                uncovered = keys - injected
                if uncovered:
                    missing.append(f"{s['rel']}:{s['lineno']} {s['code']} 缺 detail=（声明用了 "
                                   f"{sorted(keys)}，注入面只覆盖 {sorted(injected)}）")
                continue
            if isinstance(detail, ast.Dict):
                # ocr2-463：值为 None/"" 的键不算覆盖（fill 会丢 None；"" 渲染成空占位）
                lit_keys = {k.value for k, v in zip(detail.keys, detail.values)
                            if isinstance(k, ast.Constant) and isinstance(k.value, str)
                            and not _empty_value_node(v)}
                if any(k is None for k in detail.keys):     # dict 里 `**` 展开
                    unverifiable.append(f"{s['rel']}:{s['lineno']} {s['code']}（detail 含 **）")
                    continue
                uncovered = keys - lit_keys - injected
                if uncovered:
                    missing.append(f"{s['rel']}:{s['lineno']} {s['code']} detail 字面 dict 没给 "
                                   f"{sorted(uncovered)}（渲染会外漏占位符）")
                continue
            unverifiable.append(f"{s['rel']}:{s['lineno']} {s['code']}（detail 非字面 dict）")
        self.assertEqual(missing, [])
        # 棘轮：不可静态核的构造点现状登记，只许减不许增（消灭"绕过＝通过"）
        self.assertLessEqual(len(unverifiable), 6,
                             f"不可核站点增长：{unverifiable}")


class TestNoProseBackflow(unittest.TestCase):
    """棘轮：已声明的 code，其构造点不得再拼散文（措辞只能来自表）。

    字面段也覆盖 **f-string 的字面部分**（t-151）：39/56 个 message 是 JoinedStr，
    旧守卫只看常量位置参 ⇒ 主要形状整体绕过；`f"闸红：{x}；先跑 k3dge sync"` 这种
    把补救散文拼回 message 的写法，字面段必须照扫。
    """

    MAX_MESSAGE = 100
    _WORDS = ("run 'k3dge", "run `k3dge", "；先 ", "please ", "请先跑", "请运行")

    def test_declared_code_messages_stay_factual(self):
        offenders = []
        unverifiable = []
        for s in _scan_sites_strict():
            if not gate_facts.is_declared(s["code"]):
                continue
            text = _literal_text(s["message"])
            if text is None:
                unverifiable.append(f"{s['rel']}:{s['lineno']} {s['code']}")
                continue
            if len(text) > self.MAX_MESSAGE:
                offenders.append(f"{s['rel']}:{s['lineno']} {s['code']} "
                                 f"message 字面 {len(text)} 字符（措辞应归表）")
            for word in self._WORDS:
                if word in text:
                    offenders.append(f"{s['rel']}:{s['lineno']} {s['code']} "
                                     f"message 里出现补救散文 {word!r}（应归 options）")
        self.assertEqual(offenders, [])
        # 棘轮：2026-10-01 实测 7 处（变量/函数结果拼 message），只许减不许增
        self.assertLessEqual(len(unverifiable), 7,
                             f"message 完全静态不可核的站点在增长：{unverifiable}")


class TestMessageDoesNotRestateFact(unittest.TestCase):
    """棘轮：已声明 code 的构造点 `message` 不得**复述声明 fact 的散文片段**。

    detail（检查器原文）与 fact（声明文案）是两层；message 只该是"事实摘要"，
    复述 fact 的措辞会立刻产生第二个文案源（改一处忘一处）。
    字段名/标识符的重叠不算（那本身就是事实），故只查**含中文的散文片段**。
    f-string 的字面段同样进比对（与 TestNoProseBackflow 共判据面）。
    """

    MIN_SEG = 10

    def _segments(self, text: str):
        import re

        t = re.sub(r"\{[^}]*\}", "", text or "")
        parts = re.split(r"[，。；、（）()\[\]`：:…——\s]+", t)
        return [s.strip() for s in parts
                if len(s.strip()) >= self.MIN_SEG and re.search(r"[\u4e00-\u9fff]", s)]

    def test_static_messages_do_not_restate_facts(self):
        offenders = []
        for s in _scan_sites_strict():
            if not gate_facts.is_declared(s["code"]):
                continue
            text = _literal_text(s["message"])
            if not text:
                continue
            fact = (gate_facts.GATE_FACTS.get(s["code"]) or {}).get("fact", "")
            for seg in self._segments(fact):
                if seg in text:
                    offenders.append(f"{s['rel']}:{s['lineno']} {s['code']}: "
                                     f"message 复述 fact 片段 {seg!r}")
        self.assertEqual(offenders, [])


class TestFactsAreProducedNotParsed(unittest.TestCase):
    """棘轮：已声明 code 的事实字段，其消费者**不得**从 message 里切（散文解析）。

    实测前科：pre-commit 用 `msg.split(": ")[-1]` / `msg.split(":")[0]` 从检查器的
    message 里取 path——检查器一改措辞就静默取错。现在检查器只产 (code, 事实)，
    path 由调用方显式给（`where=`）。
    """

    def test_hook_does_not_split_messages(self):
        """扫描面＝**薄壳＋实现宿主**两件（t-154 尾账）。

        2026-09-21 起实现搬进 `k3dge.engine.doc_gate`、`scripts/pre-commit` 只是薄壳——
        旧测只扫壳，散文解析若回流到 doc_gate 里，本守卫照样绿；壳哪天挪走/改名，
        read_text 还会以 FileNotFoundError 崩掉而不是说清"守卫的靶没了"。
        """
        root = Path(__file__).resolve().parents[3]
        targets = [root / "scripts" / "pre-commit",
                   root / "src" / "k3dge" / "engine" / "doc_gate.py"]
        import re as _re
        # ocr2-465：不能只认 `msg.split` 这个名字——`m.split(...)`/`message.split(...)`/
        # `v.message.split(...)`（任何指向 message 的局部名）以及 `re.search(..., msg)` 都是
        # 同一类静默字段提取。按"对象是 message 系"匹配，而非钉死一个标识符。
        split_pat = _re.compile(r"\b\w*(?:msg|message)\w*\s*\.\s*split\b", _re.IGNORECASE)
        regex_pat = _re.compile(
            r"\bre\.(?:search|match|findall|finditer|fullmatch|sub|split)\s*\([^)]*"
            r"\b\w*(?:msg|message)\w*", _re.IGNORECASE)
        for t in targets:
            self.assertTrue(t.is_file(), f"守卫靶不存在（搬家了？）：{t}")
        for t in targets:
            code_lines = [ln for ln in t.read_text(encoding="utf-8").splitlines()
                          if not ln.strip().startswith("#")
                          and (split_pat.search(ln) or regex_pat.search(ln))]
            self.assertEqual(code_lines, [], f"{t.name} 仍在从 message 里切字段：{code_lines}")

    def test_pure_checks_return_facts_for_declared_codes(self):
        """抽样：`ORPHAN_*` / `MD_CRLF` / `ARCHIVE_NO_DEST` 返回的第二项就是**事实**（路径）。"""
        import tempfile

        from k3dge.engine import pure_refs

        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            p = ws / "docs" / "memo" / "a.md"
            p.parent.mkdir(parents=True)
            p.write_text("# t\r\n", encoding="utf-8")
            self.assertEqual(pure_refs.check_markdown_bytes(p.read_bytes(), "docs/memo/a.md"),
                             [("MD_CRLF", "docs/memo/a.md")])
            arch = ws / "docs" / "memo" / "archive"
            arch.mkdir(parents=True)
            (arch / "x.md").write_text("# 归档但没写去向标记\n", encoding="utf-8")
            self.assertEqual(pure_refs.find_unguarded_archives(ws, ["docs/memo/archive/x.md"]),
                             [("ARCHIVE_NO_DEST", "docs/memo/archive/x.md")])


class TestDeclaredInvalidSeverity(unittest.TestCase):
    """已声明但 severity 非法的 code 不得被静默升成 block（ocr2-255）。"""

    def test_invalid_declared_severity_is_warn_and_loud(self):
        import contextlib
        import io

        code = "__OCR2_255_INVALID__"
        gate_facts.GATE_FACTS[code] = {"severity": "blockk", "fix": "judgment"}
        try:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                sev = gate_facts.severity(code)
        finally:
            gate_facts.GATE_FACTS.pop(code, None)
        self.assertEqual(sev, "warn")
        self.assertIn("WARN", err.getvalue())
