"""生成物新鲜度闸：符号索引 / docs/generated/{api,domains}.md / `.mcp.json`（2026-09-21）。"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


def _git_env() -> dict:
    """ocr2-467：夹具 git 必须出局宿主环境——只清 K3DGE_BASE_SHA/GIT_DIR 不够，
    全局 commit.gpgsign/hooksPath/autocrlf/excludesFile、GIT_CONFIG_*、GIT_WORK_TREE
    都会让 setup 为无关原因红或改写 fixture 字节。"""
    e = {k: v for k, v in os.environ.items()
         if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG", "K3DGE_BASE_SHA")}
    e["GIT_CONFIG_GLOBAL"] = os.devnull
    e["GIT_CONFIG_NOSYSTEM"] = "1"
    return e


def _git(repo: Path, *args: str) -> None:
    """失败**带 git 的 stderr**（t-165）：`check=True` 的 CalledProcessError 只印命令与 rc，
    `capture_output` 又把 stderr 吞了——"Command returned non-zero exit status 128" 读起来
    像产品 bug，其实是 git <2.28 不认 `-b` / init.defaultBranch 被拦 / CI 包装器作怪。"""
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       env=_git_env(), timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{(r.stderr or r.stdout).strip()}")


def _git_out(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          check=True, capture_output=True, text=True, env=_git_env(),
                          timeout=60).stdout


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


def _violations(repo: Path):
    return ConsistencyEngine(repo).evaluate().violations


def _rules(repo: Path) -> list:
    return [v.rule_id for v in _violations(repo)]


class TestGeneratedProjections(unittest.TestCase):
    def setUp(self) -> None:
        # 环境隔离 + 提交（t-166）：`evaluate()` 先走 change-set；继承的 K3DGE_BASE_SHA
        # 在这个 HEAD-less 临时仓上让 `git diff` 失败 ⇒ GIT_UNAVAILABLE 早退，
        # 本闸**根本没跑**——assertIn 全红、assertNotIn 全 vacuous。清环境之外，
        # 把 fixture 提交一次，与真仓形状一致。
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("K3DGE_BASE_SHA", None)
        os.environ.pop("GIT_DIR", None)
        self.repo = _make_repo(Path(self._tmp.name))
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "init")
        self.assertTrue(_git_out(self.repo, "rev-parse", "HEAD").strip(), "HEAD 没建起来")

    def _fresh_check(self, rule: str):
        """取该闸的违例并验它**不是崩溃冒充**（t-167：detail/message 里不许有 crash）。"""
        # ocr2-741：旧写法为拼失败信息把 `_violations(self.repo)` 求值两遍（全引擎×2），
        # 且"非崩溃"只靠英文子串 `crash`/`失败`——生产改措辞就静默退化。求值一次复用；
        # 钉崩溃分支的**模板级**标记（`check crashed: ` + peer 哨兵），不是通用子串。
        found = _violations(self.repo)
        vs = [v for v in found if v.rule_id == rule]
        self.assertEqual(len(vs), 1, [v.rule_id for v in found])
        v = vs[0]
        text = str(v.message) + str(getattr(v, "detail", "") or "")
        self.assertNotIn("check crashed", text, f"{rule} 实为闸崩溃冒充判定：{text[:200]}")
        detail = getattr(v, "detail", None) or {}
        if isinstance(detail, dict):
            self.assertNotIn("（校验崩溃，未定位）", str(detail.values()),
                             f"{rule} 实为闸崩溃冒充判定：{text[:200]}")
        return v

    def _assert_gate_ran(self) -> None:
        """负测的正面：闸可达（无 GIT_UNAVAILABLE/MANIFEST_INVALID 早退）才算"没漂移"（t-166/167）。"""
        rules = _rules(self.repo)
        self.assertNotIn("GIT_UNAVAILABLE", rules, "change-set 读挂——本闸没跑，负断言 vacuous")
        self.assertNotIn("MANIFEST_INVALID", rules)

    # --- ① 符号索引 ---

    def test_cell_neutralises_backticks(self) -> None:
        """`_cell` 必须中和反引号（ocr2-618）：`_layout_block` 把 src/spec 包进
        行内代码段，反引号会提前闭合代码段 ⇒ 剩余文本渲染成活 Markdown。
        `_head`（api.md 标题）早已去反引号，表格单元走同一口径。"""
        from k3dge.engine.generated_docs import _cell

        self.assertNotIn("`", _cell("a`b"))
        self.assertIn("a", _cell("a`b"))

    def test_missing_symbol_index_is_not_a_violation(self) -> None:
        """索引不存在 ⇒ 跳过（`k3dge where` 会惰性建；缺文件不是漂移）。

        ocr2-468：`_assert_gate_ran()` 只证闸可达，不证本规则沉默——先确证索引真的不在，
        再断言 `SYMBOL_INDEX_STALE` 不在违例里（否则"缺索引漏报"会被测成绿）。
        """
        self.assertFalse(search.index_path(self.repo).is_file(), "夹具前提：索引本就不存在")
        self._assert_gate_ran()
        self.assertNotIn("SYMBOL_INDEX_STALE", _rules(self.repo))

    def test_stale_symbol_index_is_violation(self) -> None:
        idx = search.index_path(self.repo)
        idx.parent.mkdir(parents=True, exist_ok=True)
        idx.write_text(json.dumps({"gone": [{"file": "src/core/mod.py", "line": 1}]}), encoding="utf-8")
        self._fresh_check("SYMBOL_INDEX_STALE")   # 恰好一条、非崩溃冒充（t-167）

    def test_fresh_symbol_index_passes(self) -> None:
        search.write_symbol_index(self.repo)
        self._assert_gate_ran()
        # ocr2-469：正面判据是"新索引不报"——只证可达的话，写盘器与闸的
        # build_symbol_index 字节不一致（键序/额外字段）也照样绿。
        self.assertNotIn("SYMBOL_INDEX_STALE", _rules(self.repo))

    # --- ② docs/generated/{api,domains}.md ---

    def test_stale_generated_docs_is_violation(self) -> None:
        gen = self.repo / "docs" / "generated"
        gen.mkdir(parents=True)
        (gen / "api.md").write_text("# API Reference\n\n手写的旧内容\n", encoding="utf-8")
        self._fresh_check("DOCS_GENERATED_STALE")

    def test_stale_domains_doc_is_violation_with_own_path(self) -> None:
        """ocr2-742：旧夹具只放 `api.md`——`domains.md` 缺文件时被跳过（evaluator 直接
        continue），`_fresh_check` 靠 api.md 一条就满足。只比第一条/漏掉 domains 的
        回归照样绿。两份都先写新鲜、再只改 domains.md：必须报且 file_path 就是它。"""
        from k3dge.engine import generated_docs

        manifest = Manifest.load(self.repo)
        rendered = generated_docs.render_manual_docs_content(self.repo, manifest)
        self.assertEqual(sorted(p.name for p in rendered), ["api.md", "domains.md"])
        for path, content in rendered.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        dom = self.repo / "docs" / "generated" / "domains.md"
        dom.write_text("# 手改的旧 domains\n", encoding="utf-8")
        v = self._fresh_check("DOCS_GENERATED_STALE")
        self.assertEqual(v.file_path, "docs/generated/domains.md", (v.file_path, v.detail))

    def test_fresh_generated_docs_pass(self) -> None:
        manifest = Manifest.load(self.repo)
        rendered = render_manual_docs_content(self.repo, manifest)
        # 模块 docstring 承诺的是**两份**投影；evaluator 对"渲染图里没有的路径"直接跳过
        # （missing rendered path is skipped）——`domains.md` 若从渲染图掉出去，闸会静默
        # 失去一半覆盖面而全 suite 无感（t-168）。把产出集钉死。
        names = sorted(p.name for p in rendered)
        self.assertEqual(names, ["api.md", "domains.md"], names)
        for path, content in rendered.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self._assert_gate_ran()
        # ocr2-470：正面判据是"新渲染不报"——只证可达时，尾换行/路径归一差异导致的
        # 假 stale 也会被放过。
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
        # ocr2-471：裸 `assertIn(rule_id)` 在闸崩溃（except 分支发同一 rule_id）时也绿。
        # 走 `_fresh_check` 挡崩溃冒充，并钉住 detail["peer"]，区分 peer 缺 vs self 缺。
        vs = self._fresh_check("MCP_JSON_PEER_MISSING")
        self.assertEqual(vs.detail.get("peer"), "peerx", vs.detail)

    def test_peer_declared_in_mcp_json_passes(self) -> None:
        self._write_pipeline()
        self._make_sibling()
        (self.repo / ".mcp.json").write_text(
            json.dumps({"mcpServers": {"k3dge": {}, "peerx": {}}}), encoding="utf-8"
        )
        # ocr2-472：负断言必须先证闸可达——否则 GIT_UNAVAILABLE/MANIFEST_INVALID 早退时
        # 违例表里没有本规则，`assertNotIn` 空转绿。
        self._assert_gate_ran()
        self.assertNotIn("MCP_JSON_PEER_MISSING", _rules(self.repo))

    def test_unresolvable_peer_is_not_a_violation(self) -> None:
        """sibling 不在 ⇒ 写侧本就会跳过（回退告警），闸不制造假红。"""
        self._write_pipeline(peer="nope")
        # 注意：self（k3dge）必须声明——否则 MCP_JSON_PEER_MISSING 为 self 而响，
        # 本测就不再测"unresolvable peer 跳过"（并发批次曾误改成 k3dit 即红于此）。
        (self.repo / ".mcp.json").write_text(json.dumps({"mcpServers": {"k3dge": {}}}), encoding="utf-8")
        self._assert_gate_ran()   # ocr2-473：先证闸跑了
        self.assertNotIn("MCP_JSON_PEER_MISSING", _rules(self.repo))

    def test_missing_k3dge_self_entry_is_violation(self) -> None:
        (self.repo / ".mcp.json").write_text(json.dumps({"mcpServers": {"other": {}}}), encoding="utf-8")
        self._write_pipeline(peer="nope")
        vs = self._fresh_check("MCP_JSON_PEER_MISSING")
        self.assertEqual(vs.detail.get("peer"), "k3dge", vs.detail)

    def test_no_mcp_json_is_not_a_violation(self) -> None:
        self._write_pipeline(peer="nope")
        self._assert_gate_ran()   # ocr2-474：先证闸跑了
        self.assertNotIn("MCP_JSON_PEER_MISSING", _rules(self.repo))

    def test_corrupt_mcp_json_currently_skips_peer_gate_declared(self) -> None:
        """**现状登记**（t-169）：`_check_mcp_json` 用 `load_mcp_document`——缺失与坏文件都回
        `None` ⇒ 一并"跳过"。四条正断言只钉过"文件在场"，"坏配置也能关闸"从没被声明。
        这与 t-147 收紧后的 `mcp_server_names`（坏⇒set()+WARN，fail-closed）**不一致**——
        故意先如实钉现状：哪天把这里也硬成 fail-closed，本测变红，逼改动被看见。
        """
        self._write_pipeline(peer="peerx")
        self._make_sibling(peer="peerx")
        (self.repo / ".mcp.json").write_text("{ not json", encoding="utf-8")
        rules = _rules(self.repo)
        self.assertNotIn("GIT_UNAVAILABLE", rules)     # 前提：闸可达
        self.assertNotIn("MCP_JSON_PEER_MISSING", rules)
        # 对照：合法但空的注册表**会**报（缺失≠坏；只有"读不出"被跳过）
        (self.repo / ".mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")
        self.assertIn("MCP_JSON_PEER_MISSING", _rules(self.repo))


if __name__ == "__main__":
    unittest.main()
