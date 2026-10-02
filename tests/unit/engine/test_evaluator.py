import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.evaluator import ConsistencyEngine
import shutil

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
    , encoding="utf-8")
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
        """元文件分类的回归必须可触发（t-134）：旧测对着 unborn HEAD 的空仓直接 evaluate，
        实际只验了"无改动 ⇒ 过"。基线提交 → **只动元文件**（pipeline.toml / 架构文档，
        不碰 src/、docs/specs/）→ 再验：过，且不因域检查（CONTRACT_DRIFT/SPEC_*）报。"""
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "baseline")
        (self.repo / ".agent" / "pipeline.toml").write_text(
            "[gates.search]\ncontext_max = 2\n", encoding="utf-8")
        (self.repo / "docs" / "architecture").mkdir(parents=True, exist_ok=True)
        (self.repo / "docs" / "architecture" / "overview.md").write_text("# Arch\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "meta: only pipeline/docs meta")
        report = ConsistencyEngine(self.repo).evaluate()
        dom = [v.rule_id for v in report.violations
               if v.rule_id.startswith(("CONTRACT_DRIFT", "SPEC_", "NO_DOMAINS", "TEST_"))]
        self.assertEqual(dom, [], f"元文件改动惊动了域检查：{dom}")
        self.assertTrue(report.passed, [(v.rule_id, v.message) for v in report.violations])

    def test_contract_drift_detected(self) -> None:
        from k3dge.sync.generator import sync_all

        (self.repo / "src/core/mod.py").write_text(
            "def foo(x: int) -> int:\n    return x\n"
        , encoding="utf-8")
        (self.repo / "docs/specs/core/spec.md").write_text(
            SPEC.format(hash="sha256:" + "0" * 64)
        , encoding="utf-8")
        # 先 sync 落真哈希再提交：基线干净（无漂移），后续改源码才引入真漂移（ocr2-115）。
        # 旧写法基线即无效哈希（全零），漂移检测坏了也照样红，测不出回归。
        sync_all(self.repo)
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "init")

        (self.repo / "src/core/mod.py").write_text(
            "def foo(x: int, y: str) -> int:\n    return x\n"
        , encoding="utf-8")
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
        , encoding="utf-8")
        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 1\n", encoding="utf-8")
        (self.repo / "tests/unit/core").mkdir(parents=True)
        (self.repo / "tests/unit/core/test_mod.py").write_text(
            "def test_fail():\n    assert False\n"
        , encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "init")
        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 2\n", encoding="utf-8")
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
        , encoding="utf-8")
        from k3dge.engine import contract

        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 1\n", encoding="utf-8")
        iface = contract.collect_domain_interface(self.repo / "src/core")
        h = contract.compute_hash(iface)
        (self.repo / "docs/specs/core/spec.md").write_text(SPEC.format(hash=f"sha256:{h}"), encoding="utf-8")
        (self.repo / "tests/unit/core").mkdir(parents=True)
        (self.repo / "tests/unit/core/test_mod.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "init")
        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 99\n", encoding="utf-8")
        report = ConsistencyEngine(self.repo).evaluate(run_tests=True)
        self.assertFalse(report.passed)
        self.assertTrue(any(v.rule_id == "MANIFEST_INVALID" for v in report.violations))

    def test_syntax_error_is_extract_failure(self) -> None:
        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 1\n", encoding="utf-8")
        (self.repo / "docs/specs/core/spec.md").write_text(
            SPEC.format(hash="sha256:" + "0" * 64)
        , encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "init")
        (self.repo / "src/core/broken.py").write_text("def bar( ->\n", encoding="utf-8")
        report = ConsistencyEngine(self.repo).evaluate()
        self.assertFalse(report.passed)
        self.assertTrue(
            any(v.rule_id == "CONTRACT_EXTRACT_FAILED" for v in report.violations)
        )

    def test_force_full_checks_untouched_domain(self) -> None:
        data = json.loads((self.repo / ".agent" / "manifest.json").read_text(encoding="utf-8"))
        data["domains"]["other"] = {
            "src": "src/other",
            "spec": "docs/specs/other/spec.md",
        }
        (self.repo / ".agent" / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 1\n", encoding="utf-8")
        (self.repo / "docs/specs/core/spec.md").write_text(
            SPEC.format(hash="sha256:" + "0" * 64)
        , encoding="utf-8")
        (self.repo / "src/other").mkdir(parents=True)
        (self.repo / "docs/specs/other").mkdir(parents=True)
        (self.repo / "src/other/mod.py").write_text("def bar() -> int:\n    return 1\n", encoding="utf-8")
        (self.repo / "docs/specs/other/spec.md").write_text(
            SPEC.replace("core", "other").format(hash="sha256:" + "0" * 64)
        , encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "init")
        # touch only core
        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 2\n", encoding="utf-8")
        selective = ConsistencyEngine(self.repo).evaluate()
        full = ConsistencyEngine(self.repo).evaluate(force_full=True)
        self.assertIn("core", selective.modified_domains)
        self.assertNotIn("other", selective.modified_domains)
        self.assertTrue(any(v.domain == "other" for v in full.violations))
        # 选择性评估必须真跳过未动域：只查 `modified_domains` 元数据不断言跳过，
        # 全量跑也照样过（ocr2-116）。`other` 的 violation 在 selective 里不得出现。
        self.assertFalse(any(v.domain == "other" for v in selective.violations),
                         [(v.domain, v.rule_id) for v in selective.violations])

    def test_non_utf8_spec_is_violation(self) -> None:
        (self.repo / "src/core/mod.py").write_text("def foo() -> int:\n    return 1\n", encoding="utf-8")
        (self.repo / "docs/specs/core/spec.md").write_bytes(b"\xff\xfe not utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "init")
        report = ConsistencyEngine(self.repo).evaluate(force_full=True)
        self.assertFalse(report.passed)
        self.assertTrue(any(v.rule_id == "SPEC_DECODE_FAILED" for v in report.violations))

    def test_engine_source_does_not_import_templates(self) -> None:
        """engine ↛ templates（ADR-0001 §2）。

        收口三洞（t-132）：①根漂了 `rglob` 静默空转——先验根、并断确实扫到文件；
        ②相对写法 `from ..templates import x`（module="templates", level=2）不匹配
        任何 `k3dge.templates` 前缀；③`from k3dge import templates` 同理。重构恰好
        会走这两种写法把 templates 拽进引擎——判据按**解析后的完整模块名**算。
        """
        import ast

        root = Path(__file__).resolve().parents[3] / "src" / "k3dge" / "engine"
        self.assertTrue(root.is_dir(), f"根解析错误：{root}")
        files = sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
        self.assertGreater(len(files), 30, f"只扫到 {len(files)} 个文件——守卫在空转")
        banned = "k3dge.templates"

        def _resolved_names(node):
            """一个 import 语句解析出的**全部完整模块名**（含 alias 粒度）。"""
            if isinstance(node, ast.Import):
                return [a.name for a in node.names]
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    depth = len(pkg_parts) - (node.level - 1)
                    base = pkg_parts[:max(depth, 0)]
                    if node.module:
                        base = base + node.module.split(".")
                    out = [".".join(base)]
                    out += [".".join([*base, a.name]) for a in node.names if a.name != "*"]
                    return [o for o in out if o]
                mods = [node.module] if node.module else []
                if node.module:
                    mods += [f"{node.module}.{a.name}" for a in node.names if a.name != "*"]
                return mods
            return []

        for path in files:
            pkg_parts = ["k3dge", "engine"] + list(path.relative_to(root).parts[:-1])
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                for m in _resolved_names(node):
                    if m == banned or m.startswith(banned + "."):
                        self.fail(f"{path.name} imports {m}")


    def test_empty_domains_is_violation(self) -> None:
        (self.repo / ".agent" / "manifest.json").write_text(
            json.dumps({"package_root": "src", "domains": {}, "ignore": []}),
            encoding="utf-8",
        )
        report = ConsistencyEngine(self.repo).evaluate(force_full=True)
        self.assertFalse(report.passed)
        self.assertTrue(any(v.rule_id == "NO_DOMAINS" for v in report.violations))

    def test_unregistered_domain_detected(self) -> None:
        (self.repo / "src" / "other").mkdir()
        (self.repo / "src" / "other" / "mod.py").write_text("def f() -> None:\n    pass\n", encoding="utf-8")
        report = ConsistencyEngine(self.repo).evaluate()
        self.assertTrue(
            any(v.rule_id == "UNREGISTERED_DOMAIN" for v in report.violations)
        )

    def _make_workspace(self, depends_a_on_b: bool) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "src" / "k3dge" / "a").mkdir(parents=True)
        (root / "src" / "k3dge" / "a" / "mod.py").write_text("from k3dge.b import x\n", encoding="utf-8")
        (root / "src" / "k3dge" / "b").mkdir(parents=True)
        (root / "src" / "k3dge" / "b" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (root / "docs" / "specs" / "a").mkdir(parents=True)
        spec = (
            "# Spec\n\n"
            "## 1. Domain Boundary & Responsibilities\nx\n"
            "## 2. Public Interfaces & Type Contracts\nx\n"
            "## 4. Verification Matrix\n"
            "| Scenario ID | Level | Input | Expected | Test File |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| TC-01 | L1 | a | b | `tests/unit/a/test_a.py` |\n"
        )
        (root / "docs" / "specs" / "a" / "spec.md").write_text(spec, encoding="utf-8")
        (root / "tests" / "unit" / "a").mkdir(parents=True)
        (root / "tests" / "unit" / "a" / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
        domains = {
            "a": {"src": "src/k3dge/a", "spec": "docs/specs/a/spec.md", "tests": "tests/unit/a"},
            "b": {"src": "src/k3dge/b", "spec": "docs/specs/a/spec.md", "tests": "tests/unit/a"},
        }
        if depends_a_on_b:
            domains["a"]["depends_on"] = ["b"]
        manifest = {"name": "t", "package_root": "src/k3dge", "domains": domains, "ignore": []}
        (root / ".agent").mkdir()
        (root / ".agent" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return root

    def test_domain_import_violation_detected(self) -> None:
        root = self._make_workspace(depends_a_on_b=False)
        report = ConsistencyEngine(root).evaluate(force_full=True)
        self.assertIn("DOMAIN_IMPORT_VIOLATION", [v.rule_id for v in report.violations])

    def test_depends_on_allows_import(self) -> None:
        root = self._make_workspace(depends_a_on_b=True)
        report = ConsistencyEngine(root).evaluate(force_full=True)
        self.assertNotIn("DOMAIN_IMPORT_VIOLATION", [v.rule_id for v in report.violations])


class TestAdrGovernance(unittest.TestCase):
    def _schema(self, ws):
        from tests.unit.engine.test_doc_catalog import ADR_SCHEMA, _write_schema

        _write_schema(ws, "adr", ADR_SCHEMA)

    def _adr(self, ws, name, number="0001", status="Accepted", date="2026-08-19", sections=True):
        self._schema(ws)
        sec = ""
        if sections:
            sec = (
                "\n## 1. 上下文 (Context)\n\nc\n\n## 2. 决策 (Decision)\n\nd\n"
                "\n## 3. 产生后果 (Consequences)\n\ne\n"
            )
        text = f"---\nStatus: {status}\nDate: {date}\n---\n\n# ADR-{number}: sample\n\nintro{sec}\n"
        p = ws / "docs" / "adr" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def _violations(self, ws):
        from k3dge.engine.doc_catalog import validate_docs

        return validate_docs(ws, types=["adr"])

    def test_valid_adr_passes(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            self._adr(ws, "0001-x.md", number="0001")
            self.assertEqual(self._violations(ws), [])

    def test_number_collision_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            self._adr(ws, "0001-a.md", number="0001")
            self._adr(ws, "0001-b.md", number="0001")
            self.assertIn("ADR_NUMBER_COLLISION", [v.rule_id for v in self._violations(ws)])

    def test_frontmatter_invalid_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            self._adr(ws, "0002-x.md", number="0002", status="Bogus")
            self.assertIn("ADR_FRONTMATTER_MISSING", [v.rule_id for v in self._violations(ws)])

    def test_sections_missing_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            self._adr(ws, "0003-x.md", number="0003", sections=False)
            self.assertIn("ADR_SECTIONS_MISSING", [v.rule_id for v in self._violations(ws)])

    def test_repo_adrs_conform(self):
        from k3dge.engine.doc_catalog import validate_docs

        ws = Path(__file__).resolve().parents[3]
        # 仓根解析错要**红**（t-135）：旧 skipTest 让 parents[3] 漂移＝治理测集体静默
        # 跳过、CI 全绿而无人被校验。本仓必有该目录——没找到即路径错。
        self.assertTrue((ws / "docs" / "adr").is_dir(),
                        f"仓根解析错误：{ws / 'docs' / 'adr'} 不存在（parents[3] 漂了？）")
        adr_v = [v for v in validate_docs(ws, types=["adr"]) if v.rule_id.startswith("ADR_")]
        self.assertEqual(
            adr_v, [], [f"{v.rule_id}: {v.message} ({v.file_path})" for v in adr_v]
        )


class TestTaskGovernance(unittest.TestCase):
    def _schema(self, ws):
        from tests.unit.engine.test_doc_catalog import _write_schema

        schema = {
            "headers": {"Status": ["idea", "deferred", "in-progress", "done"]},
            "codes": {"headers": "TASK_STATUS_INVALID"},
        }
        _write_schema(ws, "tasks", schema)

    def _violations(self, ws):
        from k3dge.engine.doc_catalog import SCHEMA_FILE, validate_docs

        if not (ws / "docs" / "tasks" / SCHEMA_FILE).is_file():
            self._schema(ws)
        return validate_docs(ws, types=["tasks"])

    def _task(self, ws, name, status="done"):
        p = ws / "docs" / "tasks" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        # done 票需带结案记录（TASK_CLOSURE_MISSING）；文件名的 .done 后缀与 status 须一致
        tail = "\n## 结案\n- 落地于 abc\n" if status == "done" else ""
        p.write_text(f"---\nstatus: {status}\n---\n\n# {name}\n{tail}", encoding="utf-8")

    def test_valid_status_passes(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            self._task(ws, "a.done.md", status="done")
            self._task(ws, "b.md", status="idea")
            self.assertEqual(self._violations(ws), [])

    def test_invalid_status_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            self._task(ws, "bad.md", status="bogus")
            ids = [v.rule_id for v in self._violations(ws)]
            self.assertIn("TASK_STATUS_INVALID", ids)

    def test_missing_status_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            p = ws / "docs" / "tasks" / "nostatus.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# no status here\n", encoding="utf-8")
            ids = [v.rule_id for v in self._violations(ws)]
            self.assertIn("TASK_STATUS_INVALID", ids)

    def test_repo_tasks_conform(self):
        from k3dge.engine.doc_catalog import validate_docs

        ws = Path(__file__).resolve().parents[3]
        # 仓根解析错要**红**（t-135）：旧 skipTest 让 parents[3] 漂移＝治理测集体静默
        # 跳过、CI 全绿而无人被校验。本仓必有该目录——没找到即路径错。
        self.assertTrue((ws / "docs" / "tasks").is_dir(),
                        f"仓根解析错误：{ws / 'docs' / 'tasks'} 不存在（parents[3] 漂了？）")
        tv = [v for v in validate_docs(ws, types=["tasks"]) if v.rule_id.startswith("TASK_")]
        self.assertEqual(tv, [], [f"{v.rule_id}: {v.message} ({v.file_path})" for v in tv])


class TestIncidentGovernance(unittest.TestCase):
    def _schema(self, ws):
        from tests.unit.engine.test_doc_catalog import _write_schema

        schema = {
            "filename": r"^INC-\d{8}-[\w-]+\.md$",
            "h1": r"^#\s+Incident",
            # 正则要显式 `re:` 前缀：字面量清单不再被当正则猜（ocr-301）
            "sections": [r"re:^##\s+1\.", r"re:^##\s+2\.", r"re:^##\s+3\.", r"re:^##\s+4\."],
            "codes": {
                "filename": "INCIDENT_FORM_INVALID",
                "h1": "INCIDENT_FORM_INVALID",
                "sections": "INCIDENT_FORM_INVALID",
            },
        }
        _write_schema(ws, "incidents", schema)

    def _violations(self, ws):
        from k3dge.engine.doc_catalog import validate_docs

        self._schema(ws)
        return validate_docs(ws, types=["incidents"])

    def _incident(self, ws, name, sections=(1, 2, 3, 4)):
        p = ws / "docs" / "incidents" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        body = "# Incident: sample\n\n" + "".join(f"## {i}. section {i}\n\nx\n" for i in sections)
        p.write_text(body, encoding="utf-8")

    def test_valid_incident_passes(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            self._incident(ws, "INC-20260827-CON-x.md")
            self.assertEqual(self._violations(ws), [])

    def test_missing_section_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            self._incident(ws, "INC-20260827-CON-x.md", sections=(1, 2, 4))  # 缺 3
            ids = [v.rule_id for v in self._violations(ws)]
            self.assertIn("INCIDENT_FORM_INVALID", ids)

    def test_bad_filename_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            self._incident(ws, "incident-x.md")  # 无 INC- 前缀
            ids = [v.rule_id for v in self._violations(ws)]
            self.assertIn("INCIDENT_FORM_INVALID", ids)

    def test_repo_incidents_conform(self):
        from k3dge.engine.doc_catalog import validate_docs

        ws = Path(__file__).resolve().parents[3]
        # 仓根解析错要**红**（t-135）：旧 skipTest 让 parents[3] 漂移＝治理测集体静默
        # 跳过、CI 全绿而无人被校验。本仓必有该目录——没找到即路径错。
        self.assertTrue((ws / "docs" / "incidents").is_dir(),
                        f"仓根解析错误：{ws / 'docs' / 'incidents'} 不存在（parents[3] 漂了？）")
        iv = [v for v in validate_docs(ws, types=["incidents"]) if v.rule_id.startswith("INCIDENT_")]
        self.assertEqual(iv, [], [f"{v.rule_id}: {v.message} ({v.file_path})" for v in iv])


if __name__ == "__main__":
    unittest.main()
