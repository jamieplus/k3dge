import tempfile
import unittest
from pathlib import Path

from k3dge.engine import contract

SRC = '''"""Module docstring."""
from __future__ import annotations

def foo(x: int, y: str = "a") -> bool:
    return True

async def bar() -> None:
    pass

class Widget:
    def run(self, n: int) -> int:
        return n

    def _helper(self) -> None:
        pass
'''


class TestContract(unittest.TestCase):
    def test_extract_interface(self):
        iface = contract.extract_python_interface(SRC)
        self.assertIn("foo(x: int, y: str='a') -> bool", iface)
        self.assertIn("bar() -> None", iface)
        self.assertIn("class Widget", iface)
        self.assertIn("    run(self, n: int) -> int", iface)
        self.assertNotIn("_helper", iface)

    def test_compute_hash_deterministic(self):
        self.assertEqual(contract.compute_hash(SRC), contract.compute_hash(SRC))
        self.assertNotEqual(
            contract.compute_hash(SRC), contract.compute_hash("def other() -> None: pass")
        )

    def test_normalize_collapses_whitespace(self):
        self.assertEqual(
            contract.normalize("  def foo(x: int)  "),
            contract.normalize("def foo(x: int)"),
        )

    def test_verify_contract_matches(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)
            (src / "mod.py").write_text("def foo(x: int) -> str:\n    return ''\n")
            iface = contract.collect_domain_interface(src)
            h = contract.compute_hash(iface)
            spec = f"**Contract Hash**: `sha256:{h}`"
            ok, expected, actual = contract.verify_contract(src, spec)
            self.assertTrue(ok)
            self.assertEqual(expected, h)
            self.assertEqual(actual, h)

    def test_verify_contract_drift(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)
            (src / "mod.py").write_text("def foo(x: int) -> str:\n    return ''\n")
            spec = "**Contract Hash**: `sha256:" + "0" * 64 + "`"
            ok, expected, actual = contract.verify_contract(src, spec)
            self.assertFalse(ok)
            self.assertNotEqual(expected, actual)

    def test_cached_property_changes_hash(self):
        prop = "class W:\n    @property\n    def x(self) -> int:\n        return 1\n"
        cached = (
            "from functools import cached_property\n"
            "class W:\n    @cached_property\n    def x(self) -> int:\n        return 1\n"
        )
        self.assertNotEqual(
            contract.compute_hash(contract.extract_python_interface(prop)),
            contract.compute_hash(contract.extract_python_interface(cached)),
        )

    def test_syntax_error_is_visible(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)
            (src / "ok.py").write_text("def foo() -> int:\n    return 1\n")
            h1 = contract.compute_hash(contract.collect_domain_interface(src))
            (src / "broken.py").write_text("def bar( ->\n")
            from k3dge.engine.contract import _ExtractError

            with self.assertRaises(_ExtractError):
                contract.collect_domain_interface(src)
            self.assertTrue(h1)

    def test_ts_function_body_not_in_signature(self):
        try:
            import tree_sitter  # noqa: F401
            import tree_sitter_typescript  # noqa: F401
        except ImportError:
            self.skipTest("tree-sitter-typescript not installed")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "mod.ts"
            path.write_text("export function foo(x: number): number {\n  return x + 1;\n}\nconst skipped = 1;\n")
            iface = contract.extract_typescript_interface(path) or ""
            self.assertIn("foo", iface)
            self.assertNotIn("return x", iface)
            self.assertNotIn("skipped", iface)

    def test_verify_contract_missing_hash(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)
            (src / "mod.py").write_text("def foo(x: int) -> str:\n    return ''\n")
            ok, expected, actual = contract.verify_contract(src, "no hash here")
            self.assertFalse(ok)
            self.assertIsNone(expected)


if __name__ == "__main__":
    unittest.main()
