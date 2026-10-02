import json
import os
import tempfile
import unittest
from pathlib import Path

from k3dge.templates.scaffold import scaffold




class TestScaffoldProblemsChannel(unittest.TestCase):
    """脚手架的失败必须有通道：执行位可补、坏输入出声、用户键不被抹（ocr-368..372）。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name) / "p"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_exec_bit_is_restored_on_existing_file(self) -> None:
        """公开行为从公开入口验（t-333）。

        旧测直接调私有 `_write_if_missing`：①`scaffold()` 哪天不再对 gate.sh 传
        `executable=True`（类 docstring 承诺的"重跑 init 修回执行位"没了），旧测照绿；
        ②内部改名它就先红。现在跑**两遍真 scaffold()**；mode 位在 Windows/部分挂载
        文件系统上不承载 ⇒ 相应环境显式 skip，而不是记错误导。
        """
        if os.name == "nt":
            self.skipTest("exec 位语义不适用于 Windows")
        problems = scaffold(self.target, name="p")
        self.assertEqual([m for m in problems if "gate" in m], [], problems)
        f = self.target / "scripts" / "gate.sh"
        self.assertTrue(f.is_file(), "scaffold 未下发 scripts/gate.sh")
        if not (os.stat(f).st_mode & 0o111):
            self.skipTest("本文件系统不承载 exec 位（挂载选项/umask）")
        f.chmod(0o644)                      # 模拟跨 fs/checkout 丢 mode
        content_before = f.read_text(encoding="utf-8")
        problems2 = scaffold(self.target, name="p")     # 重跑＝公开幂等面
        self.assertEqual([m for m in problems2 if "gate" in m], [], problems2)
        self.assertTrue(os.stat(f).st_mode & 0o111, "重复跑 init 永远修不回执行位")
        self.assertEqual(f.read_text(encoding="utf-8"), content_before)   # 内容不动

    def test_manifest_problems_come_back_in_the_channel(self) -> None:

        (self.target / ".agent").mkdir(parents=True)
        (self.target / ".agent" / "manifest.json").write_text("{ 坏 json", encoding="utf-8")
        problems = scaffold(self.target, name="p")
        self.assertTrue([m for m in problems if "manifest.json" in m], problems)

    def test_user_keys_survive_domain_upgrade(self) -> None:

        (self.target / ".agent").mkdir(parents=True)
        (self.target / ".agent" / "manifest.json").write_text(json.dumps({
            "name": "old", "package_root": "lib", "ignore": ["vendor/**"],
            "version": "9.9.9", "self_hosting": True, "domains": {}}) + "\n", encoding="utf-8")
        self.assertEqual(scaffold(self.target, name="p"), [])
        data = json.loads((self.target / ".agent" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(data["package_root"], "lib")
        self.assertEqual(data["ignore"], ["vendor/**"])
        self.assertEqual(data["version"], "9.9.9")
        self.assertTrue(data["self_hosting"])
        self.assertIn("p", data["domains"])
        # 新域条目与保留键**内部一致**（t-335/t-338）：旧实现在 package_root=lib 时
        # 把域写成 `src/p`、包也铺在 src/ 下——本测只验"键没被抹"，等于给自相矛盾的
        # 清单发了合格证。域 src 与落盘位置都跟 package_root 走。
        self.assertEqual(data["domains"]["p"]["src"], "lib/p")
        self.assertTrue((self.target / "lib" / "p" / "__init__.py").is_file())
        self.assertFalse((self.target / "src" / "p").exists(), "package_root=lib 不得往 src/ 铺包")

    def test_corrupt_mcp_json_is_a_problem(self) -> None:

        self.target.mkdir(parents=True)
        (self.target / ".mcp.json").write_text("{ nope", encoding="utf-8")
        problems = scaffold(self.target, name="p")
        self.assertTrue([m for m in problems if ".mcp.json" in m], problems)
        # 契约的破坏面（t-334）：`False` 的存在理由＝"跳过、不改写"以免抹掉 peers——
        # 只断"有 problem"的话，"从空 dict 重写 `.mcp.json`"的回归同样有 problem 照样绿。
        self.assertEqual((self.target / ".mcp.json").read_bytes(), b"{ nope",
                         "坏文件被重写＝用户的对端配置没了")
class TestScaffold(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name) / "project"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_generates_tree(self) -> None:
        scaffold(self.target)
        self.assertTrue((self.target / ".agent" / "manifest.json").exists())
        self.assertTrue((self.target / "AGENTS.md").exists())
        self.assertTrue((self.target / ".pre-commit-config.yaml").exists())
        self.assertTrue((self.target / "docs" / "specs" / "_template" / "spec.md").exists())
        self.assertTrue((self.target / "docs" / "adr").is_dir())
        self.assertTrue((self.target / "docs" / "tasks").is_dir())
        self.assertTrue((self.target / "docs" / "guides").is_dir())
        self.assertTrue((self.target / "docs" / "generated").is_dir())
        # 旧这里把 `docs/tasks` 又断了一遍（t-336）——受管面真正没被点名的是协议/架构/分支/备忘：
        self.assertTrue((self.target / "docs" / "protocols").is_dir())
        self.assertTrue((self.target / "docs" / "architecture").is_dir())
        self.assertTrue((self.target / "docs" / "branches").is_dir())
        self.assertTrue((self.target / "docs" / "memo").is_dir())
        self.assertTrue((self.target / "docs" / "tasks" / "README.md").exists())
        self.assertTrue((self.target / "docs" / "adr" / ".schema.json").is_file())
        self.assertTrue((self.target / "docs" / "adr" / "AUTHORING.md").is_file())
        self.assertTrue((self.target / "docs" / "tasks" / ".schema.json").is_file())
        self.assertTrue((self.target / "docs" / "tasks" / "AUTHORING.md").is_file())
        self.assertTrue((self.target / "docs" / "memo" / ".schema.json").is_file())
        self.assertTrue((self.target / "docs" / "branches" / ".schema.json").is_file())

        manifest = json.loads((self.target / ".agent" / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("domains", manifest)
        self.assertIn("project", manifest["domains"])
        self.assertTrue((self.target / "src" / "project" / "__init__.py").is_file())
        self.assertTrue((self.target / "docs" / "specs" / "project" / "spec.md").is_file())
        self.assertTrue((self.target / "docs" / "guides" / "mcp-bridge.md").is_file())
        self.assertTrue((self.target / "docs" / "guides" / "downstream.md").is_file())
        self.assertTrue((self.target / ".gitignore").is_file())
        reviews = (self.target / "docs" / "reviews" / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("2026-08-25-pass1", reviews)
        leftovers = self.target / "docs" / "reviews" / "LEFTOVERS.md"
        self.assertTrue(leftovers.is_file())
        self.assertNotIn("2026-08-25-pass1", leftovers.read_text(encoding="utf-8"))
        self.assertIn("LEFTOVERS.md", reviews)

        readme = self.target / ".agent" / "README.md"
        self.assertTrue(readme.exists())
        self.assertIn("机器配置目录", readme.read_text(encoding="utf-8"))

        for name in (
            "00-core-discipline.md",
            "01-docs-structure.md",
            "02-simplification.md",
            "03-self-contained.md",
        ):
            path = self.target / ".agent" / "rules" / name
            self.assertTrue(path.exists(), name)
            text = path.read_text(encoding="utf-8")
            self.assertGreater(len(text.strip()), 80, name)
            self.assertIn("ADR-0010", text)
        two = (self.target / ".agent" / "rules" / "02-simplification.md").read_text(encoding="utf-8")
        self.assertIn("procedural discipline", two)
        zero = (self.target / ".agent" / "rules" / "00-core-discipline.md").read_text(
            encoding="utf-8").strip()
        self.assertNotEqual(zero, "# Rule 00: Core Discipline")

    def test_scripts_are_executable(self) -> None:
        scaffold(self.target)
        gate = self.target / "scripts" / "gate.sh"
        init = self.target / "k3dge-init.sh"
        self.assertTrue(os.access(gate, os.X_OK))
        self.assertTrue(os.access(init, os.X_OK))

    def test_idempotent(self) -> None:
        scaffold(self.target)
        agents = self.target / "AGENTS.md"
        agents.write_text("custom", encoding="utf-8")
        scaffold(self.target)
        self.assertEqual(agents.read_text(encoding="utf-8"), "custom")

    def test_empty_manifest_upgraded_to_first_domain(self) -> None:
        (self.target / ".agent").mkdir(parents=True)
        (self.target / ".agent" / "manifest.json").write_text(
            json.dumps(
                {
                    "name": "project",
                    "version": "0.1.0",
                    "package_root": "src",
                    "domains": {},
                    "ignore": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        scaffold(self.target, name="k3dit")
        data = json.loads((self.target / ".agent" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "k3dit")
        self.assertIn("k3dit", data["domains"])
        self.assertTrue((self.target / "src" / "k3dit" / "__init__.py").is_file())

    def test_pipeline_peers_declared_so_birth_not_red(self) -> None:
        """item 3：scaffold 把 pipeline 绑定的 peer 以 stub 写进 .mcp.json，出生不报 PIPELINE_PEER_UNWIRED。"""
        from k3dge.engine.pipeline_schema import validate_pipeline_config

        scaffold(self.target)
        servers = json.loads((self.target / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
        self.assertIn("k3dge", servers)
        self.assertIn("k3dit", servers)  # pipeline 绑定的 peer 已登记
        self.assertIn("k3che", servers)
        codes = [c for c, _ in validate_pipeline_config(self.target)]
        self.assertNotIn("PIPELINE_PEER_UNWIRED", codes, validate_pipeline_config(self.target))


class TestSlugAndPackageRoot(unittest.TestCase):
    def test_slug_rejects_keywords_and_stdlib(self) -> None:
        # 关键字/标准库名做包名会语法错或影子标准库（ocr2-107）；与数字开头同法加前缀。
        from k3dge.templates.scaffold import _slug

        self.assertEqual(_slug("class"), "p_class")
        self.assertEqual(_slug("os"), "p_os")
        self.assertEqual(_slug("my-app"), "my_app")

    def test_package_root_traversal_falls_back(self) -> None:
        # manifest 的 package_root 含 `..`/绝对路径 ⇒ 回落 src，不铺出仓（ocr2-108）。
        import json

        from k3dge.templates import scaffold as sc

        with self.subTest("parent-escape"):
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as d:
                target = Path(d)
                (target / ".agent").mkdir(parents=True)
                (target / ".agent" / "manifest.json").write_text(
                    json.dumps({"package_root": "../evil", "domains": {}}), encoding="utf-8")
                sc._ensure_first_domain(target, "p", "2026-10-02")
                data = json.loads((target / ".agent" / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(data["domains"]["p"]["src"], "src/p")
                self.assertFalse((target / "evil").exists())
                self.assertFalse((target.parent / "evil").exists())


if __name__ == "__main__":
    unittest.main()
