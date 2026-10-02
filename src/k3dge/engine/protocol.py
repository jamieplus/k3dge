"""Persistent protocol deviation escalation.

`write_incident` is the only protocol-related primitive k3dge keeps: it writes a
human-visible incident note when an agent ignores the soft gate. The audit
protocol's two fallback layers (审计 `audit_default.md` / 复审 `verify_default.md`)
are configured in `.agent/pipeline.toml` via manual-step `protocol` references and
validated by `k3dge check` (PIPELINE_PROTOCOL_NOT_FOUND) — there is no longer a
central `.agent/protocols.toml` registry. See ADR-0018.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path


def _inline(text) -> str:
    """元信息字段压成一行：外部可控文本里的换行会把 `- **Path**: …` 列表截成任意段落（ocr-293）。"""
    if text is None:
        return ""
    return " ".join(str(text).splitlines()).strip()


def _block(text) -> str:
    """正文净化：行首 `#` 转义、去掉会让 `## 2./## 3.` 结构闸误判的裸标题行，长度封顶。

    转义判据是**缩进后**的行首（t-232）：markdown 允许 ≤3 空格的标题缩进，
    `   ## 2. 我伪造的根因` 若因"不以 `#` 开头"被放过，人在 GitHub 上看到的仍是真 H2——
    反伪造保证只对"顶格"生效等于没有保证。结构闸同样按 `^\\s*#` 数节，两侧口径一致。
    """
    if text is None:
        return ""
    out = []
    for ln in str(text).splitlines():
        s = ln.rstrip()
        stripped = s.lstrip()
        if stripped.startswith("#"):
            indent = s[: len(s) - len(stripped)]
            s = indent + "\\" + stripped   # 保留缩进，转义 `#`：不再是标题，B-T-D 结构闸仍数到自己的四节
        elif stripped.startswith(">"):
            # 引用块里的 `#` 标题仍渲染为 H2（ocr2-299）：转义前导 `>`，结构闸只数 `^\s*#`。
            indent = s[: len(s) - len(stripped)]
            s = indent + "\\" + stripped
        elif stripped != "" and set(stripped) <= set("=-") and len(stripped) >= 3:
            # setext 下划线行（`===`/`---`）：上一行文本会被渲染成真 H1/H2（ocr2-299）。
            indent = s[: len(s) - len(stripped)]
            s = indent + "\\" + stripped
        elif stripped.startswith("```") or stripped.startswith("~~~"):
            # 围栏标记原样穿透 ⇒ 后面的 `## 2./3./4.` 被吞进代码块，且产物触发
            # `MD_FENCE_UNCLOSED` 阻塞闸（ocr2-300）：转义首符，不再是围栏。
            indent = s[: len(s) - len(stripped)]
            s = indent + "\\" + stripped
        out.append(s[:2000])
    return "\n".join(out)[:20000]


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
    # 白名单去掉 `.`：docs/incidents/.schema.json 的文件名规则是 `^INC-\d{8}-[\w-]+\.md$`，
    # 中间段不接受点号 ⇒ 带点会产出自相矛盾的破格文件（ocr-292）。
    safe_slug = re.sub(r"[^A-Za-z0-9_-]", "-", slug).strip("-")
    # 长度封顶：Linux 单段文件名上限 255，`target` 来自外部 JSON 完全不受控（ocr-291）。
    # 超长时截断并留 8 位校验和，保证同源输入仍得同名（幂等，不产重复件）。
    if len(safe_slug) > 60:
        import hashlib

        sig = hashlib.sha1(slug.encode("utf-8", "replace")).hexdigest()[:8]
        safe_slug = f"{safe_slug[:52]}-{sig}"
    safe_slug = safe_slug or "protocol"
    path = inc_dir / f"INC-{date_compact}-protocol-{safe_slug}.md"
    # 文件名只含日期+slug：同日同 slug 的第二起事件会 `write_text` 截断覆盖，把第一份人可见审计物
    # 静默丢掉（ocr2-071）。存在即加 `-2`/`-3` 后缀，不覆写。
    if path.is_file():
        _n = 2
        while (inc_dir / f"INC-{date_compact}-protocol-{safe_slug}-{_n}.md").is_file():
            _n += 1
        path = inc_dir / f"INC-{date_compact}-protocol-{safe_slug}-{_n}.md"
    # Emits the B-T-D four core sections (docs/README.md) so the file satisfies the
    # INCIDENT_FORM_INVALID gate; sections 2-4 are placeholders for audit backfill.
    body = (
        f"# Incident: protocol deviation (soft gate ignored)\n\n"
        f"- **Path**: {_inline(target) or '(none)'}\n"
        f"- **Protocol**: {_inline(task_type) or '(none)'}\n"
        f"- **Task**: {_inline(task_id) or '(none)'}\n"
        f"- **Date**: {date_iso}\n\n"
        f"## 1. 现象与证伪证据 (B-T-D Evidence)\n\n{_block(detail)}\n\n"
        f"## 2. 根因剖析 (5 Whys)\n\n（待人工/审计回填）\n\n"
        f"## 3. 防退化动作清单\n\n（待人工/审计回填）\n\n"
        f"## 4. 经验灌入\n\n（待人工/审计回填）\n"
    )
    path.write_text(body, encoding="utf-8")
    return path
