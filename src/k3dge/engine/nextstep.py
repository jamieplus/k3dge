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

Shape (CLI):
    [NEXT] state=<state> milestone=<id>[ pending=<n>]
      ask: <question>          (only when a decision is required)
      if y: <action>
      if n: <action>

MCP isomorphic JSON: {"next": {"state", "milestone", "pending"?, "reasons"?, "fact"?, "options"?, "question"?, "pointers"?}}

Constraints (design review):
  - success -> state; failure -> action. Never decide for the human.
  - only legal options, no "now execute seal".
"""

from __future__ import annotations

import json
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
#:   5 在办进程 / 后续步（ratchet_open / doc_audit）
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
    "ratchet_open": {
        "priority": 5,
        "fact": "有在办棘轮工单（k3dge ADR-0025）：进程不等人，但账必须可见",
        "pointers": [
            "k3dge audit status <id>",
            "peer_contract §1.4（Hall pin-only：判读落钉→修翻 fixnote→复核翻 fixed→Hall 拔→sign-report）",
            "k3dge ADR-0025 §2.7",
        ],
    },
    "doc_audit": {
        "priority": 5,
        "fact": "docs/ 有改动：check 是静态硬闸（T-01），doc-audit 在其**之后**跑、不阻断（本轮不改，封板轮也得闭环）",
        "pointers": ["k3dge ADR-0022 §2.2", "k3dge doc-audit"],
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
        "fact": "里程碑 <id> 审计已闭环（待修=0）；封板与否由你决定（封＝归档+版本+指针）",
        "question": "里程碑 <id>：封板？",
        "options": [
            "k3dge milestone seal <id>（align→归档+版本+指针）",
            "不封（里程碑继续挂着，当普通提交结束）",
        ],
        "pointers": ["k3dge ADR-0004 §2.1.4", "docs/reviews/"],
    },
    "audit_needed": {
        "priority": 2,
        "fact": "里程碑 <id> 未审计，不可封板（封＝归档+版本+指针，非界限）",
        "options": [
            "k3dge milestone audit <id>（先闭环审计）",
            "不封板，当普通提交结束",
        ],
        "pointers": ["k3dge ADR-0004 §2.1.6", "k3dge milestone audit <id>"],
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
    "audit_closed": ("audit_needed", ""),
    "audit_report_missing": ("rejected", "audit_missing"),
    "audit_open_declined": ("rejected", "audit_open_declined"),
    "tasks_all_done": ("rejected", "tasks_pending"),
}

#: 拒绝事实文案（仅当 state 自带的 fact 不够用时；`<id>` 占位）。
REJECTION_FACTS: dict = {
    "audit_missing": "审计缺失：先落盘报告（k3dge milestone audit-submit <id>）或 k3dge milestone audit <id>",
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

    @classmethod
    def from_state(cls, state: str, milestone: str, *, pending: Optional[int] = None, reasons: Optional[list] = None) -> "NextStep":
        opt = STATE_OPTIONS.get(state, {})
        return cls(
            state=state,
            milestone=milestone,
            pending=pending,
            priority=int(opt.get("priority", 5)),
            fact=opt.get("fact"),
            options=list(opt["options"]) if opt.get("options") else None,
            question=opt.get("question"),
            reasons=reasons,
            pointers=opt.get("pointers"),
        )

    def _fill(self, text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        out = text.replace("<id>", self.milestone)
        if self.pending is not None:
            out = out.replace("<n>", str(self.pending))
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
        path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError:
        pass


def begin_run(workspace: Path) -> None:
    """一轮的开始：清空侧车（处理点集合按轮重置；否则上一条命令的提示会留到这一轮）。"""
    _write_cards(workspace, [], None)


def persist(workspace: Path, ns: NextStep) -> None:
    """**替换**写入（单判定流程用：seal_flow / milestone_audit 各自只判一个下一步）。"""
    _write_cards(workspace, [_card(ns)], ns.state)
    from k3dge.engine import events
    events.emit(workspace, "next", state=ns.state, milestone=ns.milestone)


def _upsert(workspace: Path, ns: NextStep) -> list:
    """本轮内 upsert：同 state 去重（后到的合并 reasons），返回本轮全部 card（按 priority 稳定排序）。"""
    existing = load_all(workspace) or []
    by_state = {c.get("state"): c for c in existing if isinstance(c, dict)}
    by_state[ns.state] = _card(ns)
    cards = sorted(by_state.values(), key=lambda c: c.get("priority", 5))
    return cards


def emit(workspace: Path, ns: NextStep, *, stream: Optional[TextIO] = None) -> str:
    """追加/更新本轮的处理点并打印这一块（单点调用用；多源汇总用 `emit_all`）。"""
    cards = _upsert(workspace, ns)
    _write_cards(workspace, cards, cards[0]["state"] if cards else None)
    from k3dge.engine import events
    events.emit(workspace, "next", state=ns.state, milestone=ns.milestone)
    text = ns.render_cli()
    if stream is not None:
        print(text, file=stream)
    return text


def emit_all(workspace: Path, steps: list, *, stream: Optional[TextIO] = None) -> list:
    """一轮的**多处理点**：按 priority 稳定排序后打印，侧车写全量 + `primary`。

    为何排序：同一轮可能命中多个处理点（实测 `k3dge check` 同轮命中 `seal_ready` 与
    `doc_audit`），stdout 顺序应表达"先看哪个"；侧车是给读侧（外来 harness / MCP）的，
    单槽会丢信息。
    """
    seen = {}
    for ns in steps:
        if ns is not None:
            seen[ns.state] = ns          # 同 state 去重（后到者胜）
    ordered = sorted(seen.values(), key=lambda n: (n.priority, list(STATE_OPTIONS).index(n.state)))
    cards = [_card(n) for n in ordered]
    _write_cards(workspace, cards, ordered[0].state if ordered else None)
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
    except ValueError:
        return []
    if not isinstance(data, dict):
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


def next_for_rejection(milestone: str, message, gate_id: Optional[str] = None) -> NextStep:
    """Failure -> action. **闭集派发**：`gate_id` → `GATE_NEXT` → state/fact。

    `message` 可为 `gates.Rejection`（自带 gate_id）或裸 str。裸 str（无 id）一律
    兜底为 `rejected` + 原文——**不从文案里猜**（猜错＝静默给错下一步）。
    """
    gid = gate_id or getattr(message, "gate_id", None)
    text = "" if message is None else str(message)
    route = GATE_NEXT.get(gid) if gid else None
    if route is None:
        return NextStep(state="rejected", milestone=milestone, fact=f"操作被拒：{text}")
    state, fact_key = route
    fact = REJECTION_FACTS.get(fact_key or "", "").replace("<id>", milestone)
    if not fact:
        fact = STATE_OPTIONS.get(state, {}).get("fact", "").replace("<id>", milestone)
    if text and text not in fact:
        fact = f"{text}\n  {fact}" if fact else text
    return NextStep(
        state=state,
        milestone=milestone,
        fact=fact,
        options=list(STATE_OPTIONS.get(state, {}).get("options") or []) or None,
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
