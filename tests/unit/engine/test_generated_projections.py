"""生成物新鲜度闸：符号索引 / docs/generated/{api,domains}.md / `.mcp.json`（2026-09-21）。"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.evaluator import ConsistencyEngine
from k3dge.engine.generated_docs import render_manual_docs_content
from k3dge.engine.manifest import Manifest
from k3dge.engine import search

SPEC = """# Domain Specification: core
- **Status**: Active
- **Module Path**: `src/core`
- **Contract Hash**: `sha256:{hash}`
- **Last Updated**: 2026-09-21
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
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


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
                "domains": {"core": {"src": "src/core", "spec": "docs/specs/core/spec.md"}},
                "ignore": [],
            }
        ),
        encoding="utf-8",
    )
    (repo / "src" / "core").mkdir(parents=True)
    (repo / "src" / "core" / "mod.py").write_text("def foo(x: int) -> int:\n    return x\n", encoding="utf-8")
    (repo / "docs" / "specs" / "core").mkdir(parents=True)
    (repo / "docs" / "specs" / "core" / "spec.md").write_text(SPEC.format(hash="0" * 64), encoding="utf-8")
    return repo


def _rules(repo: Path) -> list:
    return [v.rule_id for v in ConsistencyEngine(repo).evaluate().violations]


class TestGeneratedProjections(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _make_repo(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # --- ① 符号索引 ---

    def test_missing_symbol_index_is_not_a_violation(self) -> None:
        """索引不存在 ⇒ 跳过（`k3dge where` 会惰性建；缺文件不是漂移）。"""
        self.assertNotIn("SYMBOL_INDEX_STALE", _rules(self.repo))

    def test_stale_symbol_index_is_violation(self) -> None:
        idx = search.index_path(self.repo)
        idx.parent.mkdir(parents=True, exist_ok=True)
        idx.write_text(json.dumps({"gone": [{"file": "src/core/mod.py", "line": 1}]}), encoding="utf-8")
        self.assertIn("SYMBOL_INDEX_STALE", _rules(self.repo))

    def test_fresh_symbol_index_passes(self) -> None:
        search.write_symbol_index(self.repo)
        self.assertNotIn("SYMBOL_INDEX_STALE", _rules(self.repo))

    # --- ② docs/generated/{api,domains}.md ---

    def test_stale_generated_docs_is_violation(self) -> None:
        gen = self.repo / "docs" / "generated"
        gen.mkdir(parents=True)
        (gen / "api.md").write_text("# API Reference\n\n手写的旧内容\n", encoding="utf-8")
        self.assertIn("DOCS_GENERATED_STALE", _rules(self.repo))

    def test_fresh_generated_docs_pass(self) -> None:
        manifest = Manifest.load(self.repo)
        for path, content in render_manual_docs_content(self.repo, manifest).items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.assertNotIn("DOCS_GENERATED_STALE", _rules(self.repo))

    # --- ③ .mcp.json vs pipeline.toml ---

    def _write_pipeline(self, peer: str = "peerx") -> None:
        (self.repo / ".agent" / "pipeline.toml").write_text(
            f'[peers.{peer}]\nenabled = true\n', encoding="utf-8"
        )

    def _make_sibling(self, peer: str = "peerx") -> None:
        sib = self.repo.parent / peer
        (sib / "src" / peer).mkdir(parents=True, exist_ok=True)
        (sib / "src" / peer / "mcp.py").write_text("# stub\n", encoding="utf-8")

    def test_enabled_resolvable_peer_missing_from_mcp_json_is_violation(self) -> None:
        self._write_pipeline()
        self._make_sibling()
        (self.repo / ".mcp.json").write_text(json.dumps({"mcpServers": {"k3dge": {}}}), encoding="utf-8")
        self.assertIn("MCP_JSON_PEER_MISSING", _rules(self.repo))

    def test_peer_declared_in_mcp_json_passes(self) -> None:
        self._write_pipeline()
        self._make_sibling()
        (self.repo / ".mcp.json").write_text(
            json.dumps({"mcpServers": {"k3dge": {}, "peerx": {}}}), encoding="utf-8"
        )
        self.assertNotIn("MCP_JSON_PEER_MISSING", _rules(self.repo))

    def test_unresolvable_peer_is_not_a_violation(self) -> None:
        """sibling 不在 ⇒ 写侧本就会跳过（回退告警），闸不制造假红。"""
        self._write_pipeline(peer="nope")
        (self.repo / ".mcp.json").write_text(json.dumps({"mcpServers": {"k3dge": {}}}), encoding="utf-8")
        self.assertNotIn("MCP_JSON_PEER_MISSING", _rules(self.repo))

    def test_missing_k3dge_self_entry_is_violation(self) -> None:
        (self.repo / ".mcp.json").write_text(json.dumps({"mcpServers": {"other": {}}}), encoding="utf-8")
        self._write_pipeline(peer="nope")
        self.assertIn("MCP_JSON_PEER_MISSING", _rules(self.repo))

    def test_no_mcp_json_is_not_a_violation(self) -> None:
        self._write_pipeline(peer="nope")
        self.assertNotIn("MCP_JSON_PEER_MISSING", _rules(self.repo))


if __name__ == "__main__":
    unittest.main()
