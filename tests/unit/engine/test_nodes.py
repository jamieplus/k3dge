"""编排节点：声明（kind/on_error/on_rerun）+ 单一执行器 run_phase。

为何要这一层：此前 seal 动作 / seal 前置闸 / align 两相各写一套循环与失败语义
⇒ "未知 id 怎么办""失败停不停""重跑安不安全"三处各答一次（票 orch_node_table）。
"""

import tempfile
import unittest
from pathlib import Path

from k3dge.engine import gates, nodes


def _ws(d: Path) -> Path:
    (d / ".agent").mkdir(parents=True, exist_ok=True)
    return d


class TestNodeDeclaration(unittest.TestCase):
    def test_defaults_cover_known_nodes(self):
        for nid, decl in nodes.NODE_DEFAULTS.items():
            self.assertIn(decl.get("kind"), ("projection", "fact"), nid)
            self.assertIn(decl.get("on_error"), ("stop", "rollback", "continue"), nid)
            if decl.get("kind") == "fact":
                self.assertIn(decl.get("on_rerun"), ("append", "reject"), nid)   # fact 必声明重跑语义

    def test_downstream_can_override(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(Path(d))
            (ws / ".agent" / "pipeline.toml").write_text(
                '[nodes.archive]\nkind = "projection"\non_error = "continue"\n', encoding="utf-8")
            decl = nodes.decl(ws, "archive")
            self.assertEqual(decl["kind"], "projection")
            self.assertEqual(decl["on_error"], "continue")

    def test_missing_declaration_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(Path(d))
            self.assertEqual(nodes.kind(ws, "archive"), "fact")
            self.assertEqual(nodes.on_error(ws, "archive"), "rollback")

    def test_repo_declares_same_values_as_defaults(self):
        """自举：本仓声明段 == 代码缺省（声明是显式化，不是偷偷改语义）。"""
        repo = Path(__file__).resolve().parents[3]
        for nid in nodes.NODE_DEFAULTS:
            self.assertEqual(nodes.decl(repo, nid), nodes.NODE_DEFAULTS[nid], nid)


class TestRunPhase(unittest.TestCase):
    """单一执行器：未知 id 拒绝、两相形状宽容、失败语义按声明。"""

    def _ws_with(self, body: str) -> Path:
        d = Path(tempfile.mkdtemp())
        _ws(d)
        (d / ".agent" / "pipeline.toml").write_text(body, encoding="utf-8")
        return d

    def test_preconditions_stop_at_first_failure(self):
        ws = self._ws_with('[checks.demo]\npreconditions = ["a_ok", "b_bad", "c_never"]\n')
        calls = []
        reg = {
            "a_ok": lambda _c: calls.append("a") or None,
            "b_bad": lambda _c: calls.append("b") or "坏了",
            "c_never": lambda _c: calls.append("c") or None,
        }
        ok, out = nodes.run_phase(ws, "demo", "preconditions", reg, {})
        self.assertFalse(ok)
        self.assertEqual(calls, ["a", "b"])              # 停在第一个失败
        self.assertEqual(out.gate_id, "b_bad")           # id 即契约里声明的那个
        self.assertIn("坏了", str(out))

    def test_unknown_id_is_rejected(self):
        ws = self._ws_with('[checks.demo]\npreconditions = ["ghost"]\n')
        ok, out = nodes.run_phase(ws, "demo", "preconditions", {}, {})
        self.assertFalse(ok)
        self.assertEqual(out.gate_id, "unknown_gate_id")

    def test_actions_accept_both_shapes(self):
        """`(ok, out)`（seal 动作）与 `Optional[str]`（align 动作）都要能跑。"""
        ws = self._ws_with('[checks.demo]\nactions = ["tuple_ok", "str_ok"]\n')
        reg = {"tuple_ok": lambda _c: (True, "done"), "str_ok": lambda _c: None}
        ok, out = nodes.run_phase(ws, "demo", "actions", reg, {})
        self.assertTrue(ok)
        self.assertIn("done", out)

    def test_continue_does_not_abort(self):
        ws = self._ws_with('[checks.demo]\nactions = ["boom", "after"]\n'
                           '[nodes.boom]\nkind = "fact"\non_error = "continue"\n')
        calls = []
        reg = {"boom": lambda _c: calls.append("boom") or (False, "清理失败"),
               "after": lambda _c: calls.append("after") or (True, "")}
        ok, out = nodes.run_phase(ws, "demo", "actions", reg, {})
        self.assertTrue(ok)
        self.assertEqual(calls, ["boom", "after"])       # continue ⇒ 不中断
        self.assertIn("清理失败", out)                    # 消息并入输出

    def test_stop_aborts(self):
        ws = self._ws_with('[checks.demo]\nactions = ["boom", "after"]\n')
        calls = []
        reg = {"boom": lambda _c: calls.append("boom") or (False, "炸了"),
               "after": lambda _c: calls.append("after") or (True, "")}
        ok, out = nodes.run_phase(ws, "demo", "actions", reg, {})
        self.assertFalse(ok)
        self.assertEqual(calls, ["boom"])
        self.assertEqual(out.gate_id, "boom")

    def test_ctx_is_passed_to_nodes(self):
        """`needs/produces` 声明的 ctx 字段是真的被传进去的（不是装饰）。"""
        ws = self._ws_with('[checks.demo]\nactions = ["peek"]\n')
        seen = {}
        reg = {"peek": lambda ctx: (seen.update(ctx) or True, "")}
        nodes.run_phase(ws, "demo", "actions", reg, {"milestone_id": "M7", "pending": [1, 2]})
        self.assertEqual(seen["milestone_id"], "M7")
        self.assertEqual(seen["pending"], [1, 2])


class TestRepoRegistriesUseTheSingleExecutor(unittest.TestCase):
    """结构守卫：三个旧注册表不再各写自己的循环。

    做法：断言那三处的循环已消失（`for aid in gates.actions` / `for _gid in gates.preconditions`
    只允许出现在 nodes.run_phase 里），逼迫后续新编排也走单一执行器。
    """

    def test_no_hand_written_dispatch_loops_left(self):
        root = Path(__file__).resolve().parents[3] / "src" / "k3dge"
        offenders = []
        for rel in ("engine/seal.py", "engine/seal_flow.py", "engine/align.py"):
            text = (root / rel).read_text(encoding="utf-8")
            for pat in ("for _gid in gates.preconditions", "for aid in gates.actions",
                        "for _aid in gates.actions"):
                if pat in text:
                    offenders.append(f"{rel}: {pat}")
        self.assertEqual(offenders, [])


class TestSatisfiesAndRejectionShape(unittest.TestCase):
    """`satisfies` 的取值形状与前置闸拒绝的 gate_id 透传（ocr-278/279）。"""

    def _ws_with(self, body: str) -> Path:
        ws = _ws(Path(tempfile.mkdtemp()))
        (ws / ".agent" / "pipeline.toml").write_text(body, encoding="utf-8")
        return ws

    def test_bare_string_satisfies_is_one_id_not_chars(self):
        ws = self._ws_with('[nodes.audit]\nsatisfies = "align_pass"\n')
        ids = nodes.satisfied_ids(ws, "seal")
        self.assertIn("align_pass", ids)
        self.assertFalse([g for g in ids if len(g) < 2], ids)

    def test_non_iterable_satisfies_is_ignored(self):
        ws = self._ws_with('[nodes.audit]\nsatisfies = 7\n')
        self.assertNotIn("7", nodes.satisfied_ids(ws, "seal"))

    def test_precondition_rejection_keeps_its_gate_id(self):
        ws = self._ws_with('[checks.seal]\npreconditions = ["g_custom"]\n')
        ok, rej = nodes.run_phase(ws, "seal", "preconditions",
                                  {"g_custom": lambda ctx: gates.Rejection("MY_GATE", "nope")}, {})
        self.assertFalse(ok)
        self.assertEqual(getattr(rej, "gate_id", None), "MY_GATE")

    def test_precondition_plain_string_falls_back_to_node_id(self):
        ws = self._ws_with('[checks.seal]\npreconditions = ["g_txt"]\n')
        ok, rej = nodes.run_phase(ws, "seal", "preconditions",
                                  {"g_txt": lambda ctx: "still bad"}, {})
        self.assertFalse(ok)
        self.assertEqual(getattr(rej, "gate_id", None), "g_txt")
