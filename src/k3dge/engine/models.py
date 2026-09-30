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
            tag = {"block": "GATE ERROR", "warn": "GATE WARN", "observe": "GATE NOTE"}[
                gate_facts.severity(self.rule_id)
            ]
            return f"[{tag}] {body}"
        return f"[GATE ERROR] {self.rule_id}{dom}: {self.message}{loc}"


@dataclass(frozen=True)
class GateReport:
    passed: bool
    changed_files: Tuple[str, ...] = ()
    modified_domains: Tuple[str, ...] = ()
    violations: Tuple[Violation, ...] = ()

    def render(self) -> str:
        if self.violations:
            lines = []
            lines.append("=" * 60)
            lines.append(" AGENT GATE VIOLATION: Commit Blocked by Policy")
            lines.append("=" * 60)
            for violation in self.violations:
                lines.append(violation.format())
            lines.append("")
            lines.append("Fix violations or run 'k3dge sync' to regenerate specs.")
            return "\n".join(lines)
        if not self.changed_files:
            return "[GATE] Workspace is clean. No validation needed."
        lines = []
        lines.append("[GATE SUCCESS] All domain-spec invariants satisfied.")
        if self.modified_domains:
            lines.append(f"  Validated domains: {', '.join(self.modified_domains)}")
        return "\n".join(lines)
