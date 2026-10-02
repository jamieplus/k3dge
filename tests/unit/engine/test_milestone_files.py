"""milestone_files: 文件名/评审文件谓词——重点锁 M1 不匹配 M10 的 token 语义。"""
import unittest
from pathlib import Path

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
        from k3dge.engine.milestone_files import _DOC_AUX_NAMES
        self.assertTrue(_is_review_aux(".keep"))
        self.assertTrue(_is_review_aux(".schema.json"))          # 点开头文件名（下发目录里常见）
        # 结构派生：生产常量的每个成员都必须被 review aux 覆盖（新增成员即自动被钉）
        for name in set(_DOC_AUX_NAMES) | {"README.md", "AUTHORING.md", "_template.md", ".DS_Store"}:
            self.assertTrue(_is_doc_aux(name), name)
            self.assertTrue(_is_review_aux(name), f"review aux 必须覆盖 doc aux：{name}")
        for name in _DOC_AUX_NAMES:
            self.assertTrue(_is_review_aux(name), f"_DOC_AUX_NAMES 新增 {name!r} 未被 review 覆盖")

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
        from k3dge.engine import milestone_files as mf_mod
        from k3dge.engine import pure_refs

        # 调 wrapper 与调 pure 对同一样本必须同判（行为超集），且别名内部直达 pure 实现
        samples = [("2026-08-23-M10-align.md", "M1"), ("M10", "M10"), ("m1", "M1"),
                   ("a/M1/b", "M1"), ("M1+x", "M1"), ("anything", "")]
        for text, mid in samples:
            self.assertEqual(_has_milestone_token(text, mid),
                             pure_refs.has_milestone_token(text, mid), (text, mid))
        # 结构断言：别名必须就是同一对象或其 __wrapped__/闭包直达 pure 符号，
        # 复制出第二份判据（即使 docstring 提到 pure）即红
        self.assertIs(_has_milestone_token, pure_refs.has_milestone_token,
                      "别名必须与 pure 实现是同一对象，复制判据即漂移")
        self.assertIs(mf_mod._has_milestone_token, pure_refs.has_milestone_token)


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

    def test_filename_token_boundary_agrees_with_token_predicate(self) -> None:
        """交叉一致：`_filename_milestone` 与 token 谓词的边界类分歧必须显式钉死。
        文件名类窄（无空白/`/`），token 类宽（含空白/`/`）——含空格的 living 报告名
        会走 body 回退，改窄/改宽任一侧都必须先翻此测。"""
        from k3dge.engine import pure_refs
        # 共同子集：两侧都认的必须一致
        for name, mid in [("2026-09-16-M10-fix-x.md", "M10"), ("M7-quality.md", "M7"),
                          ("2026-09-16-fix-x.md", "M10")]:
            tok = pure_refs.has_milestone_token(name, mid)
            fn = _filename_milestone(name)
            if fn is None:
                self.assertFalse(tok, f"{name!r} 文件名无里程碑但 token 命中 {mid}")
            else:
                self.assertTrue(tok, f"{name!r} 文件名抽出 {fn} 但 token 否认 {mid}")
        # 已知分歧：空格/`/` 在 token 侧算边界、文件名侧不算——显式钉住现状
        self.assertTrue(pure_refs.has_milestone_token("2026-09-16 M10 audit.md", "M10"))
        self.assertIsNone(_filename_milestone("2026-09-16 M10 audit.md"),
                          "空格分隔文件名现状不抽取（改动需同步修调用方回退）")
        self.assertTrue(pure_refs.has_milestone_token("a/M10/b", "M10"))
        self.assertIsNone(_filename_milestone("a/M10/b"),
                          "`/` 分隔现状文件名侧不认（调用方走 body 回退）")


class TestAuxCaseInsensitive(unittest.TestCase):
    """小写脚手架不得当内容（ocr2-274）。"""

    def test_lowercase_scaffolding_is_aux(self):
        for n in ("readme.md", "ReadMe.MD", "authoring.md", "_Template.md"):
            self.assertTrue(_is_doc_aux(n), n)
            self.assertTrue(_is_review_aux(n), n)

    def test_leftovers_any_case_is_review_aux(self):
        self.assertTrue(_is_review_aux("LEFTOVERS.md"))
        self.assertTrue(_is_review_aux("Leftovers.MD"))


def _git_repo(ws: Path) -> None:
    import subprocess

    def g(*a: str) -> None:
        r = subprocess.run(["git", "-C", str(ws), *a], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"git {' '.join(a)} 失败：{(r.stderr or r.stdout).strip()}")

    g("init", "-q")
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "seed")


class TestMilestoneTagShape(unittest.TestCase):
    """裸年份 tag 不是里程碑边界（ocr2-276）。"""

    def test_bare_year_excluded(self):
        import tempfile

        from k3dge.engine.milestone_files import milestone_tags

        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            _git_repo(ws)
            import subprocess

            subprocess.run(["git", "-C", str(ws), "tag", "M10"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(ws), "tag", "2024"], check=True, capture_output=True)
            tags = milestone_tags(ws)
            self.assertIn("M10", tags)
            self.assertNotIn("2024", tags)

    def test_git_failure_warns_not_silent(self):
        import contextlib
        import io
        import tempfile

        from k3dge.engine.milestone_files import milestone_tags

        with tempfile.TemporaryDirectory() as d:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                tags = milestone_tags(Path(d))          # 非 git 仓
            self.assertEqual(tags, {})
            self.assertIn("WARN", err.getvalue())


class TestTasksAfterBoundaryKeyCase(unittest.TestCase):
    """frontmatter 键/值大小写 + `*.md` 目录（ocr2-278）。"""

    def test_uppercase_key_and_md_dir(self):
        import subprocess
        import tempfile

        from k3dge.engine.milestone_files import tasks_after_boundary

        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            (ws / "docs" / "tasks").mkdir(parents=True)
            _git_repo(ws)
            subprocess.run(["git", "-C", str(ws), "tag", "M10"], check=True, capture_output=True)
            (ws / "docs" / "tasks" / "a-dir.md").mkdir()          # 同名目录：必须跳过
            (ws / "docs" / "tasks" / "2026-09-20-M10-late.md").write_text(
                "---\nMilestone: M10\nstatus: idea\n---\n# t\n", encoding="utf-8")
            rows = tasks_after_boundary(ws)
            self.assertEqual([r[0] for r in rows], ["docs/tasks/2026-09-20-M10-late.md"])


if __name__ == "__main__":
    unittest.main()
