"""Single-source `next-step` hints appended to k3dge command outputs.

Why: an agent reads a tool's *return value* in the same turn, not AGENTS.md.
Commands therefore end with a fixed-shape `[NEXT]` line (CLI) / `next` field
(MCP) so the operator knows the legal next action without re-deriving SOP.

Single source: every option string lives ONLY in `STATE_OPTIONS` (and the
rejection routing table `GATE_NEXT`). Commands never hand-write their own
playbook — they call `NextStep.from_state(...)` / `ask_text(...)` /
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

MCP isomorphic JSON: {"next": {"state", "milestone", "pending"?, "ask"?, "if_y"?, "if_n"?, "note"?}}

Constraints (design review):
  - success -> state; failure -> action. Never decide for the human.
  - only legal options, no "now execute seal".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TextIO

# Success / neutral states: the option text is the single source of truth.
# `pointers` = 纵深指针（doc id / ADR 节 / 命令），推"去哪取细节"而非灌正文（ADR-0008 §2 渐进披露）。
STATE_OPTIONS: dict = {
    "normal": {"note": "常规提交门禁通过", "pointers": ["AGENTS.md §12"]},
    "pending_findings": {
        "ask": "有 findings 钉在代码/文档里；继续处理这些 pending？",
        "if_y": "修完删 `k3dit:pending <ID>` 标记；有意留改成 `k3dit:leftover <ID>` 指针（处置仍以 12 列报告 + tasks 为准，标记只是指针）",
        "if_n": "stop",
        "pointers": ["peer_contract §8", "k3dge ADR-0025"],
    },
    "ratchet_open": {
        "note": "有在办棘轮工单（k3dge ADR-0025）：进程不等人，但账必须可见",
        "if_y": "k3dge audit status <job> 查对端；席位侧一圈见契约 §1.4（Hall pin-only：判读落钉→修翻 fixnote→复核翻 fixed→Hall 拔→sign-report）",
        "pointers": ["k3dge audit status <id>", "peer_contract §1.4", "k3dge ADR-0025 §2.7"],
    },
    "doc_audit": {
        "note": "docs/ 有改动：check 是静态硬闸（T-01），doc-audit 在其**之后**跑、不阻断——`k3dge doc-audit` 出报告(k3dit)+建里程碑 task（本轮不改，封板轮也得闭环）",
        "pointers": ["k3dge ADR-0022 §2.2", "k3dge doc-audit"],
    },
    "audit_suggested": {
        "ask": "要审吗？",
        "if_y": "k3dge milestone audit <id>（必审，待修=0 才谈封板）",
        "if_n": "stop（继续干活）",
        "pointers": ["k3dge ADR-0004 §2.1.5", "k3dge milestone audit <id>"],
    },
    "seal_ready": {
        "ask": "里程碑 <id>：审计已闭环（待修=0），封板？",
        "if_y": "k3dge milestone seal <id>（align→归档+版本+指针）",
        "if_n": "stop（里程碑继续挂着，不封）",
        "pointers": ["k3dge ADR-0004 §2.1.4", "docs/reviews/"],
    },
    "audit_needed": {
        "note": "未审计不可封板（封=归档+版本+指针，非界限）：先 k3dge milestone audit <id>",
        "pointers": ["k3dge ADR-0004 §2.1.6", "k3dge milestone audit <id>"],
    },
    "audit_open": {
        "ask": "里程碑 <id>：发现 <n> 项待修，agent 修？",
        "if_y": "修完重跑 k3dge milestone audit <id>（重审）",
        "if_n": "stop / 转人工干预",
        "pointers": ["k3dge ADR-0022", "k3dge milestone audit <id>"],
    },
    "escalated": {
        "note": "verify 连续 >3 次未闭环，转人工干预：k3dge milestone audit-submit <id> 或人工复核",
        "pointers": ["k3dge milestone audit-submit <id>", "docs/incidents/"],
    },
    "sealed": {"note": "已封板（归档+版本+指针）；收摊在压缩上下文：见 docs/reviews/*-closure.md → 更新设计文档 → 提交里程碑", "pointers": ["docs/reviews/*-closure.md", "k3dge ADR-0004 §2.1.4"]},
    "seal_declined": {"note": "已放弃封板（当普通提交结束）", "pointers": ["AGENTS.md §12"]},
    # 兑底态：闸/动作拒绝且其 gate_id 不在 `GATE_NEXT` 路由表内。原文照登，不猜。
    "rejected": {"note": "操作被拒（原因见上）", "pointers": ["AGENTS.md §12", "k3dge milestone status <id>"]},
    # `new_domain` is a cross-cutting trigger the hard gate does not turn red on
    # but has a file-level signal. Architecture/overview updates are intentionally
    # NOT a hook — they are done inside the milestone closure note (ADR-0004).
    "new_domain": {
        "ask": "新建 src/ 域未在 manifest 注册？",
        "if_y": "补 manifest + spec + tests，再 k3dge sync 回写契约",
        "if_n": "stop",
        "pointers": ["k3dge ADR-0005 §2.8", "k3dge sync"],
    },
}

#: 拒绝派发闭集（唯一源）：`gate_id` → (state, note_key)。
#: **不在表里的 id 兜底为 `rejected` + 原文**（不猜）。id 词表：`pipeline.toml`
#: `[checks.*].preconditions/actions` + `gates.INTERNAL_GATE_IDS`。
GATE_NEXT: dict = {
    # 封板前置闸：未审计 ⇒ 回审计入口
    "audit_closed": ("audit_needed", ""),
    "audit_report_missing": ("rejected", "audit_missing"),
    "audit_open_declined": ("rejected", "audit_open_declined"),
    "tasks_all_done": ("rejected", "tasks_pending"),
}

#: 拒绝备注文案（仅当 state 自带的 note 不够用时；`<id>` 占位）。
REJECTION_NOTES: dict = {
    "audit_missing": "审计缺失：先落盘报告（k3dge milestone audit-submit <id>）或 k3dge milestone audit <id>",
    "audit_open_declined": "stop / 转人工干预（待修未修复且 agent 拒绝修复）",
    "tasks_pending": "票据未全 done：先干活或改挂里程碑，再谈 align/seal",
}


@dataclass
class NextStep:
    state: str
    milestone: str
    pending: Optional[int] = None
    note: Optional[str] = None
    ask: Optional[str] = None
    if_y: Optional[str] = None
    if_n: Optional[str] = None
    reasons: Optional[list] = None
    pointers: Optional[list] = None

    @classmethod
    def from_state(cls, state: str, milestone: str, *, pending: Optional[int] = None, reasons: Optional[list] = None) -> "NextStep":
        opt = STATE_OPTIONS.get(state, {})
        return cls(
            state=state,
            milestone=milestone,
            pending=pending,
            ask=opt.get("ask"),
            if_y=opt.get("if_y"),
            if_n=opt.get("if_n"),
            note=opt.get("note"),
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

    def render_cli(self) -> str:
        head = f"[NEXT] state={self.state} milestone={self.milestone}"
        if self.pending is not None:
            head += f" pending={self.pending}"
        lines = [head]
        if self.reasons:
            for r in self.reasons:
                lines.append(f"  reason: {r}")
        ask = self._fill(self.ask)
        if_y = self._fill(self.if_y)
        if_n = self._fill(self.if_n)
        if ask:
            lines.append(f"  ask: {ask}")
        if if_y:
            lines.append(f"  if y: {if_y}")
        if if_n:
            lines.append(f"  if n: {if_n}")
        if self.note:
            lines.append(f"  note: {self.note}")
        if self.pointers:
            lines.append("  pointers: " + " | ".join(self._fill(p) or p for p in self.pointers))
        return "\n".join(lines)

    def render_mcp(self) -> dict:
        d: dict = {"state": self.state, "milestone": self.milestone}
        if self.pending is not None:
            d["pending"] = self.pending
        if self.reasons:
            d["reasons"] = list(self.reasons)
        ask = self._fill(self.ask)
        if_y = self._fill(self.if_y)
        if_n = self._fill(self.if_n)
        if ask:
            d["ask"] = ask
        if if_y:
            d["if_y"] = if_y
        if if_n:
            d["if_n"] = if_n
        if self.note:
            d["note"] = self.note
        if self.pointers:
            d["pointers"] = [self._fill(p) or p for p in self.pointers]
        return d


_SIDECAR_REL = ".k3dge/next.json"


def persist(workspace: Path, ns: NextStep) -> None:
    """Write next-step sidecar to `.k3dge/next.json`. Fire-and-forget; never raises."""
    try:
        path = workspace / _SIDECAR_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(ns.render_mcp(), ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError:
        pass
    from k3dge.engine import events
    events.emit(workspace, "next", state=ns.state, milestone=ns.milestone)


def emit(workspace: Path, ns: NextStep, *, stream: Optional[TextIO] = None) -> str:
    """Persist sidecar + render CLI text + optionally print. Returns the CLI text."""
    persist(workspace, ns)
    text = ns.render_cli()
    if stream is not None:
        print(text, file=stream)
    return text


def load_persisted(workspace: Path) -> Optional[dict]:
    """读回 `.k3dge/next.json`（MCP 投影形状）。不存在/坏 JSON ⇒ None，永不抛。

    用途：流程（`run_seal_flow` / `run_audit_flow`）已自己判定并 `persist` 过下一步；
    MCP 层直接投影**同一个判定**，而不是拿返回的散文消息重新猜一遍。
    """
    try:
        raw = (Path(workspace) / _SIDECAR_REL).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) and data.get("state") else None


def next_for_rejection(milestone: str, message, gate_id: Optional[str] = None) -> NextStep:
    """Failure -> action. **闭集派发**：`gate_id` → `GATE_NEXT` → state/note。

    `message` 可为 `gates.Rejection`（自带 gate_id）或裸 str。裸 str（无 id）一律
    兜底为 `rejected` + 原文——**不从文案里猜**（猜错＝静默给错下一步）。
    """
    gid = gate_id or getattr(message, "gate_id", None)
    text = "" if message is None else str(message)
    route = GATE_NEXT.get(gid) if gid else None
    if route is None:
        return NextStep(state="rejected", milestone=milestone, note=f"操作被拒：{text}")
    state, note_key = route
    note = REJECTION_NOTES.get(note_key or "", "").replace("<id>", milestone)
    if not note:
        note = STATE_OPTIONS.get(state, {}).get("note", "").replace("<id>", milestone)
    if text and text not in note:
        note = f"{text}\n  {note}" if note else text
    return NextStep(state=state, milestone=milestone, note=note)


def ask_text(state: str, milestone: str, *, n: Optional[int] = None) -> str:
    """判定文案单源投影：交互式 `prompt.ask` 与 `[NEXT]` 共用 `STATE_OPTIONS[state]`。

    通道行为（`default_yes` / `countdown`）留在调用点——那是**怎么问**，不是**问什么**。
    占位符：`<id>` = 里程碑，`<n>` = 待修计数。
    """
    opt = STATE_OPTIONS.get(state, {})
    text = opt.get("ask") or opt.get("note") or ""
    out = text.replace("<id>", milestone)
    if n is not None:
        out = out.replace("<n>", str(n))
    return out
