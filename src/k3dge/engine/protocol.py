"""Persistent protocol deviation escalation.

`write_incident` is the only protocol-related primitive k3dge keeps: it writes a
human-visible incident note when an agent ignores the soft gate. The audit
protocol's two fallback layers (审计 `audit_default.md` / 复审 `verify_default.md`)
are configured in `.agent/pipeline.toml` via manual-step `protocol` references and
validated by `k3dge check` (PIPELINE_PROTOCOL_NOT_FOUND) — there is no longer a
central `.agent/protocols.toml` registry. See ADR-0019.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path


def write_incident(
    workspace: Path,
    target: str | None,
    task_type: str | None,
    task_id: str,
    detail: str,
) -> Path:
    """Escalate a persistent protocol deviation to a human-visible incident note.

    Writes `docs/incidents/INC-YYYYMMDD-protocol-<slug>.md`. This is the "report it to
    a human" backstop when an agent ignores the soft gate and proceeds regardless.
    """
    inc_dir = workspace / "docs" / "incidents"
    inc_dir.mkdir(parents=True, exist_ok=True)
    date_iso = datetime.date.today().isoformat()
    date_compact = date_iso.replace("-", "")
    slug = Path(target).stem if target else (task_type or "protocol")
    safe_slug = re.sub(r"[^A-Za-z0-9._-]", "-", slug)
    path = inc_dir / f"INC-{date_compact}-protocol-{safe_slug}.md"
    # Emits the B-T-D four core sections (docs/README.md) so the file satisfies the
    # INCIDENT_FORM_INVALID gate; sections 2-4 are placeholders for audit backfill.
    body = (
        f"# Incident: protocol deviation (soft gate ignored)\n\n"
        f"- **Path**: {target or '(none)'}\n"
        f"- **Protocol**: {task_type or '(none)'}\n"
        f"- **Task**: {task_id or '(none)'}\n"
        f"- **Date**: {date_iso}\n\n"
        f"## 1. 现象与证伪证据 (B-T-D Evidence)\n\n{detail}\n\n"
        f"## 2. 根因剖析 (5 Whys)\n\n（待人工/审计回填）\n\n"
        f"## 3. 防退化动作清单\n\n（待人工/审计回填）\n\n"
        f"## 4. 经验灌入\n\n（待人工/审计回填）\n"
    )
    path.write_text(body, encoding="utf-8")
    return path
