"""Core data models for k3dge gate reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Violation:
    rule_id: str
    message: str
    domain: Optional[str] = None
    file_path: Optional[str] = None
    detail: Optional[dict] = None

    def format(self) -> str:
        """渲染闸红。

        已进 `gate_facts.GATE_FACTS` 声明面的 code 走**单一渲染器**（陈述式 fact +
        成对 options + pointers，档位前缀由声明定）；未声明的 code 保持旧形状
        （`message` 由构造点自带）——迁移是增量的，搬一个就少一处手拼串。
        """
        from k3dge.engine import gate_facts

        loc = f" [{self.file_path}]" if self.file_path else ""
        dom = f" <{self.domain}>" if self.domain else ""
        if gate_facts.is_declared(self.rule_id):
            facts = dict(self.detail or {})
            # 声明面模板常用 `{path}`/`{domain}`，而构造点常只给 file_path/domain ⇒ 一并注入，
            # 否则 fact 里会漏出字面 `{path}`/`{domain}` 占位符（ocr-088）。
            if self.file_path:
                facts.setdefault("path", self.file_path)
            if self.domain:
                facts.setdefault("domain", self.domain)
            body = gate_facts.render(self.rule_id, facts, where=f"{dom}{loc}".strip())
            tag = gate_facts.severity_tag(gate_facts.severity(self.rule_id))   # 标签单源在声明面（435）
            return f"[{tag}] {body}"
        return f"[{gate_facts.severity_tag(gate_facts.severity(self.rule_id))}] {self.rule_id}{dom}: {self.message}{loc}"


@dataclass(frozen=True)
class GateReport:
    passed: bool
    changed_files: Tuple[str, ...] = ()
    modified_domains: Tuple[str, ...] = ()
    violations: Tuple[Violation, ...] = ()

    def render(self) -> str:
        # `passed` 是 CLI 退出码的判据（`cli/main.py`），以前 render 只看 violations/changed_files
        # 是否为空 ⇒ `passed=False` 而 violations 为空的一轮会被渲染成"干净"（436）
        if self.violations or not self.passed:
            from k3dge.engine import gate_facts

            # `warn`/`observe` 不拦提交（gate_facts 的语义），横幅却写死 "Commit Blocked"、
            # 页脚写死 "Fix violations" ⇒ 全 warn 的一轮也长得像被拦（消费方按文案决定动作，ocr-271）。
            blocking = [x for x in self.violations if gate_facts.severity(x.rule_id) == "block"]
            lines = []
            lines.append("=" * 60)
            lines.append(" AGENT GATE VIOLATION: Commit Blocked by Policy" if blocking
                         else " AGENT GATE NOTICE: 非阻断提示（warn/observe），本次不拦提交")
            lines.append("=" * 60)
            for violation in self.violations:
                lines.append(violation.format())
            lines.append("")
            lines.append("Fix violations or run 'k3dge sync' to regenerate specs." if blocking
                         else "以上为提示项（warn/observe）；不阻断提交。")
            return "\n".join(lines)
        if not self.changed_files:
            return "[GATE] Workspace is clean. No validation needed."
        lines = []
        lines.append("[GATE SUCCESS] All domain-spec invariants satisfied.")
        if self.modified_domains:
            lines.append(f"  Validated domains: {', '.join(self.modified_domains)}")
        return "\n".join(lines)
