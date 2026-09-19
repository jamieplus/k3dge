"""闸红文案与档位的**单一声明面**（B 线：自动 → 自主）。

零依赖（stdlib only）：`scripts/pre-commit` 与 engine 都要能加载，口径同
`pure_schema` / `pure_refs`（工具坏不得阻断所有提交）。

内容/流程解耦（用户裁定 2026-09-19；ADR-0026 §2.2/§2.3）：

    检查器   只产 (code, 结构化事实)      —— 不知道文案，不拼串
    本表     code → severity/fact/options/pointers —— 不知道检查器内部，只吃事实的键名
    渲染器   一份实现，两个投影：
             给进程     → `projection()`  闭集 dict（code + severity + 事实），可机械分支
             给判断主体 → `render()`      陈述式 fact + 成对 options + pointers

形态不变量（与 `nextstep.TestProjectionInvariants` 同口径，由 test_gate_facts 守）：
  1. `fact` / `options` 不得是疑问句——纯打印面无应答通道，且疑问句会把预设嵌进句式，
     变成带主观偏见的引导性话术（ADR-0026 §2.2 语法维）。
  2. `severity=block` 的 code 必须给 ≥2 个 options（只给一条路＝下令，不是给判断主体）。
  3. 档位是**声明**，不是代码分支：`block|warn|observe` 只在这里定义，
     消费者（hook / CLI / MCP）一律查表，不得自己写"WARN-only"这类散文档位。

未声明的 code 走 `DEFAULT_SEVERITY` 且由调用方自己的 message 兜底——**迁移是增量的**，
不要求一次把全部 code 搬进表（搬一个就少一处手拼串）。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

#: 档位闭集（唯一源）。block=拦提交/红闸；warn=显示但不拦；observe=观测建议，不判定。
SEVERITIES: tuple = ("block", "warn", "observe")
DEFAULT_SEVERITY = "block"

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


class _SafeFacts(dict):
    """缺失键原样留 `{key}`，不抛——文案模板不得因为少一个事实字段就崩掉渲染。"""

    def __missing__(self, key):  # noqa: D105
        return "{" + key + "}"


#: code → 声明。`fact`/`options`/`pointers` 支持 `{key}` 占位，由检查器给的 `facts` 填。
GATE_FACTS: Dict[str, Dict[str, Any]] = {
    # --- block：拦下并要求判断主体选一条路 ---
    "CONTRACT_DRIFT": {
        "severity": "block",
        "fact": "公有接口变了，spec 的契约哈希没跟上（spec={expected_hash} ≠ code={actual_hash}）；"
                "哈希由 `k3dge sync` 回写，不手写",
        "options": [
            "k3dge sync（回写契约哈希 + 重生 docs/generated）",
            "接口本不该变 → 回退代码改动，再跑 k3dge check",
        ],
        "pointers": ["AGENTS.md Core Invariants 2", "k3dge sync"],
    },
    "DOC_NEW_UNSCREENED": {
        "severity": "block",
        "fact": "新建受管文档 `{path}`（主观撰写类）未经重复/覆盖排查——首次提交拦一次，回执后不再提示。"
                "值不值得建由你判（进程判不了语义覆盖与子项关系），本闸只负责把排查送到动手这一刻",
        "options": [
            "并入既存 → 目标文档收编本节、删掉本文件、写并入说明，再 k3dge sync",
            "确认新建 → k3dge doc screen {path}",
            "指明并入目标 → k3dge doc screen {path} --into docs/<type>/<target>.md",
        ],
        "pointers": ["AGENTS.md §12", "docs/adr/AUTHORING.md「先并入，后新建」", "k3dge doc list --type <type>"],
    },
    # --- warn：显示但不拦（孤儿＝可能是有意的新增，判定归人）---
    "ORPHAN_TEST": {
        "severity": "warn",
        "fact": "`{path}` 没有被任何 Verification Matrix 行引用——测试存在但不在验证面上",
        "options": [
            "在对应 spec 的 Verification Matrix 里补一行引用它",
            "确认是有意留（探索性/临时测试）→ 不处理，本条只观测不拦",
        ],
        "pointers": ["docs/specs/<domain>/spec.md", "k3dge ADR-0005 §2.5"],
    },
    "ORPHAN_SPEC": {
        "severity": "warn",
        "fact": "`{path}` 没有被 manifest 的任何域引用——spec 存在但不是任何域的判据",
        "options": [
            "在 .agent/manifest.json 的域里补 spec 指针",
            "确认是有意留（跨域说明/模板）→ 不处理，本条只观测不拦",
        ],
        "pointers": [".agent/manifest.json", "k3dge ADR-0005 §2.8"],
    },
    # --- observe：观测建议，不阻断、不裁决（service 角色；peer 不可达即无提示）---
    "DUP_CHECK": {
        "severity": "observe",
        "fact": "新建票据与集存内容可能重复（候选见下）——是不是真重复由你判，本条不阻断、不裁决",
        "options": [
            "确属重复 → 并入既存票据（`k3dge task done <旧票>` 记关闭理由），不新开",
            "确属新事 → 保留本票，无需动作",
        ],
        "pointers": ["docs/tasks/AUTHORING.md", "k3dge task list --json"],
    },
    "ORPHAN_ADR": {
        "severity": "warn",
        "fact": "`{path}` 未列入 docs/adr/README.md 的 Topics——决策存在但索引找不到它",
        "options": [
            "在 README 的 Topics 里补一行（按类归入）",
            "该 ADR 已退役 → 移入 docs/adr/obsolete/（reconcile 由 k3dge sync 跑）",
        ],
        "pointers": ["docs/adr/README.md", "docs/adr/AUTHORING.md"],
    },
}


def is_declared(code: str) -> bool:
    """该 code 是否已进声明表（未进 ⇒ 调用方用自己的 message 兜底）。"""
    return code in GATE_FACTS


def severity(code: str) -> str:
    """档位唯一源：查表；未声明按 `DEFAULT_SEVERITY`。消费者不得自己判档位。"""
    decl = GATE_FACTS.get(code) or {}
    sev = str(decl.get("severity") or DEFAULT_SEVERITY)
    return sev if sev in SEVERITIES else DEFAULT_SEVERITY


def fill(template: str, facts: Optional[Dict[str, Any]]) -> str:
    """把 `{key}` 用检查器给的结构化事实填上；缺失键原样留着（不抛）。"""
    if not template:
        return ""
    if not facts:
        return template
    try:
        return template.format_map(_SafeFacts({k: v for k, v in facts.items() if v is not None}))
    except (ValueError, IndexError):  # 模板里有非占位的花括号
        return _PLACEHOLDER.sub(lambda m: str(facts.get(m.group(1), m.group(0))), template)


def render(code: str, facts: Optional[Dict[str, Any]] = None, *, where: str = "") -> str:
    """给**判断主体**的投影：陈述式 fact + 成对 options + pointers（不出疑问句）。

    `where` = 位置（文件/域），有则挂在首行末尾，与 `[GATE ERROR] … [path]` 的旧形状兼容。
    """
    decl = GATE_FACTS.get(code)
    if not decl:
        return ""
    lines = [f"fact: {fill(str(decl.get('fact', '')), facts)}"]
    for opt in decl.get("options") or []:
        lines.append(f"option: {fill(str(opt), facts)}")
    ptrs = [fill(str(p), facts) for p in (decl.get("pointers") or [])]
    if ptrs:
        lines.append("pointers: " + " | ".join(ptrs))
    head = f"[{code}]" + (f" {where}" if where else "")
    return head + "\n" + "\n".join("  " + ln for ln in lines)


def projection(code: str, facts: Optional[Dict[str, Any]] = None) -> dict:
    """给**进程**的投影：闭集（code + severity + 事实），无文案、无分支余地。"""
    return {
        "code": code,
        "severity": severity(code),
        "declared": is_declared(code),
        "facts": dict(facts or {}),
    }


def facts_of(code: str) -> List[str]:
    """声明里用到的占位键名（供守卫测试核对检查器是否真给了这些事实）。"""
    decl = GATE_FACTS.get(code) or {}
    keys: List[str] = []
    for text in [str(decl.get("fact", ""))] + [str(o) for o in (decl.get("options") or [])]:
        for m in _PLACEHOLDER.finditer(text):
            if m.group(1) not in keys:
                keys.append(m.group(1))
    return keys
