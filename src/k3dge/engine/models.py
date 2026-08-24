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

    def format(self) -> str:
        loc = f" [{self.file_path}]" if self.file_path else ""
        dom = f" <{self.domain}>" if self.domain else ""
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
