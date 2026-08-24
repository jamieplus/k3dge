import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.evaluator import ConsistencyEngine

SPEC = """# Domain Specification: core
- **Status**: Active
- **Module Path**: `src/core`
- **Contract Hash**: {hash}
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


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )


def _make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "tester")
    (repo / ".agent").mkdir()
    (repo / ".agent" / "manifest.json").write_text(
        json.dumps(
            {
                "package_root": "src",
                "domains": {
                    "core": {
                        "src": "src/core",
                        "spec": "docs/specs/core/spec.md",
                    }
                },
                "ignore": [],
            }
        )
    )
    (repo / "src" / "core").mkdir(parents=True)
    (repo / "docs" / "specs" / "core").mkdir(parents=True)
    return repo


class TestEvaluator(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _make_repo(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_no_violations_when_only_meta_files_changed(self) -> None:
        report = ConsistencyEngine(self.repo).evaluate()
        self.assertTrue(report.passed)

    def test_contract_drift_detected(self) -> None:
        (self.repo / "src/core/mod.py").write_text(
            "def foo(x: int) -> int:\n    return x\n"
        )
        (self.repo / "docs/specs/core/spec.md").write_text(
            SPEC.format(hash="sha256:" + "0" * 64)
        )
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "init")

        (self.repo / "src/core/mod.py").write_text(
            "def foo(x: int, y: str) -> int:\n    return x\n"
        )
        report = ConsistencyEngine(self.repo).evaluate()
        self.assertFalse(report.passed)
        self.assertTrue(
            any(v.rule_id == "CONTRACT_DRIFT" for v in report.violations)
        )

    def test_invalid_manifest_json_is_violation(self) -> None:
        (self.repo / ".agent" / "manifest.json").write_text("{not json", encoding="utf-8")
        report = ConsistencyEngine(self.repo).evaluate()
        self.assertFalse(report.passed)
        self.assertTrue(
            any(v.rule_id == "MANIFEST_INVALID" for v in report.violations)
        )

    def test_missing_spec_with_failing_tests_does_not_crash(self) -> None:
        (self.repo / ".agent" / "manifest.json").write_text(
            json.dumps(
                {
                    "package_root": "src",
                    "domains": {
                        "core": {
                            "src": "src/core",
                            "tests": "tests/unit/core",
                        }
                    },
                    "ignore": [],
                }
            )
        )
        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 1\n")
        (self.repo / "tests/unit/core").mkdir(parents=True)
        (self.repo / "tests/unit/core/test_mod.py").write_text(
            "def test_fail():\n    assert False\n"
        )
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "init")
        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 2\n")
        report = ConsistencyEngine(self.repo).evaluate(run_tests=True)
        self.assertFalse(report.passed)
        self.assertTrue(
            any(v.rule_id in {"SPEC_NOT_FOUND", "TEST_FAILURE"} for v in report.violations)
        )

    def test_bad_test_command_template_is_violation(self) -> None:
        (self.repo / ".agent" / "manifest.json").write_text(
            json.dumps(
                {
                    "package_root": "src",
                    "test_command_template": "pytest {missing}",
                    "domains": {
                        "core": {
                            "src": "src/core",
                            "spec": "docs/specs/core/spec.md",
                            "tests": "tests/unit/core",
                        }
                    },
                    "ignore": [],
                }
            )
        )
        from k3dge.engine import contract

        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 1\n")
        iface = contract.collect_domain_interface(self.repo / "src/core")
        h = contract.compute_hash(iface)
        (self.repo / "docs/specs/core/spec.md").write_text(SPEC.format(hash=f"sha256:{h}"))
        (self.repo / "tests/unit/core").mkdir(parents=True)
        (self.repo / "tests/unit/core/test_mod.py").write_text("def test_ok():\n    assert True\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "init")
        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 99\n")
        report = ConsistencyEngine(self.repo).evaluate(run_tests=True)
        self.assertFalse(report.passed)
        self.assertTrue(any(v.rule_id == "MANIFEST_INVALID" for v in report.violations))

    def test_syntax_error_is_extract_failure(self) -> None:
        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 1\n")
        (self.repo / "docs/specs/core/spec.md").write_text(
            SPEC.format(hash="sha256:" + "0" * 64)
        )
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "init")
        (self.repo / "src/core/broken.py").write_text("def bar( ->\n")
        report = ConsistencyEngine(self.repo).evaluate()
        self.assertFalse(report.passed)
        self.assertTrue(
            any(v.rule_id == "CONTRACT_EXTRACT_FAILED" for v in report.violations)
        )

    def test_force_full_checks_untouched_domain(self) -> None:
        data = json.loads((self.repo / ".agent" / "manifest.json").read_text())
        data["domains"]["other"] = {
            "src": "src/other",
            "spec": "docs/specs/other/spec.md",
        }
        (self.repo / ".agent" / "manifest.json").write_text(json.dumps(data))
        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 1\n")
        (self.repo / "docs/specs/core/spec.md").write_text(
            SPEC.format(hash="sha256:" + "0" * 64)
        )
        (self.repo / "src/other").mkdir(parents=True)
        (self.repo / "docs/specs/other").mkdir(parents=True)
        (self.repo / "src/other/mod.py").write_text("def bar() -> int:\n    return 1\n")
        (self.repo / "docs/specs/other/spec.md").write_text(
            SPEC.replace("core", "other").format(hash="sha256:" + "0" * 64)
        )
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "init")
        # touch only core
        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 2\n")
        selective = ConsistencyEngine(self.repo).evaluate()
        full = ConsistencyEngine(self.repo).evaluate(force_full=True)
        self.assertIn("core", selective.modified_domains)
        self.assertNotIn("other", selective.modified_domains)
        self.assertTrue(any(v.domain == "other" for v in full.violations))

    def test_unregistered_domain_detected(self) -> None:
        (self.repo / "src" / "other").mkdir()
        (self.repo / "src" / "other" / "mod.py").write_text("def f() -> None:\n    pass\n")
        report = ConsistencyEngine(self.repo).evaluate()
        self.assertTrue(
            any(v.rule_id == "UNREGISTERED_DOMAIN" for v in report.violations)
        )


if __name__ == "__main__":
    unittest.main()
