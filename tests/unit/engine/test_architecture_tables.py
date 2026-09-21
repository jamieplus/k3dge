"""设计文档域表 vs manifest（`ARCH_TABLE_DRIFT`）：只比事实列，不比散文。"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.evaluator import ConsistencyEngine

MANIFEST = {
    "package_root": "src",
    "domains": {
        "core": {"src": "src/core", "spec": "docs/specs/core/spec.md", "tests": "tests/unit/core",
                 "depends_on": ["leaf", "extra"], "description": "核心（散文，闸不管）"},
        "leaf": {"src": "src/leaf", "spec": "docs/specs/leaf/spec.md", "tests": "tests/unit/leaf"},
        "extra": {"src": "src/extra", "spec": "docs/specs/extra/spec.md", "tests": "tests/unit/extra"},
    },
    "ignore": [],
}

OVERVIEW_ROWS = (
    "| core | `src/core` | `docs/specs/core/spec.md` | 核心 |\n"
    "| leaf | `src/leaf` | `docs/specs/leaf/spec.md` | 叶子 |\n"
    "| extra | `src/extra` | `docs/specs/extra/spec.md` | 附加 |"
)
ENCY_ROWS = (
    "| `core` | `src/core` | `docs/specs/core/spec.md` | `tests/unit/core` | extra, leaf | 核心 |\n"
    "| `leaf` | `src/leaf` | `docs/specs/leaf/spec.md` | `tests/unit/leaf` | — | 叶子 |\n"
    "| `extra` | `src/extra` | `docs/specs/extra/spec.md` | `tests/unit/extra` | — | 附加 |"
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "tester")
    (repo / ".agent").mkdir()
    (repo / ".agent" / "manifest.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    (repo / "docs" / "architecture").mkdir(parents=True)
    return repo


def _overview(rows: str) -> str:
    return ("# Arch\n\n## 1. 域地图\n\n"
            "| Domain | Source | Spec | Description |\n| --- | --- | --- | --- |\n" + rows + "\n")


def _encyclopedia(rows: str) -> str:
    return ("# Ency\n\n## 2. 域地图\n\n"
            "| Domain | 源码 | 契约 Spec | 测试 | depends_on | 一句话 |\n"
            "| --- | --- | --- | --- | --- | --- |\n" + rows + "\n")


class TestArchitectureTables(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _make_repo(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _rules(self) -> list:
        return [v.rule_id for v in ConsistencyEngine(self.repo).evaluate().violations]

    def _write(self, overview_rows: str = OVERVIEW_ROWS, ency_rows: str = ENCY_ROWS) -> None:
        arch = self.repo / "docs" / "architecture"
        (arch / "overview.md").write_text(_overview(overview_rows), encoding="utf-8")
        (arch / "encyclopedia.md").write_text(_encyclopedia(ency_rows), encoding="utf-8")

    def test_matching_tables_pass(self) -> None:
        self._write()
        self.assertNotIn("ARCH_TABLE_DRIFT", self._rules())

    def test_missing_domain_row_is_violation(self) -> None:
        self._write(overview_rows=OVERVIEW_ROWS.rsplit("\n", 1)[0])
        self.assertIn("ARCH_TABLE_DRIFT", self._rules())

    def test_wrong_src_cell_is_violation(self) -> None:
        self._write(overview_rows=OVERVIEW_ROWS.replace("`src/leaf`", "`src/leafy`"))
        self.assertIn("ARCH_TABLE_DRIFT", self._rules())

    def test_depends_on_is_order_insensitive(self) -> None:
        # 文档写 "extra, leaf"，manifest 是 ["leaf", "extra"] ⇒ 不算漂移
        self.assertIn("extra, leaf", ENCY_ROWS)
        self._write()
        self.assertNotIn("ARCH_TABLE_DRIFT", self._rules())

    def test_depends_on_missing_entry_is_violation(self) -> None:
        self._write(ency_rows=ENCY_ROWS.replace("extra, leaf", "leaf"))
        self.assertIn("ARCH_TABLE_DRIFT", self._rules())

    def test_missing_doc_is_not_a_violation(self) -> None:
        arch = self.repo / "docs" / "architecture"
        (arch / "overview.md").write_text("# Arch\n", encoding="utf-8")
        self.assertNotIn("ARCH_TABLE_DRIFT", self._rules())

    def test_other_tables_are_ignored(self) -> None:
        (self.repo / "docs" / "architecture" / "overview.md").write_text(
            "# Arch\n\n| 术语 | 一句话 |\n| --- | --- |\n| Gate | 闸 |\n", encoding="utf-8"
        )
        self.assertNotIn("ARCH_TABLE_DRIFT", self._rules())


if __name__ == "__main__":
    unittest.main()
