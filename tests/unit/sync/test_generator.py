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

            self.assertIsNone(render_readme_layout(root, manifest))



    def test_unreadable_spec_warns_instead_of_silent_skip(self) -> None:
        """非 UTF-8 spec 以前被完全静默吞掉 ⇒ 每轮无声跳过，闸一直红而无定位信息（340）。"""
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
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            got = sync_domain(ws, Manifest.load(ws), "engine")
        assert got is None
        assert "WARN" in err.getvalue() and "跳过该域" in err.getvalue()

    def test_atomic_write_does_not_truncate_target_on_failure(self) -> None:
        """就地 `write_text` 先截断；崩在半路把受管事实源留在空/半截状态（341）。"""
        from unittest import mock

        from k3dge.engine.atomic import atomic_write_text

        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        target = ws / "spec.md"
        target.write_text("原文\n", encoding="utf-8")

        # 只桩"写目标本身"是不够的：真实现根本不碰 target，所以原地实现的截断也不会被暴露。
        # 这里核的是**性质**：载荷先写进同目录的兄弟临时件，再 os.replace 顶上。
        written: list = []
        real = Path.write_text

        def spy(self, data, *a, **k):
            written.append(self.name)
            return real(self, data, *a, **k)

        with mock.patch.object(Path, "write_text", spy):
            atomic_write_text(target, "新内容\n")
        assert written and all(n != target.name for n in written), written   # 从不就地写 target
        assert target.read_text(encoding="utf-8") == "新内容\n"
        assert not [p for p in ws.iterdir() if p.name.endswith(".tmp")] or \
            all(p.name != target.name for p in ws.iterdir())

        with mock.patch.object(Path, "write_text", side_effect=OSError("disk full")):
            with self_raises(OSError):
                atomic_write_text(target, "半截")
        assert target.read_text(encoding="utf-8") == "新内容\n"

class self_raises:
    def __init__(self, exc):
        self.exc = exc

    def __enter__(self):
        return self

    def __exit__(self, t, v, tb):
        assert isinstance(v, self.exc), v
        return True


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
