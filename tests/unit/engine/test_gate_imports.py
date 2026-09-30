"""闸核不得 import 生命周期（T-02 依赖方向：evaluate 及其检查只出 Violation）。"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[3] / "src" / "k3dge" / "engine"

# Form-gate cluster: disk → Violation / hash. Must not pull writers or the facade.
_GATE = frozenset({
    "evaluator.py",
    "contract.py",
    "diff.py",
    "spec_schema.py",
    "manifest.py",
    "pairs.py",
    "models.py",
    "gates.py",
    "pipeline_schema.py",
    "mcp_json.py",
    "pure_schema.py",
    "pure_refs.py",
    "extractor_gen.py",
})

# Mutators + outbound + the compatibility facade (importing it pulls the graph).
_LIFECYCLE = frozenset({
    "k3dge.engine.milestone",
    "k3dge.engine.align",
    "k3dge.engine.seal",
    "k3dge.engine.seal_flow",
    "k3dge.engine.task_write",
    "k3dge.engine.audit_flow",
    "k3dge.engine.worktree",
    "k3dge.engine.pipeline_runner",
    "k3dge.engine.milestone_audit",
    "k3dge.engine.doc_audit",
    "k3dge.engine.changelog",
    "k3dge.engine.review_archive",
    "k3dge.engine.prompt",
})


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


class TestGateDoesNotImportLifecycle(unittest.TestCase):
    def test_gate_cluster_imports_no_lifecycle(self) -> None:
        leaks = []
        for name in sorted(_GATE):
            path = ENGINE / name
            self.assertTrue(path.is_file(), f"missing gate module {name}")
            for mod in _imported_modules(path):
                if mod in _LIFECYCLE or any(mod.startswith(b + ".") for b in _LIFECYCLE):
                    leaks.append(f"{name} imports {mod}")
        self.assertEqual(leaks, [], "gate ↛ lifecycle:\n  " + "\n  ".join(leaks))


def test_facts_of_covers_every_rendered_field() -> None:
    """render() 也填 fix_hint/pointers 的占位 ⇒ 守卫面必须一起扫（423）。"""
    from k3dge.engine import gate_facts

    code = next((c for c, d in gate_facts.GATE_FACTS.items()
                 if "{path}" in str(d.get("pointers") or "") or "{path}" in str(d.get("fix_hint") or "")), None)
    if code is None:
        # 没有这种声明也要保证 facts_of 的字段覆盖面（用一条含 fix_hint 的码验）
        code = next(c for c, d in gate_facts.GATE_FACTS.items() if d.get("fix_hint"))
    assert "path" in gate_facts.facts_of(code) or "{path}" not in (
        str((gate_facts.GATE_FACTS[code] or {}).get("fix_hint"))
        + str((gate_facts.GATE_FACTS[code] or {}).get("pointers"))), code


def test_generated_docs_fence_survives_backticks_in_iface(tmp_path, monkeypatch) -> None:
    """docstring 里出现三反引号会提前关围栏 ⇒ 投影形状坏（426）。"""
    from k3dge.engine import contract
    from k3dge.engine.generated_docs import render_manual_docs_content
    from k3dge.engine.manifest import Manifest

    nasty = "def f():\n    pass\n\n# doc: 例 ```py\nx\n```\n"
    monkeypatch.setattr(contract, "collect_domain_interface", lambda *a, **k: nasty)
    ws = _mini_ws(tmp_path)
    content = render_manual_docs_content(ws, Manifest.load(ws))
    api = [v for k, v in content.items() if k.name == "api.md"][0]
    assert "````python" in api, api[-500:]


def _mini_ws(tmp_path: Path) -> Path:
    (tmp_path / ".agent").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".agent" / "manifest.json").write_text(
        '{"package_root":"src","domains":{"demo":{"src":"src/demo","spec":"docs/specs/demo/spec.md"}}}',
        encoding="utf-8")
    (tmp_path / "src" / "demo").mkdir(parents=True)
    (tmp_path / "src" / "demo" / "__init__.py").write_text("def f():\n    pass\n", encoding="utf-8")
    return tmp_path
