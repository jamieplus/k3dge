"""Single-source `next-step` hints appended to k3dge command outputs.

Why: an agent reads a tool's *return value* in the same turn, not AGENTS.md.
Commands therefore end with a fixed-shape `[NEXT]` line (CLI) / `next` field
(MCP) so the operator knows the legal next action without re-deriving SOP.

Single source: every option string lives ONLY in `STATE_OPTIONS` (and the
rejection routing table `GATE_NEXT`). Commands never hand-write their own
playbook — they call `NextStep.from_state(...)` / `question_text(...)` /
`next_for_rejection(...)`, which derive from the same state machine as
`pipeline.toml` / `AGENTS.md`.

Rejection routing is **closed-set**: a rejection carries a `gate_id`
(`gates.Rejection`, a str subclass) and `GATE_NEXT` maps id → (state, note).
No prose substring matching — wording changes must not be able to silently
break the branch (memo §S7: 投影给进程的判定必须是闭集；参见 A-01 前科).

Shape (CLI) — 陈述句投影，**疑问句只在 prompt 侧**（`question_text()`；`[NEXT]` 里没有 ask/if）:
    [NEXT] state=<state> milestone=<id>[ pending=<n>]
      reason: <一条一项>        (有则列)
      fact: <事实陈述>
      option: <可选动作>        (成对出现，决策类)
      pointers: <指针 | 指针>

MCP isomorphic JSON: {"next": {"state", "milestone", "priority", "pending"?, "reasons"?,
"fact"?, "options"?, "question"?, "pointers"?}}（`priority` 也在卡里，读侧按它排序）

Constraints (design review):
  - success -> state; failure -> action. Never decide for the human.
  - only legal options, no "now execute seal".
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TextIO

# 单一源：一个判定 = 一条声明，两个投影（ADR-0026 §2.2）：
#   fact     陈述句事实 → `[NEXT]`（纯打印面，无应答通道；不用疑问句——疑问句不客观
#            反映事实，会变成带预设的引导性话术）+ 决策权归属
#   options  合法选项（≥ 2，否则＝只给一条路＝下令）；不替判断主体选
#   question 疑问句 → **只**给 `prompt.ask`（有 stdin 应答通道），与 fact 同一判定的另一投影
# `pointers` = 纵深指针（doc id / ADR 节 / 命令），推"去哪取细节"而非灌正文（ADR-0008 §2）。
#: `priority`（闭集，唯一源）＝同一轮命中多个处理点时的"先看哪个"（**建议，不是执行顺序**；
#: k3dge 不编排自主工作流，ADR-0026 §2.6）：
#:   1 需人立即介入（pending_findings 钉未处置 / escalated 转人工）
#:   2 环未闭环，不处理无法前进（audit_open / audit_needed）
#:   3 操作被拒（rejected）
#:   4 决策点，可做可不做（seal_ready / audit_suggested / new_domain）
#:   5（空档；原 ratchet_open 已随棘轮形状退休）
#:   9 播报，无需动作（normal / sealed / seal_declined）
#:
#: 播报态（无 options）：只陈述事实 + 指针，不给分支。
STATE_OPTIONS: dict = {
    "normal": {
        "priority": 9,"fact": "常规提交门禁通过", "pointers": ["AGENTS.md §12"]},
    "pending_findings": {
        "priority": 1,
        "fact": "代码/文档里有 findings 钉（`k3dit:pending`）未处置；怎么处置由你决定",
        "options": [
            "修完删 `k3dit:pending <ID>` 标记",
            "有意留 → 改成 `k3dit:leftover <ID>` 指针（处置仍以 12 列报告 + tasks 为准，标记只是指针）",
            "本轮不处理（钉仍在，下次照旧提示）",
        ],
        "pointers": ["peer_contract §8", "k3dge ADR-0025"],
    },
    "audit_suggested": {
        "priority": 4,
        "fact": "里程碑 <id> 命中审计触发条件（reason 见上）；审与不审由你决定",
        "options": [
            "k3dge milestone audit <id>（必审，待修=0 才谈封板）",
            "不审，继续干活（触发条件仍在，下次照旧提示）",
        ],
        "pointers": ["k3dge ADR-0004 §2.1.5", "k3dge milestone audit <id>"],
    },
    "seal_ready": {
        "priority": 4,
        # 基础事实；**封板前置**由 `seal_ready_for()` 追加（同表另存一句，避免占位符从
        # 其它构造点漏出——`from_state("seal_ready")` 仍可单独用）
        "fact": "里程碑 <id> 形式闸与票已齐；是否收这一章由你决定（seal 会跑：预审 → 审计 → 收摊）",
        # 有未满足前置时的**另一条声明事实**：以前靠对 fact 做散文 `.replace("形式闸与票已齐",…)`
        # 修正，措辞一改就静默失效 ⇒ 闸未齐仍宣称已齐（判据与投影背离，ocr-276）。
        "fact_blocked": "里程碑 <id> 形式闸未齐（见 reasons）；先修完再 seal（seal 会跑：预审 → 审计 → 收摊）",
        "fact_with_blockers": "；预审待办：<blockers>",
        "question": "里程碑 <id>：封板？",
        "options": [
            "k3dge milestone seal <id>（预审 → 审计 → 归档+版本+指针）",
            "不封（里程碑继续挂着，当普通提交结束）",
        ],
        "pointers": ["k3dge ADR-0004 §2.1.9", "docs/reviews/"],
    },
    "doc_fix": {
        "priority": 2,
        "fact": "docs/ 有 <n> 处**可确定修**的规约偏差（<rules>）；改与不改由你决定"
                "（不改则封板前置 `docs_normalized` 会拦）",
        "options": [
            "k3dge doc fix --dry-run（先看要改哪里）",
            "k3dge doc fix（按闭集规则改；改完自己 review diff 再提交）",
            "不处理（偏差留着，封板前会被闸拦）",
        ],
        "pointers": ["docs/tasks/AUTHORING.md", "k3dge ADR-0022 §2.2"],
    },
    "audit_open": {
        "priority": 2,
        "fact": "里程碑 <id> 审计发现 <n> 项待修，环未闭环；由谁修由你决定",
        "question": "里程碑 <id>：<n> 项待修，agent 修？",
        "options": [
            "agent 修 → 修完重跑 k3dge milestone audit <id>（重审）",
            "不由 agent 修 → stop / 转人工干预",
        ],
        "pointers": ["k3dge ADR-0022", "k3dge milestone audit <id>"],
    },
    "escalated": {
        "priority": 1,
        "fact": "verify 连续 >3 次未闭环，已转人工干预（k3dge milestone audit-submit <id> 或人工复核）",
        "pointers": ["k3dge milestone audit-submit <id>", "docs/incidents/"],
    },
    "sealed": {
        "priority": 9,
        "fact": "已封板（归档+版本+指针）；收摊在压缩上下文：见 docs/reviews/*-closure.md → 更新设计文档 → 提交里程碑",
        "pointers": ["docs/reviews/*-closure.md", "k3dge ADR-0004 §2.1.4"],
    },
    "seal_declined": {
        "priority": 9,"fact": "已放弃封板（当普通提交结束）", "pointers": ["AGENTS.md §12"]},
    # 兜底态：闸/动作拒绝且其 gate_id 不在 `GATE_NEXT` 路由表内。原文照登，不猜。
    "rejected": {
        "priority": 3,"fact": "操作被拒（原因见上）", "pointers": ["AGENTS.md §12", "k3dge milestone status <id>"]},
    # 路由自身坏了（`lifecycle_next` 取处理点时抛）：不得渲染成"没待办"（ocr2-178）。
    # 机器面（`status --json` `.next` / MCP）靠它与 `None` 区分"坏了"与"没事"。
    "routing_error": {
        "priority": 1,
        "fact": "处理点路由异常（见 reasons），本轮无法判定是否有待办；这不是“没事”",
        "pointers": ["AGENTS.md §12"]},
    # `new_domain` is a cross-cutting trigger the hard gate does not turn red on
    # but has a file-level signal. Architecture/overview updates are intentionally
    # NOT a hook — they are done inside the milestone closure note (ADR-0004).
    "new_domain": {
        "priority": 4,
        "fact": "新建 src/ 域未在 manifest 注册（硬闸不红，但有文件级信号）",
        "options": [
            "补 manifest + spec + tests，再 k3dge sync 回写契约哈希",
            "有意不注册 → 在 manifest `ignore` 里声明",
        ],
        "pointers": ["k3dge ADR-0005 §2.8", "k3dge sync"],
    },
}

#: 拒绝派发闭集（唯一源）：`gate_id` → (state, fact_key)。
#: **不在表里的 id 兜底为 `rejected` + 原文**（不猜）。id 词表：`pipeline.toml`
#: `[checks.*].preconditions/actions` + `gates.INTERNAL_GATE_IDS`。
GATE_NEXT: dict = {
    # 封板前置闸：未审计 ⇒ 回审计入口
    # 注：`audit_closed` 的派发项已随该闸一并退除（ADR-0004 §2.1.3：报告降为可选
    # 产物、审计由 `seal` 自己跑）——留着会是一个永不出现的键。
    "audit_report_missing": ("rejected", "audit_missing"),
    "audit_noop": ("rejected", "audit_noop"),
    "audit_degraded_unsigned": ("rejected", "audit_degraded_unsigned"),
    "audit_open_declined": ("rejected", "audit_open_declined"),
    "tasks_all_done": ("rejected", "tasks_pending"),
}

#: 拒绝事实文案（仅当 state 自带的 fact 不够用时；`<id>` 占位）。
REJECTION_FACTS: dict = {
    "audit_missing": "审计缺失：先落盘报告（k3dge milestone audit-submit <id>）或 k3dge milestone audit <id>",
    "audit_noop": "审计未真跑：这一跳被跳过或失败——空转不得当闭环（k3dge ADR-0004 §2.1.11）；检查传输链/透镜可达后重跑 k3dge milestone audit <id>",
    "audit_degraded_unsigned": "审计降级到 manual 但报告无署名/来源——降级不静默：补署名后可记 degraded-manual（k3dge ADR-0004 §2.1.11）",
    "audit_open_declined": "stop / 转人工干预（待修未修复且 agent 拒绝修复）",
    "tasks_pending": "票据未全 done：先干活或改挂里程碑，再谈 align/seal",
}


@dataclass
class NextStep:
    state: str
    milestone: str
    pending: Optional[int] = None
    priority: int = 5
    fact: Optional[str] = None
    options: Optional[list] = None
    question: Optional[str] = None
    reasons: Optional[list] = None
    pointers: Optional[list] = None
    rules: Optional[str] = None

    @classmethod
    def from_state(cls, state: str, milestone: str, *, pending: Optional[int] = None,
                   reasons: Optional[list] = None, rules: Optional[str] = None) -> "NextStep":
        opt = STATE_OPTIONS.get(state, {})
        if not opt:
            # 未知 state 静默当空声明 ⇒ 投出"没有下一步"的假象，与"确实没有待办"不可分（438）
            print(f"[NEXT] WARN: 未知 state={state!r}（不在 STATE_OPTIONS 闭集里）⇒ 只登事实，不投影处理点",
                  file=sys.stderr)
        return cls(
            state=state,
            milestone=milestone,
            pending=pending,
            priority=int(opt.get("priority", 5)),
            fact=opt.get("fact"),
            options=list(opt["options"]) if opt.get("options") else None,
            question=opt.get("question"),
            # 拷贝：`reasons` 是调用方的列表、`pointers` 是模块级 STATE_OPTIONS 的列表，
            # 按引用交出去，任何消费者原地改动都污染单一源（ocr2-281）。
            reasons=list(reasons) if reasons else None,
            pointers=list(opt.get("pointers") or []) or None,
            rules=rules,
        )

    def _fill(self, text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        out = text.replace("<id>", self.milestone)
        if self.pending is not None:
            out = out.replace("<n>", str(self.pending))
        if self.rules is not None:
            out = out.replace("<rules>", self.rules)
        # 未解析的占位符不得静默进投影（"里程碑 M7 审计发现 <n> 项待修"）：`<n>`/`<rules>`
        # 是可选 kwarg，漏传时旧实现把字面量印给操作者（ocr2-282）。出声。
        import re as _re

        if _re.search(r"<[a-z_]+>", out):
            print(f"[NEXT] WARN: 投影残留未解析占位符：{out!r}", file=sys.stderr)
        return out

    def filled_options(self) -> list:
        return [self._fill(o) or o for o in (self.options or [])]

    def render_cli(self) -> str:
        """纯打印面：**只出 fact + options**（陈述句，无应答通道故不用疑问句）。"""
        head = f"[NEXT] state={self.state} milestone={self.milestone}"
        if self.pending is not None:
            head += f" pending={self.pending}"
        lines = [head]
        if self.reasons:
            for r in self.reasons:
                lines.append(f"  reason: {r}")
        fact = self._fill(self.fact)
        if fact:
            lines.append(f"  fact: {fact}")
        for o in self.filled_options():
            lines.append(f"  option: {o}")
        if self.pointers:
            lines.append("  pointers: " + " | ".join(self._fill(p) or p for p in self.pointers))
        return "\n".join(lines)

    def render_mcp(self) -> dict:
        # `priority` 进投影：读侧（外来 harness / MCP）需要它才能自己排序；
        # 也是 `_upsert` 排序的依据（卡片里没有它 ⇒ 排序全落默认值）。
        d: dict = {"state": self.state, "milestone": self.milestone, "priority": self.priority}
        if self.pending is not None:
            d["pending"] = self.pending
        if self.reasons:
            d["reasons"] = list(self.reasons)
        fact = self._fill(self.fact)
        if fact:
            d["fact"] = fact
        opts = self.filled_options()
        if opts:
            d["options"] = opts
        question = self._fill(self.question)
        if question:
            d["question"] = question   # 只给有应答通道的消费者（prompt.ask）
        if self.pointers:
            d["pointers"] = [self._fill(p) or p for p in self.pointers]
        return d


_SIDECAR_REL = ".k3dge/next.json"


def _card(ns: "NextStep") -> dict:
    return ns.render_mcp()


def _write_cards(workspace: Path, cards: list, primary: Optional[str]) -> None:
    """侧车＝**当前轮的处理点集合**：`{"next": [card...], "primary": <state>}`。

    单条时仍写这个形状（读侧兼容旧单条形状，见 `load_persisted`）。
    """
    try:
        path = workspace / _SIDECAR_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"next": list(cards), "primary": primary}
        # 侧车被 CLI（含 git hook 进程）与 MCP server 共享：`write_text` 先截断 ⇒ 并发读者
        # 可能读到空/半个 JSON，`load_all` 又把解析失败当"本轮无处理点"（ocr-272）。原子替换。
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        # 静默吞 ⇒ 操作者与 harness 读到的是上一轮遗留的提示，且没有任何信号（ocr-273）
        print(f"[nextstep] WARN: 侧车写入失败（{exc}）⇒ 本轮提示未持久化", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - ocr2-755：json.dumps 的 TypeError（如 reasons 里混进
        # Path/set/datetime）同样不得把 persist/emit 掀翻——侧车是 best-effort，出声不断行。
        print(f"[nextstep] WARN: 侧车序列化失败（{type(exc).__name__}: {exc}）⇒ 本轮提示未持久化",
              file=sys.stderr)


def begin_run(workspace: Path) -> None:
    """一轮的开始：清空侧车（处理点集合按轮重置；否则上一条命令的提示会留到这一轮）。

    **只在文件已存在时删除**（不写空壳）：这样"没有提示的一轮"不留任何文件，
    只读命令（如 `milestone seal-check`）也就真的不产状态。
    """
    try:
        (Path(workspace) / _SIDECAR_REL).unlink(missing_ok=True)
    except OSError as exc:      # 清不掉 ⇒ 本轮会接着上一轮的提示，必须出声（ocr-273）
        print(f"[nextstep] WARN: 侧车清理失败（{exc}）⇒ 可能残留上一轮提示", file=sys.stderr)


def persist(workspace: Path, ns: NextStep) -> None:
    """**替换**写入（单判定流程用：seal_flow / milestone_audit 各自只判一个下一步）。"""
    _write_cards(workspace, [_card(ns)], ns.state)
    from k3dge.engine import events
    events.emit(workspace, "next", state=ns.state, milestone=ns.milestone)


def _upsert(workspace: Path, ns: NextStep) -> list:
    """本轮内 upsert：同 state 去重（后到的合并 reasons），返回本轮全部 card（按 priority 稳定排序）。"""
    existing = load_all(workspace) or []
    by_state = {c.get("state"): c for c in existing if isinstance(c, dict)}
    prev = by_state.get(ns.state) or {}
    card = _card(ns)
    if isinstance(prev.get("reasons"), list) and prev["reasons"]:
        # docstring 承诺"同 state 去重（后到的合并 reasons）"，旧实现是整条替换 ⇒
        # 前一条同 state 的 reasons/pending 被静默丢（ocr-274）。
        merged = list(prev["reasons"])
        for r_ in (card.get("reasons") or []):
            if r_ not in merged:
                merged.append(r_)
        card["reasons"] = merged
    for _k in ("pending", "pointers", "question"):
        # 新卡没设的字段（`render_mcp` 在 None/空时直接省键，ocr2-283）从旧卡继承，
        # 否则第二块同态卡会把上一块的 pending/pointers/question 静默清掉。
        if _k not in card and _k in prev:
            card[_k] = prev[_k]
    by_state[ns.state] = card
    cards = sorted(by_state.values(), key=_prio)     # 同 439：外来 card 的 priority 未必可比
    return cards


def emit(workspace: Path, ns: NextStep, *, stream: Optional[TextIO] = None) -> str:
    """追加/更新本轮的处理点并打印这一块（单点调用用；多源汇总用 `emit_all`）。"""
    cards = _upsert(workspace, ns)
    primary = next((c.get("state") for c in cards if isinstance(c, dict) and c.get("state")), None)
    _write_cards(workspace, cards, primary)
    from k3dge.engine import events
    events.emit(workspace, "next", state=ns.state, milestone=ns.milestone)
    text = ns.render_cli()
    if stream is not None:
        print(text, file=stream)
    return text


def _prio(card: dict) -> int:
    """`priority` 未必可比：旧形状/手工编辑/外来 harness 写的 null 或字符串会让 `sorted` 抛（439）。"""
    try:
        return int(card.get("priority", 5))
    except (TypeError, ValueError):
        return 5


def _merge_reasons(old: Optional[list], new: Optional[list]) -> Optional[list]:
    """同 state 两卡的 reasons 并集合并（保序、去重；任一为空即取另一方）。"""
    if not old:
        return list(new) if new else old
    if not new:
        return list(old)
    merged = list(old)
    for _r in new:
        if _r not in merged:
            merged.append(_r)
    return merged


def emit_all(workspace: Path, steps: list, *, stream: Optional[TextIO] = None) -> list:
    """一轮的**多处理点**：按 priority 稳定排序后打印，侧车写全量 + `primary`。

    为何排序：同一轮可能命中多个处理点（实测 `k3dge check` 同轮命中 `seal_ready` 与
    `doc_fix`），stdout 顺序应表达"先看哪个"；侧车是给读侧（外来 harness / MCP）的，
    单槽会丢信息。
    """
    seen = {}
    for ns in steps:
        if ns is not None:
            prev_ns = seen.get(ns.state)
            if prev_ns is not None and getattr(prev_ns, "reasons", None):
                # 同轮同 state 去重不能整条替换（ocr2-285）：先并 reasons，
                # 否则先落地的 seal_ready blocker reasons 会被后到的裸卡抹掉。
                ns.reasons = _merge_reasons(prev_ns.reasons, ns.reasons)
            seen[ns.state] = ns          # 同 state 去重（后到者胜，reasons 已合并）
    order = list(STATE_OPTIONS)
    ordered = sorted(seen.values(),
                     key=lambda n: (n.priority, order.index(n.state) if n.state in order else len(order)))
    cards = [_card(n) for n in ordered]
    # `emit` 走 `_upsert`（先读再合并），`emit_all` 以前**全量覆盖** ⇒ 同轮里 persist/emit
    # 先落地的处理点（审计/封板判定、前一个 hook 的拒绝）被整片抹掉（ocr-275）。
    by_state = {c.get("state"): c for c in (load_all(workspace) or []) if isinstance(c, dict)}
    for c in cards:
        prev_c = by_state.get(c.get("state")) or {}
        if isinstance(prev_c.get("reasons"), list) and prev_c["reasons"]:
            # 与 `_upsert` 同口径：已 persist 的同态卡 reasons 要合并而非覆盖（ocr2-285）。
            c["reasons"] = _merge_reasons(prev_c["reasons"], c.get("reasons"))
        for _k in ("pending", "pointers", "question"):
            # 同 `_upsert`：新卡未设的字段从旧卡继承，否则第二块同态卡会把上一块的
            # pending/pointers/question 静默清掉（`render_mcp` 在 None/空时省键）。
            if _k not in c and _k in prev_c:
                c[_k] = prev_c[_k]
        by_state[c.get("state")] = c
    merged = sorted(by_state.values(),
                    key=lambda c: (_prio(c),
                                   order.index(c.get("state")) if c.get("state") in order else len(order)))
    _write_cards(workspace, merged, merged[0].get("state") if merged else None)
    from k3dge.engine import events
    for n in ordered:
        events.emit(workspace, "next", state=n.state, milestone=n.milestone)
        if stream is not None:
            print(n.render_cli(), file=stream)
    return [n.render_cli() for n in ordered]


def load_all(workspace: Path) -> list:
    """读回本轮全部处理点（新形状 `{"next": [...]}`）；旧单条形状 ⇒ 单元素列表。"""
    try:
        raw = (Path(workspace) / _SIDECAR_REL).read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        data = json.loads(raw)
    except ValueError as exc:
        # 损坏的侧车不能报成"本轮无处理点"（ocr2-286）：缺文件才静默，坏内容必须出声。
        print(f"[nextstep] WARN: 侧车解析失败（{type(exc).__name__}: {exc}）⇒ 本轮提示不可信",
              file=sys.stderr)
        return []
    if not isinstance(data, dict):
        print("[nextstep] WARN: 侧车顶层不是对象 ⇒ 本轮提示不可信", file=sys.stderr)
        return []
    if isinstance(data.get("next"), list):
        return [c for c in data["next"] if isinstance(c, dict)]
    return [data] if data.get("state") else []          # 旧形状（单条）兼容


def load_persisted(workspace: Path) -> Optional[dict]:
    """读回**主处理点**（`primary`）——MCP/外来 harness 的单值读法。

    流程（`run_seal_flow` / `run_audit_flow`）已自己判定并 persist 过下一步；MCP 层直接
    投影**同一个判定**，而不是拿返回的散文消息重新猜一遍。
    """
    cards = load_all(workspace)
    if not cards:
        return None
    try:
        raw = json.loads((Path(workspace) / _SIDECAR_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cards[0]
    primary = raw.get("primary") if isinstance(raw, dict) else None
    for c in cards:
        if c.get("state") == primary:
            return c
    return cards[0]


def seal_ready_for(workspace: Path, milestone_id: str, *, unmet=None, tasks=None) -> "NextStep":
    """`seal_ready` 的**唯一生产构造入口**：把"剩余封板前置闸"填进事实。

    为何：`[NEXT]` 此前只说"审计已闭环"就让人去封板，而 `seal` 还要过预审的
    形式闸（tasks_all_done / align_pass marker / adrs_all_accepted / docs_normalized …）
    ⇒ 投影与判据不同源，操作者跑到 seal 才发现。本函数让两者同源（都问
    `seal.unmet_seal_preconditions`）。告警面＝**需人先办**的项（`satisfies` 的 ⚙️ 项不列）。
    零 task ⇒ 不是 seal_ready（ADR-0004 空窗不建议封）。
    """
    if tasks is None or unmet is None:
        from k3dge.engine.seal import unmet_seal_preconditions
        from k3dge.engine.task_index import scan_milestone_tasks

        if tasks is None:
            tasks = scan_milestone_tasks(workspace, milestone_id)
        if unmet is None:
            unmet = unmet_seal_preconditions(workspace, milestone_id)
    if not tasks:
        return NextStep.from_state("normal", milestone_id)
    ns = NextStep.from_state("seal_ready", milestone_id)
    suffix = str(STATE_OPTIONS["seal_ready"].get("fact_with_blockers") or "")
    blockers = "、".join(gid for gid, _ in unmet) or "全绿"
    ns.fact = (ns.fact or "") + suffix.replace("<blockers>", blockers)
    if unmet:
        ns.reasons = [f"{gid}：{msg[:110]}" for gid, msg in unmet[:4]]
        blocked = str(STATE_OPTIONS["seal_ready"].get("fact_blocked") or "")
        if blocked:
            ns.fact = blocked.replace("<id>", milestone_id) + suffix.replace("<blockers>", blockers)
    return ns


def next_for_rejection(milestone: str, message, gate_id: Optional[str] = None) -> NextStep:
    """Failure -> action. **闭集派发**：`gate_id` → `GATE_NEXT` → state/fact。

    `message` 可为 `gates.Rejection`（自带 gate_id）或裸 str。裸 str（无 id）一律
    兜底为 `rejected` + 原文——**不从文案里猜**（猜错＝静默给错下一步）。
    """
    gid = gate_id or getattr(message, "gate_id", None)
    text = "" if message is None else str(message)
    route = GATE_NEXT.get(gid) if gid else None
    if route is None:
        opt = STATE_OPTIONS.get("rejected", {})
        return NextStep(
            state="rejected", milestone=milestone,
            fact=f"操作被拒：{text}" if text else str(opt.get("fact", "")).replace("<id>", milestone),
            priority=int(opt.get("priority", 3)),
            pointers=list(opt.get("pointers") or []) or None,
        )
    state, fact_key = route
    fact = REJECTION_FACTS.get(fact_key or "", "").replace("<id>", milestone)
    if not fact:
        fact = STATE_OPTIONS.get(state, {}).get("fact", "").replace("<id>", milestone)
    if text and text not in fact:
        fact = f"{text}\n  {fact}" if fact else text
    opt = STATE_OPTIONS.get(state, {})
    return NextStep(
        state=state,
        milestone=milestone,
        fact=fact,
        options=list(opt.get("options") or []) or None,
        # 路由分支以前只带 options：`priority`/`pointers` 留在声明表里没读 ⇒ 一张被拒的卡
        # 掉回默认 priority 5（决策点之后），排序就骗人（t-206；与 ocr-277 同一族的另一半）
        priority=int(opt.get("priority", 3)),
        pointers=list(opt.get("pointers") or []) or None,
    )


def question_text(state: str, milestone: str, *, n: Optional[int] = None) -> str:
    """交互式 `prompt.ask` 的文案单源投影：取 `STATE_OPTIONS[state]["question"]`。

    与 `[NEXT]` 的 `fact` 是**同一判定的两个投影**（ADR-0026 §2.2 语法维）：
    有应答通道（prompt 读 stdin）→ 疑问句；纯打印（`[NEXT]`）→ 陈述句。
    两者都不是第二源：同一声明里的两个字段，各投影一次。
    通道行为（`default_yes` / `countdown`）留在调用点——那是**怎么问**，不是**问什么**。
    占位符：`<id>` = 里程碑，`<n>` = 待修计数。无 `question` 的态回落 `fact`。
    """
    opt = STATE_OPTIONS.get(state, {})
    text = opt.get("question") or opt.get("fact") or ""
    out = text.replace("<id>", milestone)
    if n is not None:
        out = out.replace("<n>", str(n))
    return out
