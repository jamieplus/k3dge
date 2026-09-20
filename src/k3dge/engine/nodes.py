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
    # --- seal 前置闸（只读判定；不写盘 ⇒ projection）---
    "tasks_all_done": {"kind": "projection", "on_error": "stop"},
    "audit_closed": {"kind": "projection", "on_error": "stop"},
    "evidence_chain": {"kind": "projection", "on_error": "stop"},
    "align_pass": {"kind": "projection", "on_error": "stop"},
    "guides_filled": {"kind": "projection", "on_error": "stop"},
    "adrs_all_accepted": {"kind": "projection", "on_error": "stop"},
    "adr_landed": {"kind": "projection", "on_error": "stop"},
    "docs_normalized": {"kind": "projection", "on_error": "stop"},   # 只读检测（doc_fix.scan）
    "audit_fresh": {"kind": "projection", "on_error": "stop"},       # 只读检测（报告基线 vs HEAD）
    # --- seal 动作 ---
    "full_matrix": {"kind": "projection", "on_error": "stop"},          # 跑矩阵 + 抹 align stub
    "archive": {"kind": "fact", "on_error": "rollback", "on_rerun": "reject",
                "produces": ["archived_paths"]},                        # 归档＝写一次即历史
    "closure_note": {"kind": "projection", "on_error": "continue"},     # 清单可重生成
    "prune": {"kind": "fact", "on_error": "continue", "on_rerun": "append"},  # 派生件清理
    # --- align ---
    "align_tasks_all_done": {"kind": "projection", "on_error": "stop"},
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
    """节点属性：`NODE_DEFAULTS` ← `pipeline.toml [nodes.<id>]`（下游可覆盖）。"""
    merged = dict(NODE_DEFAULTS.get(node_id, {}))
    merged.update((gates.load(workspace).get("nodes") or {}).get(node_id) or {})
    return merged


def kind(workspace: Path, node_id: str) -> str:
    return str(decl(workspace, node_id).get("kind") or "projection")


def on_error(workspace: Path, node_id: str) -> str:
    val = str(decl(workspace, node_id).get("on_error") or "stop")
    return val if val in ("stop", "rollback", "continue") else "stop"


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
    - 未知 id ⇒ 拒绝（`unknown_gate_id` / `unknown_action_id`）
    - precondition 的失败值 ⇒ `Rejection(gid, msg)`；action 的失败值 ⇒ `gates.rejection(out, aid)`
    - `on_error=continue` 的节点失败**不中断**（用于收尾类步骤），其消息并入输出
    """
    from k3dge.engine import gates as _gates

    ids = (_gates.preconditions(workspace, op) if phase == "preconditions"
           else _gates.actions(workspace, op))
    collected: list[str] = []
    for nid in ids:
        fn = registry.get(nid)
        if fn is None:
            gid = "unknown_gate_id" if phase == "preconditions" else "unknown_action_id"
            label = "gate" if phase == "preconditions" else "action"
            return False, gates.Rejection(
                gid, f"gate contract references unknown {label} id: '{nid}'")
        out = fn(ctx)
        if phase == "preconditions":
            if out:
                return False, gates.Rejection(nid, str(out))
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
    return True, "".join(collected)
