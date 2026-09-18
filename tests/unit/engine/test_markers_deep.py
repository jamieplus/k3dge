"""markers: 审计钉解析——重点锁 code-11（行号口径）与 @repo/多主锚校验。"""
import unittest

from k3dge.engine.markers import (
    Marker,
    OPEN_KINDS,
    SIDECAR,
    _line_index,
    closure_ok,
    counts,
    head_block_end,
    open_samples,
    parse_sidecar,
    parse_text,
    validate,
)


def _mk(id="X1", kind="pending", file="src/a.py", line=1, scope="line", note=""):
    return Marker(file=file, line=line, kind=kind, id=id, scope=scope, note=note)


class TestHeadBlockEnd(unittest.TestCase):
    def test_shebang_and_encoding_allowed(self):
        lines = ["#!/usr/bin/env python3", "# -*- coding: utf-8 -*-", "# real comment", "import os"]
        self.assertEqual(head_block_end(lines), 3)

    def test_docstring_terminates_block(self):
        """语义记录：docstring 不算注释行（_COMMENT_LINE_RE 只认 # // <!--）。

        后果：`@file` 钉必须写在 docstring **之前**的注释块里，否则报
        「声明 @file 但不在头部注释块内」。
        """
        self.assertEqual(head_block_end(["#!/usr/bin/env python3", '"""doc"""', "import os"]), 1)

    def test_blank_lines_inside_block(self):
        self.assertEqual(head_block_end(["# a", "", "# b", "code = 1"]), 3)

    def test_no_header(self):
        self.assertEqual(head_block_end(["x = 1", "# later"]), 0)

    def test_empty(self):
        self.assertEqual(head_block_end([]), 0)

    def test_all_comments(self):
        self.assertEqual(head_block_end(["# a", "// b", "<!-- c -->"]), 3)


class TestLineIndex(unittest.TestCase):
    """code-11 回归守卫：行号必须与 str.splitlines() 同口径。

    splitlines 除 \\n 外还切 \\x0b \\x0c \\x1c-\\x1e \\x85 \\u2028 \\u2029；
    若 _line_index 只认 \\n，strip_pins 按 splitlines 索引删行会错位删错行。
    """

    def test_matches_splitlines_for_plain_newlines(self):
        text = "a\nb\nc\n"
        for offset in range(len(text)):
            expected = text[:offset].count("\n") + 1
            self.assertEqual(_line_index(text, offset), expected, f"offset={offset}")

    @unittest.skipUnless(True, "exotic line breaks")
    def test_exotic_breaks_count_as_lines(self):
        # \x0b (vertical tab) 是 splitlines 的行界
        text = "a\x0bb\n"
        self.assertEqual(len(text.splitlines()), 2)
        # 第二行起点在 \x0b 之后
        pos_b = text.index("b")
        self.assertEqual(_line_index(text, pos_b), 2)

    def test_unicode_line_separator(self):
        text = "a\u2028b"
        self.assertEqual(len(text.splitlines()), 2)
        self.assertEqual(_line_index(text, text.index("b")), 2)

    def test_crlf_counts_once(self):
        text = "a\r\nb"
        self.assertEqual(len(text.splitlines()), 2)
        self.assertEqual(_line_index(text, text.index("b")), 2)


class TestParseText(unittest.TestCase):
    def test_python_line_marker(self):
        src = "x = 1  # k3dit:pending A1 sev=high prio=P1 type=bug 说明\n"
        ms, problems = parse_text("src/a.py", src)
        self.assertEqual(len(ms), 1)
        m = ms[0]
        self.assertEqual((m.kind, m.id, m.sev, m.prio, m.type), ("pending", "A1", "high", "P1", "bug"))
        self.assertEqual(m.scope, "line")
        self.assertEqual(m.line, 1)
        self.assertEqual(problems, [])

    def test_markdown_uses_comment_syntax_only(self):
        # md 文件里裸 `# k3dit:` 不算钉（必须 <!-- -->），防反引号示例自触发
        md = "# k3dit:pending A1 note\n"
        ms, _ = parse_text("docs/a.md", md)
        self.assertEqual(ms, [])
        md2 = "<!-- k3dit:pending A1 note -->\n"
        ms2, _ = parse_text("docs/a.md", md2)
        self.assertEqual(len(ms2), 1)

    def test_backtick_example_in_md_not_matched(self):
        md = "行内示例 `k3dit:pending A1` 不应触发\n"
        ms, _ = parse_text("docs/a.md", md)
        self.assertEqual(ms, [])

    def test_note_cap_truncates_and_reports(self):
        long_note = "x" * 90
        src = f"y = 2  # k3dit:leftover L1 {long_note}\n"
        ms, problems = parse_text("src/a.py", src, max_note=80, max_note_pending=500)
        self.assertEqual(len(problems), 1)
        self.assertIn("超 80", problems[0])
        self.assertTrue(ms[0].note.endswith("…"))

    def test_pending_allows_longer_note(self):
        note = "y" * 300
        src = f"z = 3  # k3dit:pending P1 {note}\n"
        ms, problems = parse_text("src/a.py", src, max_note=80, max_note_pending=500)
        self.assertEqual(problems, [])
        self.assertEqual(ms[0].note, note)

    def test_file_scope_outside_header_is_problem(self):
        src = "code = 1\nmore = 2\n# k3dit:leftover F1 @file 在正文里\n"
        ms, problems = parse_text("src/a.py", src)
        self.assertEqual(len(ms), 1)
        self.assertTrue(any("@file" in p for p in problems), problems)

    def test_file_scope_in_header_ok(self):
        src = "# k3dit:leftover F1 @file 头部块内\n\ncode = 1\n"
        ms, problems = parse_text("src/a.py", src)
        self.assertEqual(len(ms), 1)
        self.assertEqual(problems, [])

    def test_fixed_and_leftover_not_open(self):
        src = ("a = 1  # k3dit:fixed D1 ok\n"
               "b = 2  # k3dit:leftover L1 keep\n"
               "c = 3  # k3dit:pending P1 todo\n")
        ms, _ = parse_text("src/a.py", src)
        self.assertEqual({m.kind for m in ms}, {"fixed", "leftover", "pending"})


class TestParseSidecar(unittest.TestCase):
    def test_repo_entry(self):
        text = "## k3dit:pending R1@repo 全局发现\n"
        ms, problems = parse_sidecar(text)
        self.assertEqual(len(ms), 1)
        self.assertEqual((ms[0].id, ms[0].scope, ms[0].file), ("R1", "repo", SIDECAR))
        self.assertEqual(problems, [])

    def test_missing_repo_scope_is_problem(self):
        text = "## k3dit:pending R2 没写 @repo\n"
        ms, problems = parse_sidecar(text)
        self.assertEqual(len(ms), 1)
        self.assertTrue(any("@repo" in p for p in problems), problems)

    def test_files_line_appends_to_note(self):
        text = "## k3dit:pending R3@repo 说明\n- files: src/a.py, src/b.py\n"
        ms, _ = parse_sidecar(text)
        self.assertEqual(len(ms), 1)
        self.assertIn("src/a.py", ms[0].note)
        self.assertIn("说明", ms[0].note)

    def test_non_marker_heading_ignored(self):
        text = "## 普通标题\n\n正文\n"
        ms, problems = parse_sidecar(text)
        self.assertEqual(ms, [])
        self.assertEqual(problems, [])


class TestOpenSamplesAndCounts(unittest.TestCase):
    def test_open_kinds_are_pending_disputed_fixnote(self):
        self.assertEqual(OPEN_KINDS, frozenset({"pending", "disputed", "fixnote"}))

    def test_open_samples_excludes_fixed_and_leftover(self):
        ms = [_mk("A", "pending"), _mk("B", "fixed"), _mk("C", "leftover"), _mk("D", "disputed")]
        got = open_samples(ms)
        self.assertEqual(sorted(got), ["src/a.py#A", "src/a.py#D"])

    def test_counts_includes_open_total(self):
        ms = [_mk("A", "pending"), _mk("B", "pending"), _mk("C", "fixed"), _mk("D", "leftover")]
        c = counts(ms)
        self.assertEqual(c["pending"], 2)
        self.assertEqual(c["fixed"], 1)
        self.assertEqual(c["leftover"], 1)
        self.assertEqual(c["open"], 2)

    def test_closure_ok_blocked_by_pending(self):
        ok, info = closure_ok([_mk("A", "pending")])
        self.assertFalse(ok)
        self.assertIn("pending", info["blockers"])

    def test_closure_ok_passes_with_only_leftover(self):
        ok, info = closure_ok([_mk("L", "leftover"), _mk("F", "fixed")])
        self.assertTrue(ok)
        self.assertEqual(info["blockers"], {})


class TestValidate(unittest.TestCase):
    def test_repo_scope_outside_sidecar_is_problem(self):
        ms = [_mk("R", "pending", file="src/a.py", scope="repo")]
        problems = validate(None, ms)
        self.assertTrue(any("@repo" in p for p in problems), problems)

    def test_repo_scope_in_sidecar_ok(self):
        ms = [_mk("R", "pending", file=SIDECAR, scope="repo")]
        self.assertEqual(validate(None, ms), [])

    def test_same_id_multiple_kinds_is_problem(self):
        ms = [_mk("X", "pending", file="src/a.py"), _mk("X", "leftover", file="src/a.py")]
        problems = validate(None, ms)
        self.assertTrue(any("多种 kind" in p for p in problems), problems)

    def test_multi_anchor_same_id_is_problem(self):
        ms = [_mk("X", "pending", file="src/a.py"), _mk("X", "pending", file="src/b.py")]
        problems = validate(None, ms)
        self.assertTrue(any("多主锚" in p for p in problems), problems)

    def test_leftover_may_span_files(self):
        """规则 2 例外：leftover 随文件走，多宿主不算违规。"""
        ms = [_mk("L", "leftover", file="src/a.py"), _mk("L", "leftover", file="src/b.py")]
        self.assertEqual(validate(None, ms), [])


if __name__ == "__main__":
    unittest.main()
