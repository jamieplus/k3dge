"""抽取器插件新鲜度 + `.agent/docs.toml` 键落点（2026-09-21 补的两个小闸）。"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.evaluator import ConsistencyEngine
from k3dge.engine import extractor_gen


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


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


def _rules(repo: Path) -> list:
    return [v.rule_id for v in ConsistencyEngine(repo).evaluate().violations]


class TestExtractorPluginStale(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _make_repo(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_config(self) -> None:
        # 用内置语言表（`enable` 引用 builtin）：自定义 [languages.*] 行要写全十余个键，测试里不必
        (self.repo / ".agent" / "extractors.toml").write_text(
            '# k3dge extractor config\nenable = ["typescript"]\n', encoding="utf-8"
        )

    def test_missing_plugin_is_violation(self) -> None:
        self._write_config()
        self.assertIn("EXTRACTOR_PLUGIN_STALE", _rules(self.repo))

    def test_fresh_plugin_passes(self) -> None:
        self._write_config()
        extractor_gen.sync_extractors(self.repo)
        self.assertNotIn("EXTRACTOR_PLUGIN_STALE", _rules(self.repo))

    def test_hand_edited_plugin_is_violation(self) -> None:
        self._write_config()
        extractor_gen.sync_extractors(self.repo)
        plug = self.repo / ".agent" / "extractors" / "typescript.py"
        plug.write_text(plug.read_text(encoding="utf-8") + "\n# 手改\n", encoding="utf-8")
        self.assertIn("EXTRACTOR_PLUGIN_STALE", _rules(self.repo))

    def test_no_config_is_not_a_violation(self) -> None:
        self.assertNotIn("EXTRACTOR_PLUGIN_STALE", _rules(self.repo))


class TestDocsTomlKeys(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _make_repo(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_script(self) -> None:
        (self.repo / "scripts").mkdir(exist_ok=True)
        (self.repo / "scripts" / "generate-docs.sh").write_text(
            '#!/usr/bin/env bash\ngen "user_guide"   "docs/guides/user_guide.md"   "User Guide"\n',
            encoding="utf-8",
        )

    def _write_cfg(self, body: str) -> None:
        (self.repo / ".agent" / "docs.toml").write_text(f"[docs]\n{body}", encoding="utf-8")

    def test_unknown_key_is_violation(self) -> None:
        self._write_script()
        self._write_cfg("bogus = true\n")
        self.assertIn("DOCS_TOML_KEY_UNKNOWN", _rules(self.repo))

    def test_known_key_without_file_still_passes(self) -> None:
        """`= true` 而文件未生成是收尾流程常态（`generate-docs.sh` 收尾才落桩）⇒ 不报。"""
        self._write_script()
        self._write_cfg("user_guide = true\n")
        self.assertNotIn("DOCS_TOML_KEY_UNKNOWN", _rules(self.repo))

    def test_readme_key_is_known(self) -> None:
        self._write_script()
        self._write_cfg("readme = true\n")
        self.assertNotIn("DOCS_TOML_KEY_UNKNOWN", _rules(self.repo))


if __name__ == "__main__":
    unittest.main()
