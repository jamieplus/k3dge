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

    def test_delimiter_class_is_exclusive_as_documented(self) -> None:
        r"""边界集是**闭集**（t-156）：文档写明分隔符＝`- _ . /` 空白与行首尾，且**不含 `+`**
        （`M10+` 不是合法 id 形状）。旧测只钉正向＋整段嵌入，把字符类加宽成 `,`/`+`/`\w`
        不会有任何测变红——规则从此比承诺松。前后边界各钉反例，行首/行尾钉正例。"""
        self.assertFalse(_has_milestone_token("M1+x", "M1"))     # `+` 不是分隔符
        self.assertFalse(_has_milestone_token("M1,x", "M1"))
        self.assertFalse(_has_milestone_token("xM1", "M1"))      # 词字符前缀不算边界
        self.assertTrue(_has_milestone_token("-M1", "M1"))       # 行首边界
        self.assertTrue(_has_milestone_token("_M1.", "M1"))
        self.assertTrue(_has_milestone_token("x M1", "M1"))      # 行尾边界

    def test_empty_milestone_never_matches(self):
        self.assertFalse(_has_milestone_token("anything", ""))
        self.assertFalse(_has_milestone_token("", ""))

    def test_token_rule_is_case_insensitive(self):
        """token 侧也钉**大小写不敏感**（t-155）。

        文件名侧 `test_case_insensitive` 早钉过，token 侧此前整组只喂大写——
        ocr-267/304 的病根恰恰是"文件名认 `m10`、token 判 M10 不认"这半条契约
        没进同一套测 ⇒ 本里程碑报告静默漏归档。删掉 `re.IGNORECASE` 现在会红；
        同时"忽略大小写"不得退化成"子串匹配"。
        """
        self.assertTrue(_has_milestone_token("m1", "M1"))
        self.assertTrue(_has_milestone_token("2026-08-23-m10-align.md", "M10"))
        self.assertTrue(_has_milestone_token("M10", "m10"))
        self.assertFalse(_has_milestone_token("m10", "M1"))       # 跨大小写也不许子串命中
        self.assertFalse(_has_milestone_token("AM1B", "m1"))


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
    def test_dotfiles_are_aux_too(self) -> None:
        """`_is_review_aux` 自带 `startswith(".")` 支路（**第二份点文件规则**，t-157）——
        旧测从未穿过它；且"review aux ⊇ doc aux"靠手列名字，`_DOC_AUX_NAMES` 添新成员
        不会有人记得补这边。点文件补测＋**结构派生**的超集断言。"""
        self.assertTrue(_is_review_aux(".keep"))
        self.assertTrue(_is_review_aux(".schema.json"))          # 点开头文件名（下发目录里常见）
        for name in ("README.md", "AUTHORING.md", "_template.md", ".DS_Store"):
            self.assertTrue(_is_doc_aux(name), name)
            self.assertTrue(_is_review_aux(name), f"review aux 必须覆盖 doc aux：{name}")

    def test_includes_doc_aux_plus_leftovers(self):
        for n in ("README.md", "AUTHORING.md", "_template.md", "LEFTOVERS.md", "leftovers.md"):
            self.assertTrue(_is_review_aux(n), n)

    def test_review_reports_not_aux(self):
        self.assertFalse(_is_review_aux("2026-09-14-M10-audit.md"))


class TestAliasAgreesWithSingleSource(unittest.TestCase):
    """`_has_milestone_token` 是委托别名（真身在 `pure_refs`）。测**别名**不等于测两层的
    一致：ocr-304 的病根正是两层各判各的（t-158）。名字公开化属另一批（生产 5 处引用者
    同改）；这里先把"同一函数"钉成契约——有人复制出第二份判据即红。"""

    def test_alias_is_the_same_object_as_pure_impl(self) -> None:
        import inspect

        from k3dge.engine import pure_refs

        # 调 wrapper 与调 pure 对同一样本必须同判（行为超集），且别名内部直达 pure 实现
        samples = [("2026-08-23-M10-align.md", "M1"), ("M10", "M10"), ("m1", "M1"),
                   ("a/M1/b", "M1"), ("M1+x", "M1"), ("anything", "")]
        for text, mid in samples:
            self.assertEqual(_has_milestone_token(text, mid),
                             pure_refs.has_milestone_token(text, mid), (text, mid))
        src = inspect.getsource(_has_milestone_token)
        self.assertIn("pure_refs.has_milestone_token", src, "委托断了？别名不得长出第二判据")


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
