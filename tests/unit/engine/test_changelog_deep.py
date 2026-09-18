"""changelog: Unreleased 追加的边界正确性——条目绝不越界写进已发布版本段。"""
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.changelog import (
    _append_to_unreleased,
    _changelog_draft_path,
    _insert_entry,
    _title_and_section,
)

_UNREL = "## [Unreleased]"


def _ws(d, changelog=None, tasks=()):
    ws = Path(d)
    if changelog is not None:
        (ws / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    tdir = ws / "docs" / "tasks"
    tdir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, body in tasks:
        p = tdir / name
        p.write_text(body, encoding="utf-8")
        paths[name] = p
    return ws, paths


class TestTitleAndSection(unittest.TestCase):
    def test_extracts_h1_title(self):
        with tempfile.TemporaryDirectory() as d:
            ws, paths = _ws(d, tasks=[("2026-09-16-M10-feat-x.md", "# 我的标题\n\n正文\n")])
            title, section = _title_and_section(paths["2026-09-16-M10-feat-x.md"])
            self.assertEqual(title, "我的标题")
            self.assertEqual(section, "Added")

    def test_falls_back_to_stem_without_h1(self):
        with tempfile.TemporaryDirectory() as d:
            ws, paths = _ws(d, tasks=[("2026-09-16-M10-feat-x.md", "没有标题\n")])
            title, _ = _title_and_section(paths["2026-09-16-M10-feat-x.md"])
            self.assertEqual(title, "2026-09-16-M10-feat-x")

    def test_type_to_section_mapping(self):
        cases = [
            ("feat", "Added"), ("fix", "Fixed"), ("audit", "Fixed"),
            ("docs", "Changed"), ("chore", "Changed"), ("refactor", "Changed"),
        ]
        with tempfile.TemporaryDirectory() as d:
            ws, paths = _ws(d, tasks=[(f"2026-09-16-M10-{t}-x.md", "# T\n") for t, _ in cases])
            for t, want in cases:
                _, section = _title_and_section(paths[f"2026-09-16-M10-{t}-x.md"])
                self.assertEqual(section, want, f"type {t}")

    def test_missing_file_uses_stem_and_default(self):
        """路径不含 `docs/tasks/` 时类型正则不匹配 → 默认 fix → Fixed。"""
        title, section = _title_and_section(Path("/nonexistent/2026-09-16-M10-feat-y.md"))
        self.assertEqual(title, "2026-09-16-M10-feat-y")
        self.assertEqual(section, "Fixed")

    def test_draft_path(self):
        self.assertEqual(
            _changelog_draft_path(Path("/w")).as_posix(), "/w/.agent/changelog_draft.md")


class TestInsertEntry(unittest.TestCase):
    def test_creates_subsection_when_absent(self):
        text = f"# Changelog\n\n{_UNREL}\n\n## [0.1.10]\n- old\n"
        idx = text.find(_UNREL)
        nxt = text.find("## [", idx + len(_UNREL))
        out = _insert_entry(text, idx, nxt, "Added", "- new\n")
        self.assertIn("### Added\n- new\n", out)
        # 新条目必须在 Unreleased 与 0.1.10 之间
        self.assertLess(out.index("- new"), out.index("## [0.1.10]"))

    def test_appends_into_existing_subsection(self):
        text = f"{_UNREL}\n\n### Added\n- first\n\n## [0.1.10]\n- old\n"
        idx = text.find(_UNREL)
        nxt = text.find("## [", idx + len(_UNREL))
        out = _insert_entry(text, idx, nxt, "Added", "- second\n")
        # 插入点在下一个 section 标记之前（故与 - first 之间可能隔空行）
        self.assertIn("- second", out)
        self.assertLess(out.index("- first"), out.index("- second"))
        self.assertLess(out.index("- second"), out.index("## [0.1.10]"))
        self.assertEqual(out.count("### Added"), 1, "不得重复建 subsection")

    def test_never_crosses_into_released_version(self):
        """核心不变量：已有版本段里没有该 subsection 时，绝不往那段插。"""
        text = f"{_UNREL}\n\n## [0.1.10]\n\n### Fixed\n- old fix\n"
        idx = text.find(_UNREL)
        nxt = text.find("## [", idx + len(_UNREL))
        out = _insert_entry(text, idx, nxt, "Fixed", "- new fix\n")
        self.assertLess(out.index("- new fix"), out.index("## [0.1.10]"),
                        "新条目泄漏进已发布版本段")

    def test_inserts_before_next_subsection(self):
        text = f"{_UNREL}\n\n### Added\n- a\n\n### Fixed\n- f\n\n## [0.1.10]\n"
        idx = text.find(_UNREL)
        nxt = text.find("## [", idx + len(_UNREL))
        out = _insert_entry(text, idx, nxt, "Added", "- a2\n")
        self.assertLess(out.index("- a2"), out.index("### Fixed"))

    def test_no_next_version_marker(self):
        text = f"{_UNREL}\n\n### Added\n- a\n"
        idx = text.find(_UNREL)
        out = _insert_entry(text, idx, -1, "Added", "- b\n")
        self.assertIn("- a\n- b\n", out)


class TestAppendToUnreleased(unittest.TestCase):
    def test_no_changelog_is_noop_true(self):
        with tempfile.TemporaryDirectory() as d:
            ws, paths = _ws(d, tasks=[("2026-09-16-M10-feat-x.md", "# T\n")])
            self.assertTrue(_append_to_unreleased(ws, paths["2026-09-16-M10-feat-x.md"]))
            self.assertFalse((ws / "CHANGELOG.md").exists())

    def test_no_unreleased_section_is_noop_true(self):
        with tempfile.TemporaryDirectory() as d:
            ws, paths = _ws(d, changelog="# Changelog\n\n## [0.1.10]\n- old\n",
                            tasks=[("2026-09-16-M10-feat-x.md", "# T\n")])
            self.assertTrue(_append_to_unreleased(ws, paths["2026-09-16-M10-feat-x.md"]))
            self.assertNotIn("### Added", (ws / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_appends_entry(self):
        with tempfile.TemporaryDirectory() as d:
            ws, paths = _ws(d, changelog=f"# C\n\n{_UNREL}\n\n## [0.1.10]\n- old\n",
                            tasks=[("2026-09-16-M10-feat-x.md", "# 新功能\n")])
            self.assertTrue(_append_to_unreleased(ws, paths["2026-09-16-M10-feat-x.md"]))
            out = (ws / "CHANGELOG.md").read_text(encoding="utf-8")
            self.assertIn("### Added\n- 新功能\n", out)

    def test_idempotent_no_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            ws, paths = _ws(d, changelog=f"# C\n\n{_UNREL}\n\n## [0.1.10]\n",
                            tasks=[("2026-09-16-M10-feat-x.md", "# 新功能\n")])
            p = paths["2026-09-16-M10-feat-x.md"]
            _append_to_unreleased(ws, p)
            _append_to_unreleased(ws, p)
            out = (ws / "CHANGELOG.md").read_text(encoding="utf-8")
            self.assertEqual(out.count("- 新功能"), 1)

    def test_same_title_in_old_version_still_appends(self):
        """去重只在 Unreleased 段内判定；旧版本里有同名条目不该阻止新增。"""
        with tempfile.TemporaryDirectory() as d:
            ws, paths = _ws(
                d,
                changelog=f"# C\n\n{_UNREL}\n\n## [0.1.10]\n\n### Added\n- 新功能\n",
                tasks=[("2026-09-16-M10-feat-x.md", "# 新功能\n")])
            self.assertTrue(_append_to_unreleased(ws, paths["2026-09-16-M10-feat-x.md"]))
            out = (ws / "CHANGELOG.md").read_text(encoding="utf-8")
            unreleased_block = out[out.find(_UNREL):out.find("## [0.1.10]")]
            self.assertIn("- 新功能", unreleased_block)


if __name__ == "__main__":
    unittest.main()
