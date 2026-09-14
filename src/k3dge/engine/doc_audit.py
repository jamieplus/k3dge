"""Doc-audit（非阻断、在硬闸之后）：改动文档前路由 k3dit 透镜 + 里程碑 task 兜底。

Extracted from `engine/milestone.py` (A-1 第五块); `milestone` re-exports for back-compat.
Milestone internals (`create_task`/`scan_milestone_tasks`/`get_current_milestone`/`_find_report`)
are imported lazily to avoid an import cycle.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

from k3dge.engine.milestone_files import _is_doc_aux

# 送审文档范围里排除的进程产物（非作者合规对象）。
_AUDIT_EXCLUDE_DOCS = ("docs/reviews/", "docs/tasks/", "docs/generated/")


def _changed_docs(workspace: Path) -> List[str]:
    """Managed docs in the current change set that warrant an authoring audit.

    Excludes process artifacts (reviews/tasks/generated) and archives.
    """
    import subprocess

    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"], cwd=workspace, capture_output=True, text=True
        )
        files = [ln[3:].strip() for ln in out.stdout.splitlines() if ln.strip()]
    except Exception:
        return []
    docs: List[str] = []
    for f in files:
        if not f.startswith("docs/"):
            continue
        parts = set(f.split("/"))
        if "archive" in parts or any(f.startswith(p) for p in _AUDIT_EXCLUDE_DOCS):
            continue
        docs.append(f)
    return docs


def _new_archive_without_note(workspace: Path) -> List[str]:
    """本轮 diff **新进** `docs/**/archive/` 且缺去向标记（`Superseded-by`/`Legacy note`）的文档。

    ADR-0023 §2.2 归档三条件；**只对增量生效**（存量不批量灌噪声），非阻断。
    """
    import subprocess

    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=workspace,
                             capture_output=True, text=True)
        lines = out.stdout.splitlines()
    except Exception:
        return []
    res: List[str] = []
    for ln in lines:
        if len(ln) < 4:
            continue
        code, raw = ln[:2].strip(), ln[3:].strip()
        if code not in ("A", "R"):
            continue
# k3dit:fixnote code-3 R 项拆 " -> " 取新路径（同 diff._parse_porcelain 口径），git mv 进 archive/ 不再整类漏检
        if "R" in code and " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        path = raw.strip()
        if "archive" not in path.split("/") or not path.endswith(".md"):
            continue
        try:
            txt = (workspace / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "Superseded-by" in txt or "Legacy note" in txt:
            continue
        res.append(path)
    return sorted(res)


def _ensure_doc_audit_task(workspace: Path, milestone_id: str, docs: List[str], report: Optional[str] = None):
    """Idempotently open a milestone-scoped doc-audit task (the durability hook).

    Because the task carries `Milestone` (and a `report:` pointer, ADR-0022), the
    seal gate (all tasks done) forces it to be cleared in the milestone round even
    if nobody acts on it at commit time. Returns the new task path, or None if an
    open one already exists.
    """
    from k3dge.engine.milestone import create_task, scan_milestone_tasks

    for t in scan_milestone_tasks(workspace, milestone_id):
        # create_task 把标题折成下划线文件名（doc_audit_*）——只匹配 "doc-audit" 会漏检，
        # 于是每次 doc-audit 都开重复 task（2026-09-03 实测 _4 存在仍建出 _39）。
        name = t.path.name.lower()
        if ("doc-audit" in name or "doc_audit" in name) and t.status != "done":
            return None
    scopes = sorted({d.split("/")[1] for d in docs if len(d.split("/")) > 1})
    hint = ", ".join(scopes[:3]) or "docs"
    title = f"doc-audit: 文档作者合规审计（{hint} 等 {len(docs)} 处）"
    ok, _msg, path = create_task(workspace, title, typ="audit", milestone=milestone_id, priority="P3", report=report)
    return path if ok else None


def _similar_task_hints(workspace: Path, title: str, exclude: Optional[Path] = None) -> List[Tuple[str, str]]:
    """k3che 相似/历史提示——service 语义：skip/失败/坏信封 ⇒ 无提示，**永不阻断创建**。

    语料含 tasks/archive（CacheIndex.rglob 覆盖归档子目录）——历史文件正是重复的
    本体。只提示，不判定：是不是真重复由看的人决定（规则 08：观测≠裁决）。
    """
    from k3dge.engine.pipeline_runner import run_action

    try:
        res = run_action(workspace, "cache.search", arguments={"query": title, "top_k": 6})
    except Exception:  # pragma: no cover - 观测件绝不误伤创建
        return []
    if not res.ok or res.provider != "mcp":
        return []
    try:
        env = json.loads(res.payload or "")
    except ValueError:
        return []
    if not isinstance(env, dict) or not env.get("ok"):
        return []
    excl = exclude.relative_to(workspace).as_posix() if exclude is not None else None
    out: List[Tuple[str, str]] = []
    for r in env.get("results") or []:
        p = str(r.get("path") or "")
        if not p or p == excl:
            continue
        out.append((p, str(r.get("title") or "")))
        if len(out) >= 3:
            break
    return out


# --- k3che 相关文档前路由（service 角色：只产提示，永不进判定链；peer contract §0） ---

_K3CHE_HINT_RE = re.compile(r"<!-- k3che-hints -->.*?<!-- /k3che-hints -->\n?", re.S)


def _related_doc_hints(workspace: Path, docs: List[str], io=None) -> List[Tuple[str, str]]:
    """Ask the cache role for docs related to the changed ones. Any failure ⇒ [] (silent-safe)."""
    from k3dge.engine.pipeline_runner import run_action

    names = [Path(d).name for d in docs[:6] if d]
    if not names:
        return []
    try:
        res = run_action(workspace, "cache.search", io=io, arguments={"query": " ".join(names), "top_k": 3})
    except Exception:  # pragma: no cover - service call must never break the flow
        return []
    if not res.ok or res.provider != "mcp":
        return []  # skip/降级 = 没有提示，仅此而已
    try:
        env = json.loads(res.payload or "")
    except ValueError:
        return []
# k3dit:fixnote code-2 补 isinstance(env, dict) 守卫：list/null 等合法 JSON 信封 ⇒ []（同 _similar_task_hints）
    if not isinstance(env, dict):
        return []
    out: List[Tuple[str, str]] = []
    for r in env.get("results") or []:
        if isinstance(r, dict) and r.get("path"):
            out.append((str(r["path"]), str(r.get("title", ""))))
        if len(out) >= 3:
            break
    return out


def _attach_k3che_hints(workspace: Path, docs: List[str], io=None) -> int:
    """Write/refresh the hints block on the open doc-audit task. Returns #hints written."""
    hints = _related_doc_hints(workspace, docs, io=io)
    if not hints:
        return 0
    tasks_dir = workspace / "docs" / "tasks"
    if not tasks_dir.is_dir():
        return 0
    target = None
    for p in sorted(tasks_dir.glob("*.md")):
        # create_task 把标题里的非字母数字折成下划线：文件名是 doc_audit_*，标题是 doc-audit:
        if p.name.endswith(".done.md") or _is_doc_aux(p.name):
            continue
        if "doc-audit" not in p.name.lower() and "doc_audit" not in p.name.lower():
            continue
        target = p
        break
    if target is None:
        return 0
    block = (
        "<!-- k3che-hints -->\n"
        "## 相关文档提示（k3che · 服务性前路由，非判定；由审计席位取舍）\n\n"
        + "".join(f"- `{path}`" + (f" — {title}" if title else "") + "\n" for path, title in hints)
        + "<!-- /k3che-hints -->\n"
    )
    text = target.read_text(encoding="utf-8")
    text = _K3CHE_HINT_RE.sub("", text).rstrip() + "\n\n" + block
    target.write_text(text, encoding="utf-8")
    return len(hints)


def run_doc_audit(workspace: Path, *, io=None) -> Tuple[str, str]:
    """Non-blocking doc-audit, run AFTER the hard gate (never inside `check`).

    k3dge keeps `check` static (no MCP/LLM — T-01). This step: routes the doc lens
    to k3dit (authoring compliance; ADR conflict/coverage stays in the milestone
    audit), and guarantees a milestone-scoped task so the finding cannot slip.
    Always non-blocking (returns cleanly even if the peer is unavailable).
    status ∈ {reported, clean}.
    """
    import sys

    from k3dge.engine.milestone import _find_report, get_current_milestone
    from k3dge.engine.pipeline_runner import run_action

    io = io or sys.stderr
    mid = get_current_milestone(workspace)
    docs = _changed_docs(workspace)
    archive_unguarded = _new_archive_without_note(workspace)
    if not docs and not archive_unguarded:
        return "clean", "no managed docs changed; nothing to doc-audit."

    try:
        # docs/ targets must route to the Doc Audit lens, not the code passes
        run_action(
            workspace,
            "k3dit.actions.audit",
            io=io,
            arguments={"target_scope": "docs", "milestone_id": mid or ""},
        )  # peer/manual authors the report
    except Exception as exc:
        print(f"WARN[DOWNGRADE] doc-audit lens routing failed ({exc}); report 仍由 k3dit/人产出", file=sys.stderr)
    # Bind the task to the report it audits (1 report = 1 task, ADR-0022) if present.
    found = _find_report(workspace, mid, "audit")
    report_rel = found[0].relative_to(workspace).as_posix() if found else None
    task = _ensure_doc_audit_task(workspace, mid, docs + archive_unguarded, report=report_rel)
    _attach_k3che_hints(workspace, docs, io=io)  # 服务性提示；失败=无提示，绝不无审计
    note = f"；另有 {len(archive_unguarded)} 份新归档缺去向标记（ADR-0023 §2.2）" if archive_unguarded else ""
    if task is None:
        return "reported", (
            f"doc-audit: {len(docs)} 处文档改动{note}；已有未关闭的 doc-audit task（不重复建）。"
        )
    return "reported", (
        f"doc-audit: 报告由 k3dit/人产出，已开里程碑 task `{task.name}`（非阻断；本轮不改，封板闸也会逼这轮闭环）{note}。"
    )
