import json
import tempfile
import unittest
from pathlib import Path

from k3dge.engine import contract
from k3dge.engine.manifest import Manifest
from k3dge.sync.generator import render_readme_layout, sync_all
import shutil

SPEC = """# Domain Specification: core
- **Status**: Active
- **Module Path**: `src/core`
- **Contract Hash**:
- **Last Updated**: 2026-08-19
## 1. Domain Boundary & Responsibilities
## 2. Public Interfaces & Type Contracts
<!-- k3dge:interfaces-start -->
```python
```
<!-- k3dge:interfaces-end -->
## 3. State Machine & Invariants
## 4. Verification Matrix
"""


class TestGenerator(unittest.TestCase):
    def test_sync_writes_hash_and_interface(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text(
                json.dumps(
                    {
                        "package_root": "src",
                        "domains": {
                            "core": {"src": "src/core", "spec": "docs/specs/core/spec.md"}
                        },
                        "ignore": [],
                    }
                )
            , encoding="utf-8")
            (root / "src" / "core").mkdir(parents=True)
            (root / "src" / "core" / "mod.py").write_text(
                "def foo(x: int) -> int:\n    return x\n"
            , encoding="utf-8")
            (root / "docs" / "specs" / "core").mkdir(parents=True)
            spec = root / "docs" / "specs" / "core" / "spec.md"
            spec.write_text(SPEC, encoding="utf-8")

            changed, docs_updated = sync_all(root)
            self.assertEqual(changed, ["core"])
            # manual docs are machine-generated under docs/generated/ (no agent needed, Diátaxis Reference)
            self.assertTrue(docs_updated)
            self.assertTrue((root / "docs/generated/api.md").exists())
            self.assertTrue((root / "docs/generated/domains.md").exists())

            content = spec.read_text(encoding="utf-8")
            iface = contract.collect_domain_interface(root / "src" / "core")
            h = contract.compute_hash(iface)
            self.assertIn(f"sha256:{h}", content)
            self.assertNotIn("# mod.py", content)
            self.assertIn("foo(x: int) -> int", content)
            api = (root / "docs/generated/api.md").read_text(encoding="utf-8")
            self.assertIn("# mod.py", api)

    def test_empty_domains_selects_empty_target_set(self) -> None:
        """ocr2-677：显式空选择（MCP `{"domains": []}`）＝空目标集，不得回落成全量同步。"""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text(
                json.dumps(
                    {
                        "package_root": "src",
                        "domains": {
                            "core": {"src": "src/core", "spec": "docs/specs/core/spec.md"}
                        },
                        "ignore": [],
                    }
                )
            , encoding="utf-8")
            (root / "src" / "core").mkdir(parents=True)
            (root / "src" / "core" / "mod.py").write_text(
                "def foo(x: int) -> int:\n    return x\n"
            , encoding="utf-8")
            (root / "docs" / "specs" / "core").mkdir(parents=True)
            spec = root / "docs" / "specs" / "core" / "spec.md"
            spec.write_text(SPEC, encoding="utf-8")
            before = spec.read_text(encoding="utf-8")

            changed, _docs_updated = sync_all(root, domains=[])
            self.assertEqual(changed, [])
            # 空目标集 ⇒ 域 spec 逐字节不动（回落全量会重写接口块+哈希）
            self.assertEqual(spec.read_text(encoding="utf-8"), before)

    def test_render_readme_layout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text(
                json.dumps(
                    {
                        "package_root": "src",
                        "domains": {
                            "core": {
                                "src": "src/core",
                                "spec": "docs/specs/core/spec.md",
                                "description": "核心模块",
                            }
                        },
                        "ignore": [],
                    }
                )
            , encoding="utf-8")
            readme = root / "README.md"
            readme.write_text(
                "# T\n\n## 布局\n\n<!-- k3dge:layout-start -->\nold content\n<!-- k3dge:layout-end -->\n",
                encoding="utf-8",       # 夹具含非 ASCII（"布局"）：不写 encoding 就随 locale 崩/串码（t-303）
            )

            manifest = Manifest.load(root)
            result = render_readme_layout(root, manifest)
            self.assertEqual(result, readme)
            content = readme.read_text(encoding="utf-8")
            self.assertIn("| core | `src/core` | `docs/specs/core/spec.md` | 核心模块 |", content)
            self.assertNotIn("old content", content)

            # ocr2-805：幂等只断返回值时，第二遍重写/截断/丢临时兄弟也照样绿——
            # 这是 no-op 路径的唯一覆盖。重读断内容逐字节不动、无残留临时件。
            siblings_before = sorted(p.name for p in readme.parent.iterdir())
            self.assertIsNone(render_readme_layout(root, manifest))
            self.assertEqual(readme.read_text(encoding="utf-8"), content)
            self.assertIn("| core | `src/core` | `docs/specs/core/spec.md` | 核心模块 |",
                          readme.read_text(encoding="utf-8"))
            self.assertNotIn("old content", readme.read_text(encoding="utf-8"))
            self.assertEqual(sorted(p.name for p in readme.parent.iterdir()), siblings_before,
                             "第二遍渲染留下临时兄弟文件")



    def test_unreadable_spec_warns_instead_of_silent_skip(self) -> None:
        """非 UTF-8 spec 以前被完全静默吞掉 ⇒ 每轮无声跳过，闸一直红而无定位信息（340）。

        ocr2-546：断言改 `self.assert*`（`-O` 不剥），钉**专属**标记 `读不出` + 出错路径，
        并证明 spec 字节未被改写。
        """
        import contextlib
        import io

        from k3dge.sync.generator import sync_domain

        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        (ws / ".agent").mkdir()
        (ws / ".agent" / "manifest.json").write_text(
            json.dumps({"package_root": "src", "domains": {
                "engine": {"src": "src/demo", "spec": "docs/specs/engine/spec.md"}}}), encoding="utf-8")
        (ws / "src" / "demo").mkdir(parents=True)
        (ws / "src" / "demo" / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        spec = ws / "docs" / "specs" / "engine" / "spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_bytes(b"\xff\xfe not utf8")
        before = spec.read_bytes()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            got = sync_domain(ws, Manifest.load(ws), "engine")
        self.assertIsNone(got)
        text = err.getvalue()
        self.assertIn("读不出", text)               # 专属分支标记，不用宽泛的 WARN/跳过该域
        self.assertIn(str(spec), text)              # 出错路径必须点名
        self.assertEqual(spec.read_bytes(), before, "读不出的 spec 被改写了")

    def test_atomic_write_does_not_truncate_target_on_failure(self) -> None:
        """就地 `write_text` 先截断；崩在半路把受管事实源留在空/半截状态（341）。

        实现改用 `mkstemp` 的 fd 直写（ocr2-186：不要关 fd 再按名重开）后，判据改核
        **性质**：载荷先写进同目录的兄弟临时件，再 `replace` 顶上；target 从不被就地写。
        """
        from unittest import mock

        from k3dge.engine.atomic import atomic_write_text

        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        target = ws / "spec.md"
        target.write_text("原文\n", encoding="utf-8")

        replaced: list = []
        real_replace = Path.replace

        def spy_replace(self, dst, *a, **k):
            # ocr2-806：记全路径——旧版只记 `self.name`（basename），写到别的
            # 目录的同名 spec.md 也满足"源名 ≠ 目标名"，真文件身份从没被断。
            replaced.append((str(self), str(dst)))
            return real_replace(self, dst, *a, **k)

        with mock.patch.object(Path, "replace", spy_replace):
            atomic_write_text(target, "新内容\n")
        # 源恒为同目录临时件，dst 才是 target ⇒ 从不就地写 target
        self.assertTrue(replaced, replaced)
        self.assertTrue(all(Path(src).parent == ws and Path(src).name != target.name
                            for src, _dst in replaced), replaced)
        self.assertTrue(any(dst == str(target) for _src, dst in replaced), replaced)
        self.assertEqual(target.read_text(encoding="utf-8"), "新内容\n")
        self.assertFalse([p for p in ws.iterdir() if p.name.startswith("." + target.name)])

        # 写阶段失败（fd 写不下去）⇒ target 保持旧内容，临时件清理干净
        with mock.patch("os.fdopen", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                atomic_write_text(target, "半截")
        self.assertEqual(target.read_text(encoding="utf-8"), "新内容\n")
        self.assertFalse([p for p in ws.iterdir() if p.name.startswith("." + target.name)])

        # ocr2-547：载荷已写进临时件、`replace` 顶上时失败——target 不得被截断，
        # 失败路径的临时候选也要清干净（旧夹具在 fd 写前就炸，验不到这一段）。
        with mock.patch.object(Path, "replace", side_effect=OSError("EIO")):
            with self.assertRaises(OSError):
                atomic_write_text(target, "半截")
        self.assertEqual(target.read_text(encoding="utf-8"), "新内容\n")
        self.assertFalse([p for p in ws.iterdir() if p.name.startswith("." + target.name)],
                         "replace 失败后临时件残留")

    def test_atomic_write_cleans_tmp_on_keyboard_interrupt(self) -> None:
        """ocr2-187：`except Exception` 接不住 KeyboardInterrupt ⇒ 临时件会永久残留。"""
        from unittest import mock

        from k3dge.engine.atomic import atomic_write_text

        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        target = ws / "spec.md"
        target.write_text("原文\n", encoding="utf-8")
        with mock.patch("os.fdopen", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                atomic_write_text(target, "半截")
        assert target.read_text(encoding="utf-8") == "原文\n"
        assert not [p for p in ws.iterdir() if p.name.startswith("." + target.name)], \
            "KeyboardInterrupt 后临时件残留"

    def test_identical_interface_still_refreshes_hash(self) -> None:
        """ocr2-342：markers 在、生成块逐字节相同 ⇒ 仍须刷哈希/日期，不得静默 return None。"""
        import re as _re

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text(json.dumps({
                "package_root": "src",
                "domains": {"core": {"src": "src/core", "spec": "docs/specs/core/spec.md"}},
                "ignore": []}, ensure_ascii=False), encoding="utf-8")
            (root / "src" / "core").mkdir(parents=True)
            (root / "src" / "core" / "mod.py").write_text("def foo(x: int) -> int:\n    return x\n",
                                                          encoding="utf-8")
            (root / "docs" / "specs" / "core").mkdir(parents=True)
            spec = root / "docs" / "specs" / "core" / "spec.md"
            spec.write_text(SPEC, encoding="utf-8")

            sync_all(root)
            good = spec.read_text(encoding="utf-8")
            iface = contract.collect_domain_interface(root / "src" / "core")
            h = contract.compute_hash(iface)
            # 只改哈希行（接口块保持逐字节相同）⇒ 修复前 sync 会静默返回 None 永远不愈合
            spec.write_text(_re.sub(r"sha256:[0-9a-f]+", "sha256:" + "0" * 64, good),
                            encoding="utf-8")
            sync_all(root)
            self.assertIn(f"sha256:{h}", spec.read_text(encoding="utf-8"))

    def test_registry_domains_step_precollects_only_requested(self) -> None:
        """ocr2-343b：`sync --domain x` 的注册表预采只覆盖本轮目标域。"""
        from unittest import mock

        from k3dge.sync.generator import _sync_registry

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text(json.dumps({
                "package_root": "src",
                "domains": {
                    "core": {"src": "src/core", "spec": "docs/specs/core/spec.md"},
                    "other": {"src": "src/other", "spec": "docs/specs/other/spec.md"},
                }, "ignore": []}, ensure_ascii=False), encoding="utf-8")
            for dom in ("core", "other"):
                (root / "src" / dom).mkdir(parents=True)
                (root / "src" / dom / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
                (root / "docs" / "specs" / dom).mkdir(parents=True)
                (root / "docs" / "specs" / dom / "spec.md").write_text(
                    SPEC.replace("core", dom), encoding="utf-8")

            real = contract.collect_domain_interface
            seen: list = []

            def spy(src_dir, *a, **k):
                seen.append(str(src_dir))
                return real(src_dir, *a, **k)

            ctx = {"workspace": root, "manifest": Manifest.load(root),
                   "domains": ["core"], "changed": []}
            with mock.patch.object(contract, "collect_domain_interface", side_effect=spy):
                ok, _msg = _sync_registry()["sync_domains"](ctx)
            self.assertTrue(ok)
            # core 采两次（clean + doc），other 一次都不采
            self.assertFalse([s for s in seen if "other" in s], seen)


class TestSyncAbortPropagates(unittest.TestCase):
    def test_sync_all_raises_when_a_node_aborts(self) -> None:
        # 中止不许回落成"成功形"返回值（ocr2-005）：调用方无法区分"跑完无改动"与"中途掐断。
        from k3dge.engine import nodes
        from k3dge.sync import generator as gen

        orig = nodes.run_phase
        nodes.run_phase = lambda *a, **k: (False, "boom")
        try:
            with self.assertRaises(RuntimeError):
                with tempfile.TemporaryDirectory() as d:
                    root = Path(d)
                    (root / ".agent").mkdir()
                    (root / ".agent" / "manifest.json").write_text(
                        json.dumps({"package_root": "src", "domains": {}, "ignore": []}),
                        encoding="utf-8")
                    gen.sync_all(root)
        finally:
            nodes.run_phase = orig


if __name__ == "__main__":
    unittest.main()
