"""设计文档域表 vs manifest（`ARCH_TABLE_DRIFT`）：只比事实列，不比散文。"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
    # 建**基线提交**（t-068）：旧 fixture 停在 unborn HEAD——change-set 只能靠
    # resolve_base() 逐级回落到 "HEAD" 才不炸，恰是 K3DGE_BASE_SHA 被导出时最脆的路；
    # 身份 config 此前是给"没人跑的 commit"用的（死配置），现在真用了。
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
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
        # 环境隔离（t-065）：`evaluate()` 先走 `diff.get_changed_files()`——继承的
        # K3DGE_BASE_SHA 在这个无提交的临时仓上让 git diff 失败 ⇒ 早退只回
        # GIT_UNAVAILABLE，域表闸**根本没跑**，四条 assertNotIn 全是 vacuous。
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("K3DGE_BASE_SHA", None)
        os.environ.pop("GIT_DIR", None)
        self.repo = _make_repo(Path(self._tmp.name))

    def _rules(self) -> list:
        return [v.rule_id for v in ConsistencyEngine(self.repo).evaluate().violations]

    def _rules_gate_ran(self) -> list:
        """负测专用：先证本闸可达（t-065），再说"没漂移"。"""
        rules = self._rules()
        self.assertNotIn("GIT_UNAVAILABLE", rules, "闸没跑到——负断言在此 vacuous")
        self.assertNotIn("MANIFEST_INVALID", rules, "闸没跑到——负断言在此 vacuous")
        self.assertNotIn("ARCH_TABLE_DRIFT", rules)
        return rules

    def _write(self, overview_rows: str = OVERVIEW_ROWS, ency_rows: str = ENCY_ROWS) -> None:
        arch = self.repo / "docs" / "architecture"
        (arch / "overview.md").write_text(_overview(overview_rows), encoding="utf-8")
        (arch / "encyclopedia.md").write_text(_encyclopedia(ency_rows), encoding="utf-8")

    def test_matching_tables_pass(self) -> None:
        self._write()
        self._rules_gate_ran()

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
        self._rules_gate_ran()

    def test_prose_column_differences_do_not_drift(self) -> None:
        """模块承诺"**只比事实列，不比散文**"——此前没有专属测（t-067：旧第二测与
        `test_matching_tables_pass` 逐字同场景，只多了个 fixture 守卫）。把两份表的
        描述列全部改花：仍不得报漂移。"""
        self._write(overview_rows=OVERVIEW_ROWS.replace("核心", "核心——随手改的散文")
                                                  .replace("叶子", "leaf? 反正散文")
                                                  .replace("附加", ""))
        self._rules_gate_ran()          # 内部已断"可达且无 ARCH_TABLE_DRIFT"
        self._write(ency_rows=ENCY_ROWS.replace("核心", "K")
                                       .replace("叶子", "L").replace("附加", "E"))
        self._rules_gate_ran()

    def test_wrong_spec_cell_is_violation(self) -> None:
        """事实列逐列钉（t-066）：旧测只动 src 与 depends_on——把比较集从
        ("src","spec") 摘掉 spec、或 encyclopedia 四元组被裁窄，旧测全绿。"""
        self._write(overview_rows=OVERVIEW_ROWS.replace("docs/specs/core/spec.md",
                                                        "docs/specs/core/other.md"))
        self.assertIn("ARCH_TABLE_DRIFT", self._rules())

    def test_wrong_tests_cell_in_encyclopedia_is_violation(self) -> None:
        self._write(ency_rows=ENCY_ROWS.replace("`tests/unit/core`", "`tests/unit/corex`"))
        self.assertIn("ARCH_TABLE_DRIFT", self._rules())

    def test_depends_on_missing_entry_is_violation(self) -> None:
        self._write(ency_rows=ENCY_ROWS.replace("extra, leaf", "leaf"))
        self.assertIn("ARCH_TABLE_DRIFT", self._rules())

    def test_missing_doc_is_not_a_violation(self) -> None:
        # "表没写"是合法状态（闸只在**写了半张表**时判）——可达性仍要证（t-065），
        # 否则这条测退化成"evaluate 早退了，恭喜"。
        arch = self.repo / "docs" / "architecture"
        (arch / "overview.md").write_text("# Arch\n", encoding="utf-8")
        rules = self._rules()
        self.assertNotIn("GIT_UNAVAILABLE", rules)
        self.assertNotIn("ARCH_TABLE_DRIFT", rules)

    def test_other_tables_are_ignored(self) -> None:
        (self.repo / "docs" / "architecture" / "overview.md").write_text(
            "# Arch\n\n| 术语 | 一句话 |\n| --- | --- |\n| Gate | 闸 |\n", encoding="utf-8"
        )
        self.assertNotIn("ARCH_TABLE_DRIFT", self._rules())


if __name__ == "__main__":
    unittest.main()
