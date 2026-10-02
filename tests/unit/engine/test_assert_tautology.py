"""ASSERT_TAUTOLOGY：断言的真值已经写在测试表达式里。"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from k3dge.engine import gate_facts
from k3dge.engine.assert_tautology import check, is_test_path, scan_source, violations_for
from k3dge.engine.evaluator import ConsistencyEngine


def _hits(source: str):
    return scan_source(source)


class TestPredicate(unittest.TestCase):
    def test_literal_true(self) -> None:
        self.assertEqual(_hits("assert True\n"), [(1, "literal_true")])
        self.assertEqual(_hits("assert (True)\n"), [(1, "literal_true")])
        self.assertEqual(_hits("assert True, 'msg'\n"), [(1, "literal_true")])

    def test_alias_self_compare(self) -> None:
        src = (
            "def test_axes():\n"
            "    ax = ck['axes']\n"
            "    assert set(ax) <= set(ck['axes'])\n"
        )
        self.assertEqual(_hits(src), [(3, "self_compare")])

    def test_same_expression_without_alias(self) -> None:
        self.assertEqual(_hits("assert x == x\n"), [(1, "self_compare")])
        self.assertEqual(_hits("assert 1 == 1\n"), [(1, "self_compare")])
        self.assertEqual(_hits("assert x <= x\n"), [(1, "self_compare")])
        self.assertEqual(_hits("assert x >= x\n"), [(1, "self_compare")])
        self.assertEqual(_hits("assert x is x\n"), [(1, "self_compare")])
        self.assertEqual(_hits("assert {1} == {1}\n"), [(1, "self_compare")])

    def test_literal_assignment_folds_one_level(self) -> None:
        src = "n = 1\nassert n == 1\n"
        self.assertEqual(_hits(src), [(2, "self_compare")])
        src = "flag = True\nself.assertTrue(flag)\n"
        self.assertEqual(_hits(src), [(2, "literal_true")])

    def test_unittest_forms(self) -> None:
        self.assertEqual(_hits("self.assertTrue(True)\n"), [(1, "literal_true")])
        self.assertEqual(_hits("self.assertFalse(False)\n"), [(1, "literal_false")])
        self.assertEqual(_hits("self.assertEqual(a, a)\n"), [(1, "self_compare")])
        self.assertEqual(_hits("self.assertIs(a, a)\n"), [(1, "self_compare")])
        self.assertEqual(_hits("self.assertLessEqual(a, a)\n"), [(1, "self_compare")])
        self.assertEqual(_hits("self.assertGreaterEqual(a, a)\n"), [(1, "self_compare")])
        src = "ax = ck['axes']\nself.assertEqual(set(ax), set(ck['axes']))\n"
        self.assertEqual(_hits(src), [(2, "self_compare")])

    def test_same_call_twice_is_a_determinism_check(self) -> None:
        self.assertEqual(_hits("assert digest(b) == digest(b)\n"), [])
        self.assertEqual(
            _hits("self.assertEqual(compute_hash(src), compute_hash(src))\n"), []
        )

    def test_real_compare_stays_quiet(self) -> None:
        samples = [
            "assert result == expected\n",
            "assert x < x\n",
            "assert x > x\n",
            "assert x != x\n",
            "assert x is not x\n",
            "assert x in x\n",
            "assert x not in x\n",
            "assert False\n",
            "assert not False\n",
            "assert cond or True\n",
            "assert len(h) == 64\n",
            "assert 1 + 1 == 2\n",
            "self.assertTrue(ok)\n",
            "self.assertTrue(1)\n",
            "self.assertFalse(0)\n",
            "self.assertFalse(None)\n",
            "self.assertEqual(got, expected)\n",
            "self.assertIn(x, x)\n",
            "self.assertNotEqual(v, v)\n",
            "self.assertIsNot(v, v)\n",
            "self.assertGreater(v, v)\n",
            "self.assertLess(v, v)\n",
        ]
        for sample in samples:
            self.assertEqual(_hits(sample), [], sample)

    def test_call_between_assignment_and_assert_drops_the_alias(self) -> None:
        src = (
            "ax = ck['axes']\n"
            "f()\n"
            "assert set(ax) <= set(ck['axes'])\n"
        )
        self.assertEqual(_hits(src), [])

    def test_alias_not_used_stays_quiet(self) -> None:
        src = "ax = ck['axes']\nassert set(ck['a']) <= set(ck['b'])\n"
        self.assertEqual(_hits(src), [])

    def test_skip_unless_true_does_not_indict_a_real_assert(self) -> None:
        src = (
            "import unittest\n"
            "@unittest.skipUnless(True, 'reason')\n"
            "def test_len():\n"
            "    assert len(h) == 64\n"
        )
        self.assertEqual(_hits(src), [])

    def test_loop_target_shadows_the_alias(self) -> None:
        src = (
            "ax = ck['axes']\n"
            "for ax in items:\n"
            "    assert set(ax) <= set(ck['axes'])\n"
        )
        self.assertEqual(_hits(src), [])

    def test_alias_inside_if_still_fires_and_does_not_leak_out(self) -> None:
        inside = (
            "ax = ck['axes']\n"
            "if cond:\n"
            "    assert set(ax) <= set(ck['axes'])\n"
        )
        self.assertEqual(_hits(inside), [(3, "self_compare")])
        leaked = (
            "if cond:\n"
            "    ax = ck['axes']\n"
            "assert set(ax) <= set(ck['axes'])\n"
        )
        self.assertEqual(_hits(leaked), [])

    def test_nested_function_does_not_inherit_aliases(self) -> None:
        src = (
            "ax = ck['axes']\n"
            "def inner():\n"
            "    assert set(ax) <= set(ck['axes'])\n"
            "assert True\n"
        )
        self.assertEqual(_hits(src), [(4, "literal_true")])

    def test_is_identity_is_not_fooled_by_alias_substitution(self) -> None:
        # ocr2-183: `is` 是同一性比较；文本级别名替换后 AST 相同 ≠ 运行时同一对象。
        self.assertEqual(_hits("a = []\nassert a is []\n"), [])
        # 替换前就同引用的 `x is x` 仍要报（真恒真）。
        self.assertEqual(_hits("assert x is x\n"), [(1, "self_compare")])

    def test_def_time_side_effects_in_defaults_and_bases_clear_aliases(self) -> None:
        # ocr2-184: def/class 语句执行期会求值默认参数/基类/关键字，副作用须清别名。
        default_mutates = (
            "a = ck['axes']\n"
            "def _f(x=ck.pop('axes')):\n"
            "    pass\n"
            "assert a == ck['axes']\n"
        )
        self.assertEqual(_hits(default_mutates), [])
        base_mutates = (
            "a = ck['axes']\n"
            "class C(ck.pop('axes')):\n"
            "    pass\n"
            "assert a == ck['axes']\n"
        )
        self.assertEqual(_hits(base_mutates), [])

    def test_annotation_side_effect_clears_aliases(self) -> None:
        # ocr2-185: AnnAssign 会求值 annotation；带副作用的注解须先失效别名。
        src = "a = ck['axes']\nx: ck.pop('axes') = None\nassert a == ck['axes']\n"
        self.assertEqual(_hits(src), [])

    def test_syntax_error_returns_empty(self) -> None:
        self.assertEqual(_hits("def ("), [])

    def test_product_module_is_not_a_test_path(self) -> None:
        self.assertFalse(is_test_path("src/k3dge/engine/test_surface.py"))
        self.assertTrue(is_test_path("tests/unit/engine/test_assert_tautology.py"))
        self.assertTrue(is_test_path("src/pkg/test/test_x.py"))
        self.assertEqual(violations_for("src/k3dge/engine/test_surface.py", "assert True\n"), [])


class TestViolation(unittest.TestCase):
    def test_format_names_the_line_and_stays_judgment(self) -> None:
        self.assertEqual(gate_facts.fix_kind("ASSERT_TAUTOLOGY"), "judgment")
        self.assertEqual(gate_facts.severity("ASSERT_TAUTOLOGY"), "block")
        found = violations_for("tests/t.py", "assert True\n")
        self.assertEqual(len(found), 1)
        text = found[0].format()
        self.assertIn("[ASSERT_TAUTOLOGY]", text)
        self.assertIn("tests/t.py", text)
        self.assertIn("第 1 行", text)
        self.assertGreaterEqual(text.count("option:"), 2)
        self.assertNotIn("fix:", text)
        self.assertNotIn("{", text)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "tester")
    (repo / ".agent").mkdir()
    (repo / ".agent" / "manifest.json").write_text(
        json.dumps({"package_root": "src", "domains": {
            "core": {"src": "src/core", "spec": "docs/specs/core/spec.md"},
        }, "ignore": []}),
        encoding="utf-8",
    )
    (repo / "src" / "core").mkdir(parents=True)
    (repo / "docs" / "specs" / "core").mkdir(parents=True)
    return repo


class TestEvaluateWiring(unittest.TestCase):
    def test_changed_test_blocks_and_product_file_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = _repo(Path(d))
            (repo / "tests").mkdir()
            (repo / "tests" / "test_bad.py").write_text("def test_bad():\n    assert True\n", encoding="utf-8")
            (repo / "src" / "core" / "test_surface.py").write_text("assert True\n", encoding="utf-8")
            report = ConsistencyEngine(repo).evaluate()
            taut = [v for v in report.violations if v.rule_id == "ASSERT_TAUTOLOGY"]
            self.assertEqual([v.file_path for v in taut], ["tests/test_bad.py"])
            self.assertFalse(report.passed)

    def test_force_full_sees_committed_tests_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = _repo(Path(d))
            (repo / "tests").mkdir()
            (repo / "tests" / "test_bad.py").write_text("def test_bad():\n    assert True\n", encoding="utf-8")
            (repo / "src" / "core" / "test").mkdir()
            (repo / "src" / "core" / "test" / "test_x.py").write_text(
                "def test_x():\n    assert True\n", encoding="utf-8"
            )
            _git(repo, "add", "-A")
            _git(repo, "commit", "-m", "init")
            incremental = ConsistencyEngine(repo).evaluate()
            self.assertFalse(any(v.rule_id == "ASSERT_TAUTOLOGY" for v in incremental.violations))
            full = ConsistencyEngine(repo).evaluate(force_full=True)
            paths = [v.file_path for v in full.violations if v.rule_id == "ASSERT_TAUTOLOGY"]
            self.assertEqual(paths, ["tests/test_bad.py"])

    def test_real_assert_on_force_full_stays_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = _repo(Path(d))
            (repo / "tests").mkdir()
            (repo / "tests" / "test_ok.py").write_text(
                "def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8"
            )
            report = ConsistencyEngine(repo).evaluate(force_full=True)
            self.assertFalse(any(v.rule_id == "ASSERT_TAUTOLOGY" for v in report.violations))

    def test_check_reads_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "tests").mkdir()
            (root / "tests" / "test_bad.py").write_text("assert x == x\n", encoding="utf-8")
            found = check(root, ["tests/test_bad.py", "src/test_surface.py"])
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].detail["shape"], "self_compare")
