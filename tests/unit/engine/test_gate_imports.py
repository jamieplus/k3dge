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
