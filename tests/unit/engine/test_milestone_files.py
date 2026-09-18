"""milestone_files: 文件名/评审文件谓词——重点锁 M1 不匹配 M10 的 token 语义。"""
import unittest

from k3dge.engine.milestone_files import (
    _filename_milestone,
    _has_milestone_token,
    _is_doc_aux,
    _is_review_aux,
)


class TestHasMilestoneToken(unittest.TestCase):
    """核心不变量：milestone id 必须按 token 匹配，不能是更长 id 的子串。"""

    def test_m1_does_not_match_m10(self):
        # 回归守卫：`M1` 命中 `2026-08-23-M10-align.md` 曾导致跨里程碑误判
        self.assertFalse(_has_milestone_token("2026-08-23-M10-align.md", "M1"))
        self.assertFalse(_has_milestone_token("M10", "M1"))
        self.assertFalse(_has_milestone_token("body mentions M10 here", "M1"))

    def test_m10_matches_m10(self):
        self.assertTrue(_has_milestone_token("2026-08-23-M10-align.md", "M10"))
        self.assertTrue(_has_milestone_token("M10", "M10"))

    def test_m1_matches_own_token(self):
        for text in ("M1", "2026-08-23-M1-align.md", "milestone M1 closed", "a/M1/b", "M1.md"):
            self.assertTrue(_has_milestone_token(text, "M1"), f"should match: {text!r}")

    def test_token_delimiters(self):
        # 分隔符集：- _ . / 空白 与行首尾
        self.assertTrue(_has_milestone_token("M1-x", "M1"))
        self.assertTrue(_has_milestone_token("M1_x", "M1"))
        self.assertTrue(_has_milestone_token("M1.x", "M1"))
        self.assertTrue(_has_milestone_token("M1/x", "M1"))
        self.assertTrue(_has_milestone_token("M1 x", "M1"))

    def test_substring_without_delimiter_not_matched(self):
        self.assertFalse(_has_milestone_token("AM1B", "M1"))
        self.assertFalse(_has_milestone_token("M12", "M1"))

    def test_empty_milestone_never_matches(self):
        self.assertFalse(_has_milestone_token("anything", ""))
        self.assertFalse(_has_milestone_token("", ""))


class TestIsDocAux(unittest.TestCase):
    def test_aux_names(self):
        for n in ("README.md", "AUTHORING.md", "_template.md"):
            self.assertTrue(_is_doc_aux(n), n)

    def test_dotfiles_are_aux(self):
        self.assertTrue(_is_doc_aux(".schema.json"))
        self.assertTrue(_is_doc_aux(".hidden.md"))

    def test_content_files_not_aux(self):
        self.assertFalse(_is_doc_aux("2026-09-16-fix-x.md"))
        self.assertFalse(_is_doc_aux("0001-arch.md"))
        # LEFTOVERS 不是 doc aux（只在 review 语境算）
        self.assertFalse(_is_doc_aux("LEFTOVERS.md"))


class TestIsReviewAux(unittest.TestCase):
    def test_includes_doc_aux_plus_leftovers(self):
        for n in ("README.md", "AUTHORING.md", "_template.md", "LEFTOVERS.md", "leftovers.md"):
            self.assertTrue(_is_review_aux(n), n)

    def test_review_reports_not_aux(self):
        self.assertFalse(_is_review_aux("2026-09-14-M10-audit.md"))


class TestFilenameMilestone(unittest.TestCase):
    def test_extracts_milestone(self):
        self.assertEqual(_filename_milestone("2026-09-16-M10-fix-x.md"), "M10")
        self.assertEqual(_filename_milestone("M7-quality.md"), "M7")
        self.assertEqual(_filename_milestone("a.M3.b"), "M3")

    def test_case_insensitive(self):
        self.assertEqual(_filename_milestone("2026-09-16-m10-fix.md"), "m10")

    def test_no_milestone(self):
        self.assertIsNone(_filename_milestone("2026-09-16-fix-x.md"))
        self.assertIsNone(_filename_milestone("README.md"))

    def test_embedded_not_matched(self):
        # 需要边界分隔：XM10Y 不算
        self.assertIsNone(_filename_milestone("XM10Y.md"))


if __name__ == "__main__":
    unittest.main()
