"""ASSERT_TAUTOLOGY：断言的真值已经写在测试表达式里。"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from k3dge.engine import gate_facts
from k3dge.engine.assert_tautology import check, is_test_path, scan_source, violations_for
from k3dge.engine.evaluator import ConsistencyEngine

# ocr2-429：宿主 GIT_*/K3DGE_BASE_SHA（CI 常导）与 global gitconfig 会让临时仓的
# setup 或被测引擎的 git 调用为无关原因红/漂移。净化 env 同时喂 `_git` 与引擎调用。
_ENV = {k: v for k, v in os.environ.items()
        if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG", "K3DGE_BASE_SHA")}
_ENV["GIT_CONFIG_GLOBAL"] = os.devnull
_ENV["GIT_CONFIG_NOSYSTEM"] = "1"


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
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                   env=_ENV)


def _evaluate(repo: Path, **kwargs):
    """被测引擎的 git 调用继承 os.environ（`diff.py` 无 env=）；在净化后的环境里求值。"""
    with mock.patch.dict(os.environ, _ENV, clear=True):
        return ConsistencyEngine(repo).evaluate(**kwargs)


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
            report = _evaluate(repo)
            taut = [v for v in report.violations if v.rule_id == "ASSERT_TAUTOLOGY"]
            self.assertEqual([v.file_path for v in taut], ["tests/test_bad.py"])
            self.assertFalse(report.passed)

    def test_incremental_reports_uncommitted_taut_test(self) -> None:
        """ocr2-431：增量面在**空改动集**上断言"无告警"是恒绿。留一个未提交的 taut
        测试，增量面必须真报出来，证明选择/接线没坏。"""
        with tempfile.TemporaryDirectory() as d:
            repo = _repo(Path(d))
            (repo / "tests").mkdir()
            _git(repo, "add", "-A")
            _git(repo, "commit", "-m", "init")
            (repo / "tests" / "test_dirty.py").write_text(
                "def test_dirty():\n    assert True\n", encoding="utf-8"
            )
            report = _evaluate(repo)
            paths = [v.file_path for v in report.violations if v.rule_id == "ASSERT_TAUTOLOGY"]
            self.assertEqual(paths, ["tests/test_dirty.py"])

    def test_force_full_scans_working_tree_tests_dir(self) -> None:
        """ocr2-432：force_full 走 `assert_tautology.test_files()` 对 **工作树** `tests/`
        的 rglob——不是"已提交集合"，也**不**覆盖 `src/**/test/`（与增量 `is_test_path`
        口径不对称，显式钉住以免名字继续误导）。"""
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
            # 未提交的工作树 taut 也被全量面看到 ⇒ 证明是工作树扫描而非已提交集
            (repo / "tests" / "test_dirty.py").write_text(
                "def test_dirty():\n    assert True\n", encoding="utf-8"
            )
            full = _evaluate(repo, force_full=True)
            paths = sorted(v.file_path for v in full.violations if v.rule_id == "ASSERT_TAUTOLOGY")
            self.assertEqual(paths, ["tests/test_bad.py", "tests/test_dirty.py"])
            self.assertNotIn("src/core/test/test_x.py", paths)

    def test_real_assert_on_force_full_stays_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = _repo(Path(d))
            (repo / "tests").mkdir()
            (repo / "tests" / "test_ok.py").write_text(
                "def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8"
            )
            report = _evaluate(repo, force_full=True)
            self.assertFalse(any(v.rule_id == "ASSERT_TAUTOLOGY" for v in report.violations))

    def test_check_reads_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "tests").mkdir()
            (root / "tests" / "test_bad.py").write_text("assert x == x\n", encoding="utf-8")
            found = check(root, ["tests/test_bad.py", "src/test_surface.py"])
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].detail["shape"], "self_compare")

    def test_check_skips_unreadable_and_non_utf8_test_paths(self) -> None:
        """ocr2-433：`check` 的 except 分支只对**测试路径**才可达——旧测喂
        `src/test_surface.py`（先被 `is_test_path` 滤掉）根本没走到。缺文件 + 非 UTF-8
        两个测试路径，证明守卫真的吞掉而不是崩。"""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "tests").mkdir()
            (root / "tests" / "test_binary.py").write_bytes(b"\xff\xfe\x00\x80")
            found = check(root, ["tests/test_missing.py", "tests/test_binary.py"])
            self.assertEqual(found, [])
