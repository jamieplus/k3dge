"""编排节点：声明（kind/on_error/on_rerun）+ 单一执行器 run_phase。

为何要这一层：此前 seal 动作 / seal 前置闸 / align 两相各写一套循环与失败语义
⇒ "未知 id 怎么办""失败停不停""重跑安不安全"三处各答一次（票 orch_node_table）。
"""

import ast
import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from k3dge.engine import gates, nodes

_REPO = Path(__file__).resolve().parents[3]


def _ws(d: Path) -> Path:
    (d / ".agent").mkdir(parents=True, exist_ok=True)
    return d


def _write_ws(d: Path, body: str) -> Path:
    _ws(d)
    (d / ".agent" / "pipeline.toml").write_text(body, encoding="utf-8")
    return d


class _WsBodyMixin:
    """带 pipeline.toml 正文的临时工作区（两类共用，修一处即可——ocr t-202）。"""

    def _ws_with(self, body: str) -> Path:
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return _write_ws(d, body)


class TestNodeDeclaration(unittest.TestCase):
    def test_defaults_cover_known_nodes(self):
        for nid, decl in nodes.NODE_DEFAULTS.items():
            self.assertIn(decl.get("kind"), ("projection", "fact"), nid)
            self.assertIn(decl.get("on_error"), ("stop", "rollback", "continue"), nid)
            if decl.get("kind") == "fact":
                self.assertIn(decl.get("on_rerun"), ("append", "reject"), nid)   # fact 必声明重跑语义

    def test_every_default_node_is_referenced(self):
        """可达性交叉核对：NODE_DEFAULTS 里每条都必须被某个 `[checks.*]` 相位引用。

        bug 类有先例：`align_tasks_all_done`（441 删）——缺省表里有 id，但没有任何
        `[checks.*]` 引用它 ⇒ 声明永远取不到，静默空转。
        """
        referenced: set = set()
        for source in (gates.DEFAULTS, gates.load(_REPO)):
            for op, sec in (source.get("checks") or {}).items():
                if not isinstance(sec, dict):
                    continue
                for phase in ("preconditions", "actions"):
                    referenced.update(str(v) for v in (sec.get(phase) or []))
        orphans = sorted(set(nodes.NODE_DEFAULTS) - referenced)
        self.assertEqual(orphans, [], "NODE_DEFAULTS 条目没被任何 [checks.*] 相位引用（陈旧声明）")

    def test_downstream_can_override(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        ws = _write_ws(d, '[nodes.archive]\nkind = "projection"\non_error = "continue"\n')
        decl = nodes.decl(ws, "archive")
        self.assertEqual(decl["kind"], "projection")
        self.assertEqual(decl["on_error"], "continue")
        # 合并语义＝逐键覆盖：未覆盖的缺省键必须存活（ocr t-195）。
        # 回归成"整段替换"（merged = declared）会在这里红，而不是被上面两行蒙过。
        default = nodes.NODE_DEFAULTS["archive"]
        self.assertEqual(decl.get("on_rerun"), default["on_rerun"])
        self.assertEqual(decl.get("produces"), default["produces"])

    def test_decl_returns_deep_copy_not_process_shared(self):
        """`decl()` 深拷贝（442）：调用方改一次返回的 list，不得污染进程级缺省表。"""
        snapshot = copy.deepcopy(nodes.NODE_DEFAULTS["archive"])
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        ws = _write_ws(d, "")
        first = nodes.decl(ws, "archive")
        first["produces"].append("junk")
        first["kind"] = "poison"
        self.assertEqual(nodes.NODE_DEFAULTS["archive"], snapshot)
        self.assertEqual(nodes.decl(ws, "archive")["produces"], snapshot["produces"])

    def test_missing_declaration_falls_back_to_defaults(self):
        """缺省回落在表上对账，不再抄字面量（ocr t-196：字面量＝把缺省复制一遍）。"""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        ws = _write_ws(d, "")
        for nid in ("archive", "seal_record"):
            self.assertEqual(nodes.kind(ws, nid), nodes.NODE_DEFAULTS[nid]["kind"], nid)
            self.assertEqual(nodes.on_error(ws, nid), nodes.NODE_DEFAULTS[nid]["on_error"], nid)
        # 真正要紧的两个兜底分支：缺省表没有的 id ⇒ kind 落到 projection、on_error 落到 stop
        self.assertEqual(nodes.kind(ws, "ghost_node"), "projection")
        self.assertEqual(nodes.on_error(ws, "ghost_node"), "stop")

    def test_on_error_off_whitelist_coerced_to_stop(self):
        """on_error 写进非闭集的值 ⇒ 强制回 stop（fail-closed），不是原样透传。"""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        ws = _write_ws(d, '[nodes.archive]\non_error = "explode"\n')
        self.assertEqual(nodes.on_error(ws, "archive"), "stop")

    def test_repo_declares_same_values_as_defaults(self):
        """自举：本仓声明段 == 代码缺省（声明是显式化，不是偷偷改语义）。

        重言式陷阱（ocr t-194）：`decl()` ＝ 缺省 merge 声明，**没声明**的 id 两边
        平凡相等 ⇒ 单靠逐 id 比较永远绿。本测把不变量拆成可失败的四条：
        ① 声明段必须存在（删光 `[nodes.*]` 即红）；② 声明的 id 必须在缺省表里
        （`[nodes.archve]` 这类拼错段即红）；③ 段内不得为空壳；④ 每个声明键与
        缺省值逐键相等。
        """
        declared = gates.load(_REPO).get("nodes") or {}
        self.assertTrue(declared, "pipeline.toml 一个 [nodes.*] 段都没声明")
        unknown = sorted(nid for nid in declared if nid not in nodes.NODE_DEFAULTS)
        self.assertEqual(unknown, [], "[nodes.<id>] 不在 NODE_DEFAULTS（拼错/未清的旧段）")
        for nid, sec in declared.items():
            self.assertTrue(sec, f"[nodes.{nid}] 是空壳段（有段头没键，声明空转）")
            for key, val in sec.items():
                self.assertIn(key, nodes.NODE_DEFAULTS[nid], f"{nid}.{key} 不是已知键")
                self.assertEqual(val, nodes.NODE_DEFAULTS[nid][key], f"{nid}.{key}")
        for nid in nodes.NODE_DEFAULTS:
            self.assertEqual(nodes.decl(_REPO, nid), nodes.NODE_DEFAULTS[nid], nid)


class TestRunPhase(_WsBodyMixin, unittest.TestCase):
    """单一执行器：未知 id 拒绝、两相形状宽容、失败语义按声明。"""

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

    def test_empty_declaration_is_explicit_noop(self):
        """空/未配置相位 ⇒ `(True, "")`：钉住**显式 no-op** 判定（ocr t-205）。

        这不是"所有闸都过了"——没有任何节点跑过。若哪天改成 fail-closed 拒空声明，
        必须连这条一起翻，别让"未配置的编排单元"静默读成绿灯。
        """
        ws = self._ws_with('[checks.demo]\npreconditions = []\n')
        ok, out = nodes.run_phase(ws, "demo", "preconditions", {}, {})
        self.assertTrue(ok)
        self.assertEqual(out, "")

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

    def test_rollback_verdict_aborts_not_continues(self):
        """`rollback` 在执行器里的判定＝中断（与 stop 同形，ocr t-197）。

        钉住它：`run_phase` 只对 `continue` 分支特殊处理，将来若把 rollback 悄悄
        映射成 continue（归档失败不再阻断 seal），本测先红。本仓 archive 声明的
        就是 rollback——两侧都钉。
        """
        self.assertEqual(nodes.on_error(_REPO, "archive"), "rollback")
        ws = self._ws_with('[checks.demo]\nactions = ["boom", "after"]\n'
                           '[nodes.boom]\nkind = "fact"\non_error = "rollback"\n')
        calls = []
        reg = {"boom": lambda _c: calls.append("boom") or (False, "归档失败"),
               "after": lambda _c: calls.append("after") or (True, "")}
        ok, out = nodes.run_phase(ws, "demo", "actions", reg, {})
        self.assertFalse(ok)
        self.assertEqual(calls, ["boom"])
        self.assertEqual(out.gate_id, "boom")

    def test_ctx_is_passed_to_nodes(self):
        """执行器把 ctx **整体**交给每个节点（ocr t-203：needs/produces 只声明键名，
        不做结构过滤——本测钉"交进去的全部到得了"，不冒认 needs/produces 语义）。

        判定先看：相位若中断就明报，不让它裸 `KeyError: 'milestone_id'` 猜原因。
        """
        ws = self._ws_with('[checks.demo]\nactions = ["peek"]\n')
        ctx = {"milestone_id": "M7", "pending": [1, 2]}
        seen = {}
        reg = {"peek": lambda c: (seen.update(c) or True, "")}
        ok, out = nodes.run_phase(ws, "demo", "actions", reg, ctx)
        self.assertTrue(ok, out)
        self.assertEqual(seen, ctx)


class TestRepoRegistriesUseTheSingleExecutor(unittest.TestCase):
    """结构守卫：分派循环只剩钉住的几处（ocr t-200）。

    原守卫是子串比对（变量名一换/一折行即绕过，且 `seal.py` 真的用 `for gid in ...`
    漏过了检查）⇒ 换成 AST 走全仓：凡 For/comprehension 迭代 `gates.preconditions`
    /`gates.actions`（直接调用，或先赋值给变量再迭代）都算站点，白名单逐 (模块, 函数)：
    · `nodes.run_phase` —— 单一执行器（正向检查它还在，守卫自身没瞎）
    · `nodes.satisfied_ids` —— 声明投影列表
    · `seal.seal_checklist` —— 全量清单投影（逐条收集、不中断判定；与执行器的
      "停在首个失败"语义不同，所以留它，但形状不变量由本测钉死不再长第二处）
    """

    _ALLOWED = {
        ("engine/nodes.py", "run_phase"),
        ("engine/nodes.py", "satisfied_ids"),
        ("engine/seal.py", "seal_checklist"),
    }

    @staticmethod
    def _is_gates_list_call(node: ast.AST) -> bool:
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "gates"
                and node.func.attr in ("preconditions", "actions"))

    def _dispatch_sites(self, root: Path) -> set:
        sites = set()
        for py in sorted(root.rglob("*.py")):
            if "__pycache__" in py.parts:
                continue
            tree = ast.parse(py.read_text(encoding="utf-8"))
            parents: dict = {}
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    parents[child] = node
            bound = set()   # 绑过 gates.preconditions/actions 返回值的变量名
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and any(
                        self._is_gates_list_call(v) for v in ast.walk(node.value)):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            bound.add(t.id)
            for node in ast.walk(tree):
                it = node.iter if isinstance(node, (ast.For, ast.comprehension)) else None
                if it is None:
                    continue
                if not (self._is_gates_list_call(it)
                        or (isinstance(it, ast.Name) and it.id in bound)):
                    continue
                fn = "module"
                cur = parents.get(node)
                while cur is not None and not isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    cur = parents.get(cur)
                if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fn = cur.name
                sites.add((py.relative_to(root).as_posix(), fn))
        return sites

    def test_only_pinned_sites_iterate_gate_lists(self):
        sites = self._dispatch_sites(_REPO / "src" / "k3dge")
        self.assertIn(("engine/nodes.py", "run_phase"), sites,
                      "正向检查：单一执行器的循环还在 nodes.run_phase（守卫别瞎）")
        offenders = sorted(sites - self._ALLOWED)
        self.assertEqual(offenders, [], "出现未钉住的分派循环——编排必须走 nodes.run_phase")


class TestSatisfiesAndRejectionShape(_WsBodyMixin, unittest.TestCase):
    """`satisfies` 的取值形状与前置闸拒绝的 gate_id 透传（ocr-278/279）。"""

    def test_bare_string_satisfies_is_one_id_not_chars(self):
        """用**没有缺省 satisfies 的 id**（audit）证明裸串分支真的在起作用（ocr t-198）。

        若沿用缺省表里的 `full_matrix`，它的缺省 `satisfies = ["align_pass"]` 会让
        断言在"裸串处理被删掉"时依然绿。seal 动作收窄到只剩 audit ⇒ 只有声明生效
        才会有 `align_pass`。
        """
        ws = self._ws_with('[checks.seal]\nactions = ["audit"]\n'
                           '[nodes.audit]\nsatisfies = "align_pass"\n')
        self.assertEqual(nodes.satisfied_ids(ws, "seal"), {"align_pass"})

    def test_non_iterable_satisfies_is_ignored(self):
        """精确集合断言（ocr t-199）：`assertNotIn("7", …)` 在 `{7}`（int 漏进）时同样绿。"""
        ws = self._ws_with('[checks.seal]\nactions = ["audit"]\n'
                           '[nodes.audit]\nsatisfies = 7\n')
        self.assertEqual(nodes.satisfied_ids(ws, "seal"), set())

    def test_empty_string_satisfies_is_nothing(self):
        ws = self._ws_with('[checks.seal]\nactions = ["audit"]\n'
                           '[nodes.audit]\nsatisfies = ""\n')
        self.assertEqual(nodes.satisfied_ids(ws, "seal"), set())

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


if __name__ == "__main__":
    unittest.main()
