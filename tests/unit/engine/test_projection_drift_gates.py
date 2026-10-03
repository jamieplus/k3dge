"""抽取器插件新鲜度 + `.agent/docs.toml` 键落点（2026-09-21 补的两个小闸）。"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from k3dge.engine.evaluator import ConsistencyEngine
from k3dge.engine import extractor_gen


class _RepoCase(unittest.TestCase):
    """两类共用的脚手架（t-237）：先注册清理、再建仓；环境隔离。

    `evaluate()` 会先跑 `diff.get_changed_files()`——它读继承的 `K3DGE_BASE_SHA`：
    主仓的 base sha 在临时仓里指不到任何提交 ⇒ `GitError`，抽取器/docs.toml 两道闸
    **根本没轮到跑**；届时 `assertNotIn` 全假绿、`assertIn` 因无关原因红。
    与 `test_diff.py` 同约定：测自己钉环境。另外 `_make_repo` 里的 git 一旦中途抛，
    temp 目录必须在**建之前**就登记进 cleanup，否则泄漏。
    """

    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        for k in ("K3DGE_BASE_SHA", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            os.environ.pop(k, None)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = self._make_repo(Path(self._tmp.name))

    @staticmethod
    def _make_repo(tmp: Path) -> Path:
        repo = tmp / "repo"
        repo.mkdir()
        _git(repo, "init", "-b", "main")
        _git(repo, "config", "user.email", "t@example.com")
        _git(repo, "config", "user.name", "tester")
        (repo / ".agent").mkdir()
        (repo / ".agent" / "manifest.json").write_text(
            json.dumps({"package_root": "src", "domains": {}, "ignore": []}), encoding="utf-8"
        )
        return repo

    def _violations(self, rule: str):
        return [v for v in ConsistencyEngine(self.repo).evaluate().violations
                if v.rule_id == rule]


def _git(repo: Path, *args: str) -> None:
    """失败要**带 git 的 stderr**（t-241）：`check=True` 抛的 CalledProcessError 只含命令与
    rc，`capture_output` 又吞了 stderr——git<2.28 不认 `-b`、safe.directory 一类环境病
    全都读成"setup 神秘失败"。"""
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{(r.stderr or r.stdout).strip()}")


def _rules(repo: Path) -> list:
    return [v.rule_id for v in ConsistencyEngine(repo).evaluate().violations]


class TestExtractorPluginStale(_RepoCase):
    def _write_config(self) -> None:
        # 用内置语言表（`enable` 引用 builtin）：自定义 [languages.*] 行要写全十余个键，测试里不必
        (self.repo / ".agent" / "extractors.toml").write_text(
            '# k3dge extractor config\nenable = ["typescript"]\n', encoding="utf-8"
        )

    def _assert_real_stale(self, violations, expect_language: str) -> None:
        """断**结构事实**，不只断闸码（t-238）。

        `_check_extractor_plugins()` 整个函数体包在 `except Exception` 里，崩溃时同样发
        `EXTRACTOR_PLUGIN_STALE`（detail 带 reason、languages＝"（校验崩溃，未定位）"）——
        只 `assertIn(rule)` 的测分不清"真的检测到过期"与"闸自己炸了"。
        """
        self.assertEqual(len(violations), 1, violations)
        det = violations[0].detail or {}
        self.assertNotIn("reason", det, f"闸崩溃冒充了过期报告：{det}")
        self.assertIn(expect_language, str(det.get("languages")))

    def test_missing_plugin_is_violation(self) -> None:
        self._write_config()
        self._assert_real_stale(self._violations("EXTRACTOR_PLUGIN_STALE"), "typescript")

    def test_fresh_plugin_passes(self) -> None:
        self._write_config()
        extractor_gen.sync_extractors(self.repo)
        self.assertNotIn("EXTRACTOR_PLUGIN_STALE", _rules(self.repo))

    def test_hand_edited_plugin_is_violation(self) -> None:
        self._write_config()
        extractor_gen.sync_extractors(self.repo)
        # 路径常量与引擎同源（t-239）：硬编码目录名 ⇒ 常量一改这里就 FileNotFoundError
        # （error，不是本测要断的"过期"），且被测闸从未被触及。前置条件显式断言。
        plug = self.repo / extractor_gen.PLUGDIR_REL / "typescript.py"
        self.assertTrue(plug.is_file(), f"sync 没产出 {plug}——前置条件就不成立")
        plug.write_text(plug.read_text(encoding="utf-8") + "\n# 手改\n", encoding="utf-8")
        self._assert_real_stale(self._violations("EXTRACTOR_PLUGIN_STALE"), "typescript")

    def test_no_config_is_not_a_violation(self) -> None:
        self.assertNotIn("EXTRACTOR_PLUGIN_STALE", _rules(self.repo))


class TestDocsTomlKeys(_RepoCase):
    """`.agent/docs.toml` 的 `= true` 键必须被 `generate-docs.sh` 的 gen 表认领。

    跳过条件（ocr2-767，如实）：`_check_docs_toml` 只在三处静默返回 `[]`——
    `.agent/docs.toml` 缺席、`scripts/generate-docs.sh` 缺席、gen 表解析为空。
    它**不**看 `[docs]` 表头：`enabled` 是整文件正则收的，别表下的键同样被查。
    """

    def _write_script(self) -> None:
        (self.repo / "scripts").mkdir(exist_ok=True)
        (self.repo / "scripts" / "generate-docs.sh").write_text(
            '#!/usr/bin/env bash\ngen "user_guide"   "docs/guides/user_guide.md"   "User Guide"\n',
            encoding="utf-8",
        )

    def _write_cfg(self, body: str) -> None:
        (self.repo / ".agent" / "docs.toml").write_text(f"[docs]\n{body}", encoding="utf-8")

    def _reported_keys(self) -> list:
        return sorted(str((v.detail or {}).get("key", ""))
                      for v in self._violations("DOCS_TOML_KEY_UNKNOWN"))

    def test_unknown_key_is_violation(self) -> None:
        self._write_script()
        self._write_cfg("bogus = true\n")
        self.assertIn("DOCS_TOML_KEY_UNKNOWN", _rules(self.repo))
        self.assertEqual(self._reported_keys(), ["bogus"])

    def test_known_key_without_file_still_passes(self) -> None:
        """`= true` 而文件未生成是收尾流程常态（`generate-docs.sh` 收尾才落桩）⇒ 不报。

        与未知键**同一条 cfg**（t-240）：纯负断言分不清"known 键被认了"与"闸整体没跑"
        （`gen` 正则与脚本形状分叉时 `_check_docs_toml` 直接返回 `[]`）。配对后，
        bogus 必须报、user_guide 必须不报——两条同时成立才证明键表真被建起来了。
        """
        self._write_script()
        self._write_cfg("user_guide = true\nbogus = true\n")
        self.assertEqual(self._reported_keys(), ["bogus"])

    def test_readme_key_is_known(self) -> None:
        self._write_script()
        self._write_cfg("readme = true\nbogus = true\n")
        self.assertEqual(self._reported_keys(), ["bogus"])

    def test_key_under_other_table_is_still_scanned(self) -> None:
        """ocr2-767：整文件扫描的钉子——`[other]` 表下的键同样被查。

        若将来把正则收紧到只扫 `[docs]` 表，本测会红（提醒同步更新闸注释）。
        """
        self._write_script()
        (self.repo / ".agent" / "docs.toml").write_text(
            "[other]\nbogus = true\n", encoding="utf-8")
        self.assertEqual(self._reported_keys(), ["bogus"])


if __name__ == "__main__":
    unittest.main()
