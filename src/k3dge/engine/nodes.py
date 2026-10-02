"""编排节点：**声明**（这一步什么性质、失败怎么办）+ **单一执行器**。

为什么单独一层：此前三步各写一套循环与失败语义——
`seal_flow.registry`（seal 动作）/ `seal.gate_fns`（seal 前置闸）/ `align._reg`（align 两相），
于是"未知 id 怎么办""失败停不停""重跑安不安全"三处各答一次。本模块把**执行**收成一份，
声明收进 `.agent/pipeline.toml` 的 `[nodes.<id>]`（缺省在 `NODE_DEFAULTS`，ADR-0026 §2.7）。

节点属性（声明，唯一源＝`NODE_DEFAULTS` ∪ `pipeline.toml`）：

    kind      projection | fact        —— projection 可幂等重算；fact 写一次即历史
    on_error  stop | rollback | continue —— 失败后停 / 回滚 / 继续下一节点
    on_rerun  （仅 kind=fact）append | reject —— 重跑是追加还是拒绝
    needs / produces  ctx 键名          —— 这一步读/写哪些上下文字段（**只声明键名**，
                                          不声明结构：表不得开始描述实现）

两条相位（守 ADR-0026 §2.1：编排的是 k3dge 自身的步）：

    precondition  fn(ctx) -> Optional[Rejection|str]   None ＝ 过
    action        fn(ctx) -> (ok, out)                 out 可为 gates.Rejection

未知 id 一律拒绝（"不让声明空转"）；失败一律经 `gates.rejection()` 正规化，
故消费方（`nextstep.GATE_NEXT`）永远拿到闭集 gate_id 而不是散文。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from k3dge.engine import gates

#: 节点属性缺省（唯一源；必须完整——下游删掉声明段也要能跑，ADR-0026 §2.7）。
NODE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    # --- seal 前置闸（**预审**：只读判定；不写盘 ⇒ projection）---
    "tasks_all_done": {"kind": "projection", "on_error": "stop"},
    "align_pass": {"kind": "projection", "on_error": "stop"},
    "guides_filled": {"kind": "projection", "on_error": "stop"},
    "adrs_all_accepted": {"kind": "projection", "on_error": "stop"},
    "adr_landed": {"kind": "projection", "on_error": "stop"},
    "adr_amend_format": {"kind": "projection", "on_error": "stop"},   # ADR amend/footnote 形态（2026-09-24）
    "docs_normalized": {"kind": "projection", "on_error": "stop"},   # 只读检测（doc_fix.scan）
    # --- seal 动作（顺序＝声明序＝ADR-0004 §2.1.9 的三相位）---
    # `satisfies`：该动作会满足哪个前置闸（声明式，供"封板清单"区分
    # "seal 自己会跑" vs "需人先办"——`align_pass` 由本动作（跑 align + 写 marker）满足）
    "full_matrix": {"kind": "projection", "on_error": "stop", "satisfies": ["align_pass"]},
    # 审计是封板的**主体**（相位 2）：seal 自己调它，不再靠外部 hook 先跑一遍。
    # 只有闭集里的 closed / degraded-manual 能过（ADR-0004 §2.1.11）。
    "audit": {"kind": "fact", "on_error": "stop", "on_rerun": "append"},
    "archive": {"kind": "fact", "on_error": "rollback", "on_rerun": "reject",
                "produces": ["archived_paths"]},                        # 归档＝写一次即历史
    # 版号在**审计正常返回后**前进（ADR-0004 §2.1.11）：bump 失败不回滚归档，只告警（§2.3）
    "version_bump": {"kind": "fact", "on_error": "continue", "on_rerun": "append"},
    # 封版提交 + 边界 tag：记录必须落在**必然产生的那次提交**上（审计常常零提交）
    "seal_record": {"kind": "fact", "on_error": "stop", "on_rerun": "append",
                    "produces": ["audit_baseline", "audit_seal_commit"]},
    "closure_note": {"kind": "projection", "on_error": "continue"},     # 清单可重生成
    "prune": {"kind": "fact", "on_error": "continue", "on_rerun": "append"},  # 派生件清理
    # --- align ---
    # `align_tasks_all_done` 曾在此声明，但 `[checks.align].preconditions` 用的 id 是
    # `tasks_all_done`（代码缺省与本仓 pipeline.toml 都是）⇒ 这条永远取不到，删（441）。
    # --- sync 链（顺序＝[checks.sync].actions 的声明序）---
    "sync_extractors": {"kind": "projection", "on_error": "continue"},   # opt-in；配置坏不挡其余步
    "reconcile_adrs": {"kind": "fact", "on_error": "continue", "on_rerun": "append",
                       "produces": ["adr_report"]},                       # 改 ADR frontmatter + 移文件
    "sync_domains": {"kind": "projection", "on_error": "stop",
                     "produces": ["changed"]},                            # spec 契约哈希 + api.md
    "sync_manual_docs": {"kind": "projection", "on_error": "stop",
                         "produces": ["docs_updated"]},
    "sync_docs_index": {"kind": "projection", "on_error": "stop"},
}


def decl(workspace: Path, node_id: str) -> Dict[str, Any]:
    """节点属性：`NODE_DEFAULTS` ← `pipeline.toml [nodes.<id>]`（下游可覆盖）。

    **深拷贝**：浅拷贝下 `satisfies`/`produces` 与 `NODE_DEFAULTS` 里是同一个 list，
    任何调用方 append 一次就污染全进程默认表（442）。
    """
    import copy

    merged = copy.deepcopy(NODE_DEFAULTS.get(node_id, {}))
    merged.update(copy.deepcopy((gates.load(workspace).get("nodes") or {}).get(node_id) or {}))
    return merged


def kind(workspace: Path, node_id: str) -> str:
    return str(decl(workspace, node_id).get("kind") or "projection")


def on_error(workspace: Path, node_id: str) -> str:
    val = str(decl(workspace, node_id).get("on_error") or "stop")
    return val if val in ("stop", "rollback", "continue") else "stop"


def satisfied_ids(workspace: Path, op: str) -> set:
    """本编排单元里"**由自己的动作满足**"的前置闸 id（读 `[nodes.*].satisfies` 声明）。

    用例：`full_matrix` 跑 align 并写 align-pass marker ⇒ `align_pass` 这个前置闸由 seal
    自己的第一个动作满足，清单里该显示 ⚙️ 而不是"需你先办"（否则误导操作者去手跑 align）。
    """
    aids = gates.actions(workspace, op)
    out: set = set()
    for aid in aids:
        sat = decl(workspace, aid).get("satisfies") or []
        if isinstance(sat, str):
            sat = [sat]                 # `satisfies = "align_pass"`：逐字符展开会产出 a/l/i… 垃圾 id（ocr-278）
        if not isinstance(sat, (list, tuple)):
            continue
        out.update(str(gid) for gid in sat)
    return out


NodeFn = Callable[[Dict[str, Any]], Any]


def run_phase(
    workspace: Path,
    op: str,
    phase: str,
    registry: Dict[str, NodeFn],
    ctx: Dict[str, Any],
) -> Tuple[bool, Any]:
    """跑一个相位的全部节点（**单一执行器**）。返回 `(ok, 首个失败或末节点输出)`。

    - `phase` ∈ {preconditions, actions}；id 列表来自声明面（`gates.preconditions/actions`）
    - 空/未配置相位 ⇒ `(True, "")`：**显式 no-op**（没有节点跑过，不等于"所有闸都过了"；
      判定由 `tests/unit/engine/test_nodes.py::test_empty_declaration_is_explicit_noop` 钉住）
    - 未知 id ⇒ 拒绝（`unknown_gate_id` / `unknown_action_id`）
    - precondition 的失败值 ⇒ `Rejection(gid, msg)`；action 的失败值 ⇒ `gates.rejection(out, aid)`
    - `on_error=continue` 的节点失败**不中断**（用于收尾类步骤），其消息并入输出
    """
    ids = (gates.preconditions(workspace, op) if phase == "preconditions"
           else gates.actions(workspace, op))
    collected: list[str] = []
    for nid in ids:
        fn = registry.get(nid)
        if fn is None:
            gid = "unknown_gate_id" if phase == "preconditions" else "unknown_action_id"
            label = "gate" if phase == "preconditions" else "action"
            return False, gates.Rejection(
                gid, f"gate contract references unknown {label} id: '{nid}'")
        try:
            out = fn(ctx)
        except Exception as exc:
            # 节点异常也要经 `gates.rejection` 正规化（文件头承诺）⇒ 消费方永远拿闭集 gate_id、
            # `[NEXT]` 照常 persist；`on_error=continue` 的节点异常也不中断（ocr-089）。
            msg = f"{type(exc).__name__}: {exc}"
            if phase == "preconditions":
                return False, gates.Rejection(nid, msg)
            rej = gates.rejection(msg, nid)
            if on_error(workspace, nid) == "continue":
                collected.append(str(rej))
                continue
            return False, rej
        if phase == "preconditions":
            if out:
                # 回调可能自带 Rejection（含自己的 gate_id）；硬编 nid 会把它丢掉，与动作分支的
                # `gates.rejection(...)` 透传不一致（docstring 声明的返回类型就是 Rejection，ocr-279）
                return False, gates.rejection(out, nid)
            continue
        # 动作形状宽容：`(ok, out)`（seal 动作）或 `Optional[str]`（align 动作，None＝过）
        if isinstance(out, tuple):
            ok, payload = out
        elif out is None or out is True:
            ok, payload = True, ""
        elif out is False:
            ok, payload = False, ""
        else:
            ok, payload = False, out
        if ok:
            collected.append(str(payload or ""))
            continue
        rej = gates.rejection(payload, nid)
        if on_error(workspace, nid) == "continue":
            collected.append(str(rej))
            continue
        return False, rej
    return True, "\n".join(collected)   # 混装 payload 与拒绝消息，无分隔符会黏成一行读不出（445）
