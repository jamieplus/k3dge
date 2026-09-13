"""Milestone lifecycle engine: alignment check, test regression, and context compaction."""

from __future__ import annotations

import datetime
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from k3dge.engine import adr_gate, gates, process_audit, report_table
from k3dge.engine.evaluator import ConsistencyEngine

from k3dge.engine.task_index import (  # A-1 第七块 re-export
    MILESTONE_RE,
    PRIORITY_RE,
    STATUS_RE,
    TITLE_RE,
    parse_frontmatter,
)
GUIDE_STUB_RE = re.compile(r"<!--\s*k3dge:guide-stub\s*-->", re.IGNORECASE)


_ALLOWED_STATUS = frozenset({"idea", "deferred", "in-progress", "done"})
_TASK_TYPES = frozenset({"audit", "feat", "fix", "docs", "chore", "refactor"})
_ALIGN_STUB_MARKER = "<!-- k3dge:align-stub -->"

# A-1 第二块：指针/id 校验已抽到 `milestone_pointer`；此处 re-export 兼容既有调用面。
from k3dge.engine.milestone_pointer import (  # noqa: E402
    _SAFE_MILESTONE_ID_RE,
    _validate_milestone_id,
    bump_milestone,
    get_current_milestone,
    set_current_milestone,
)


def _align_pass_marker(milestone_id: str) -> str:
    return f"<!-- k3dge:align-pass:{milestone_id} -->"


# A-1 第八块：CHANGELOG 追加已抽到 `changelog`；re-export 兼容调用面。
from k3dge.engine.changelog import (  # noqa: E402
    _append_to_unreleased,
    _changelog_draft_path,
)


# k3dit:leftover value-2 code-13 已把 _count_status 委托 _parse_audit_stats 消分歧；余4扫描器职责各异，全并属refactor
# A-1 第三块：命名/甄别帮助已抽到 `milestone_files`；re-export 兼容调用面。
from k3dge.engine.milestone_files import (  # noqa: E402
    _DOC_AUX_NAMES,
    _FILENAME_MILESTONE_RE,
    _REVIEW_AUX,
    _filename_milestone,
    _has_milestone_token,
    _is_doc_aux,
    _is_review_aux,
)


# A-1 第六块：reviews 归档机械已抽到 `review_archive`；re-export 兼容调用面。
from k3dge.engine.review_archive import (  # noqa: E402
    _living_review_files,
    _reviews_to_archive,
    _rewrite_leftover_links,
    _safe_archive_dir,
)


def scan_unfilled_guides(workspace: Path) -> List[str]:
    """Names of guide stubs in docs/guides/ still carrying `<!-- k3dge:guide-stub -->`."""
    guides_dir = workspace / "docs" / "guides"
    if not guides_dir.exists():
        return []
    out: List[str] = []
    for g in sorted(guides_dir.glob("*.md")):
        if g.name == "AUTHORING.md":   # 说明书讲桩是元文本，不是桩本身（doc-catalog 先例同形）
            continue
        try:
            text = g.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            out.append(g.name)
            continue
        if GUIDE_STUB_RE.search(text):
            out.append(g.name)
    return out


# A finding pinned at its 位置 next to the code/doc — a *pointer only* (like
# guide-stub). The disposition authority stays the 12-col report + tasks; these
# markers carry no rationale/how-to-fix (that would become a 3rd fact source,
# and L1 does not hash comments so the gate cannot catch comment drift).
def scan_pending_findings(workspace: Path) -> Tuple[int, List[str]]:
    """未决 findings（语法 v1：pending/disputed/fixnote 计 open）。

    薄委托 `engine/markers.py`，保留历史返回 (count, ["path#ID", ...])。leftover（有意留）
    照旧不计时；删标（已修）不计时。语法违规**不改计数口径**，由 `k3dge markers --check` 暴露。
    """
    from k3dge.engine import markers as _mk

    ms, _problems = _mk.extract(workspace)
    samples = _mk.open_samples(ms)
    return (len(samples), samples)


from k3dge.engine.task_index import (  # A-1 第七块 re-export
    MilestoneTask,
    TaskIndex,
    list_tasks,
    scan_milestone_tasks,
)


# A-1 第九块：task 写入核心已抽到 `task_write`；re-export 兼容调用面。
from k3dge.engine.task_write import (  # noqa: E402
    _auto_backfill_reviews,
    create_task,
    mark_task_done,
)


def run_milestone_alignment(workspace: Path, milestone_id: str) -> Tuple[bool, str, List[MilestoneTask]]:
    id_err = _validate_milestone_id(milestone_id)
    if id_err:
        return False, id_err, []

    tasks = scan_milestone_tasks(workspace, milestone_id)
    if not tasks:
        return False, f"No tasks found for milestone '{milestone_id}' under docs/tasks/", []

    invalid = [t for t in tasks if t.status not in _ALLOWED_STATUS]
    if invalid:
        listing = "\n".join(f"  - {t.path.name} (status: {t.status})" for t in invalid)
        return False, f"Invalid Status (not idea|deferred|in-progress|done):\n{listing}", tasks

    # 前置闸/动作：读「硬闸契约」`[checks.align]`（ADR-0001 §2 第 8 条）。
    pending = [t for t in tasks if t.status != "done"]

    def _tasks_all_done():
        if pending:
            return f"Cannot align milestone '{milestone_id}'. {len(pending)} pending tasks:\n" + "\n".join(
                f"  - {t.path.name} (status: {t.status})" for t in pending
            )
        return None

    def _full_matrix():
        report = ConsistencyEngine(workspace).evaluate(run_tests=True, force_full=True)
        if not report.passed:
            return f"Regression tests failed during milestone alignment:\n{report.render()}"
        return None

    _reg = {"tasks_all_done": _tasks_all_done, "full_matrix": _full_matrix}
    for _gid in gates.preconditions(workspace, "align"):
        _fn = _reg.get(_gid)
        if _fn is None:
            return False, f"[ALIGN REJECTED] gate contract references unknown gate id: '{_gid}'", tasks
        _err = _fn()
        if _err:
            return False, _err, tasks
    for _aid in gates.actions(workspace, "align"):
        _fn = _reg.get(_aid)
        if _fn is None:
            return False, f"[ALIGN REJECTED] gate contract references unknown action id: '{_aid}'", tasks
        _err = _fn()
        if _err:
            return False, _err, tasks

    # 2. 生成极简对齐评审报告
    today = datetime.date.today().isoformat()
    review_file = workspace / "docs" / "reviews" / f"{today}-{milestone_id}-align.md"
    if not review_file.exists():
        review_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# 里程碑对齐与验收报告: {milestone_id}",
            _ALIGN_STUB_MARKER,
            _align_pass_marker(milestone_id),
            "",
            f"- **Date**: {today}",
            "- **Regression**: PASS (k3dge milestone align Full Matrix)",
            f"- **Completed Tasks**: {len(tasks)}",
            "",
            "## 1. 目标达成清单",
            "",
        ]
        for t in tasks:
            lines.append(f"- [x] `{t.path.name}`")
        lines.extend([
            "",
            "## 2. 重构准入评估",
            "> 仅在存在阻塞后续扩展的设计缺陷时启动重构；常规情况下跳过大重构。",
            "",
            "- [ ] 是否存在阻塞后续阶段的架构/接口缺陷？(Yes/No)",
            "- [ ] 是否存在超出阈值的深层嵌套坏味道？(Yes/No)",
            "- 处置结论: 跳过重构直接封板 / 触发定向微调",
            "",
            "## 3. 验收结论",
            "目标达成，契约一致，准予封板压缩。",
            "",
        ])
        review_file.write_text("\n".join(lines), encoding="utf-8")

    # 3. 指南完成度扫描（预警非阻断）：docs/guides/ 残留的 TODO 桩在 seal 时会被硬拦
    unfilled = scan_unfilled_guides(workspace)
    note = ""
    if unfilled:
        note = (
            " WARNING: unfilled guide stubs (will block seal): "
            + ", ".join(unfilled)
        )

    msg = (
        f"[ALIGN] Full Matrix verification PASS for milestone '{milestone_id}'.\n"
        f"  Created review scaffold: docs/reviews/{today}-{milestone_id}-align.md\n"
        f"  Milestone is seal-eligible. Audit is mandatory before seal "
        f"(k3dge milestone seal -> enter-seal prompt -> k3dit.actions.audit)."
    )
    if note:
        msg += note
    return True, msg, tasks


def _seal_review_gate(workspace: Path, milestone_id: str, tasks: List[MilestoneTask]) -> Optional[str]:
    """Gate 1: a filled audit review listing every task. Returns rejection msg or None."""
    reviews_dir = workspace / "docs" / "reviews"
    matching_reviews = []
    stub_reviews = []
    missing_pass = []
    incomplete_reviews: list[Path] = []
    pass_mark = _align_pass_marker(milestone_id)
    if reviews_dir.exists():
        for f in reviews_dir.iterdir():
            if not f.is_file() or not _has_milestone_token(f.name, milestone_id):
                continue
            try:
                content = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if not content.strip():
                continue
            if _ALIGN_STUB_MARKER in content:
                stub_reviews.append(f)
                continue
            if pass_mark not in content:
                missing_pass.append(f)
                continue
            # 验收：正文必须列出该里程碑下全部 done 任务名（防空报告）
            missing_tasks = [t for t in tasks if t.path.name not in content]
            if missing_tasks:
                incomplete_reviews.append(f)
                continue
            matching_reviews.append(f)
    if matching_reviews:
        return None
    if stub_reviews:
        return (
            f"[SEAL REJECTED] Review for milestone '{milestone_id}' is still an align stub.\n"
            f"  Remove `{_ALIGN_STUB_MARKER}` after filling docs/reviews/ (keep `{pass_mark}`)."
        )
    if missing_pass:
        return (
            f"[SEAL REJECTED] Review for milestone '{milestone_id}' has no align-pass marker.\n"
            f"  Run 'k3dge milestone align {milestone_id}' (writes `{pass_mark}`) then fill the stub."
        )
    if incomplete_reviews:
        return (
            f"[SEAL REJECTED] Review for milestone '{milestone_id}' does not list all tasks.\n"
            f"  Missing in {incomplete_reviews[0].name}: {[t.path.name for t in tasks if t.path.name not in incomplete_reviews[0].read_text(encoding='utf-8')]}"
        )
    return (
        f"[SEAL REJECTED] Missing audit review document for milestone '{milestone_id}'.\n"
        f"  Run 'k3dge milestone align {milestone_id}' and fill docs/reviews/ before sealing."
    )


def _seal_archive(workspace: Path, milestone_id: str, tasks: List[MilestoneTask]) -> Tuple[bool, str]:
    """Move tasks/reviews into archive (collision-checked, rollback on failure) + bump."""
    reviews_dir = workspace / "docs" / "reviews"
    pass_mark = _align_pass_marker(milestone_id)
    task_archive, err = _safe_archive_dir(workspace, "tasks", milestone_id)
    if task_archive is None:
        return False, err
    review_archive, err = _safe_archive_dir(workspace, "reviews", milestone_id)
    if review_archive is None:
        return False, err
    to_archive_reviews = _reviews_to_archive(reviews_dir, milestone_id, pass_mark)
    collisions = [t.path.name for t in tasks if (task_archive / t.path.name).exists()]
    collisions.extend(rev.name for rev in to_archive_reviews if (review_archive / rev.name).exists())
    if collisions:
        return False, (
            f"Cannot seal milestone '{milestone_id}': archive target already exists: {collisions}"
        )
    leftover_path = reviews_dir / "LEFTOVERS.md"
    leftover_orig: str | None = None
    if leftover_path.is_file():
        try:
            leftover_orig = leftover_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            leftover_orig = None
    task_archive.mkdir(parents=True, exist_ok=True)
    if to_archive_reviews:
        review_archive.mkdir(parents=True, exist_ok=True)
    moved_records: list[tuple[Path, Path]] = []
    try:
        for t in tasks:
            target = task_archive / t.path.name
            shutil.move(str(t.path), str(target))
            moved_records.append((target, t.path))
        for rev in to_archive_reviews:
            target = review_archive / rev.name
            shutil.move(str(rev), str(target))
            moved_records.append((target, rev))
            _rewrite_leftover_links(workspace, rev.name, f"archive/{milestone_id}/{rev.name}")
    except Exception as exc:
        if leftover_orig is not None:
            try:
                leftover_path.write_text(leftover_orig, encoding="utf-8")
            except OSError:
                pass
        rollback_errors: list[str] = []
        for current, original in reversed(moved_records):
            try:
                shutil.move(str(current), str(original))
            except Exception as rb_exc:
                rollback_errors.append(f"{current} -> {original}: {rb_exc}")
        if rollback_errors:
            return False, (
                f"Failed to seal milestone '{milestone_id}': {exc}; "
                f"rollback incomplete: {rollback_errors}"
            )
        return False, f"Failed to seal milestone '{milestone_id}', rolled back: {exc}"
    review_note = (
        f" and {len(to_archive_reviews)} reviews to docs/reviews/archive/{milestone_id}/"
        if to_archive_reviews
        else ""
    )
    sealed = (
        f"Sealed milestone '{milestone_id}'. Archived {len(tasks)} tasks to "
        f"docs/tasks/archive/{milestone_id}/{review_note}."
    )
    try:
        nxt = bump_milestone(workspace)
        return True, f"{sealed} Next milestone: {nxt}"
    except Exception:
        return True, f"{sealed} (milestone bump failed)"


def seal_preconditions_error(workspace: Path, milestone_id: str) -> Optional[str]:
    """策略层：按「硬闸契约」`[checks.seal].preconditions` 求值全部前置闸，返回首个错误（None=全绿）。

    与 `seal_milestone`（纯归档动作）分离：**何时可封＝策略（本函数）**，封板归档＝动作。
    未实现的 id 视为配置错（拒绝，不让声明空转）。
    """
    from k3dge.engine.audit_trigger import audit_closed

    tasks = scan_milestone_tasks(workspace, milestone_id)
    pending = [t for t in tasks if t.status != "done"]
    unfilled = scan_unfilled_guides(workspace)
    gate_fns = {
        "tasks_all_done": lambda: (
            f"Cannot seal milestone '{milestone_id}'. Tasks not done: "
            f"{[t.path.name for t in pending]}" if pending else None
        ),
        "audit_closed": lambda: (
            None if audit_closed(workspace, milestone_id)
            else f"[SEAL REJECTED] Milestone '{milestone_id}' audit not closed（无 12 列报告 / 待修≠0）。"
        ),
        "evidence_chain": lambda: process_audit.evidence_chain_error(workspace, milestone_id),
        "align_pass": lambda: _seal_review_gate(workspace, milestone_id, tasks),
        "guides_filled": lambda: (
            f"[SEAL REJECTED] Unfilled guide stubs detected in docs/guides/: {unfilled}.\n"
            f"  Complete the documentation before milestone seal." if unfilled else None
        ),
        "adrs_all_accepted": lambda: adr_gate.adrs_all_accepted(workspace),
        "adr_landed": lambda: adr_gate.adr_landed(workspace),
    }
    for gid in gates.preconditions(workspace, "seal"):
        fn = gate_fns.get(gid)
        if fn is None:
            return f"[SEAL REJECTED] gate contract references unknown gate id: '{gid}'"
        err = fn()
        if err:
            return err
    return None


def seal_milestone(workspace: Path, milestone_id: str) -> Tuple[bool, str]:
    """纯归档动作：id 合法 + 有任务 + 状态合法 → `_seal_archive`。策略闸在 `seal_preconditions_error`。"""
    id_err = _validate_milestone_id(milestone_id)
    if id_err:
        return False, id_err

    tasks = scan_milestone_tasks(workspace, milestone_id)
    if not tasks:
        return False, f"No tasks to seal for milestone '{milestone_id}'."

    invalid = [t for t in tasks if t.status not in _ALLOWED_STATUS]
    if invalid:
        return False, (
            f"Cannot seal milestone '{milestone_id}'. Invalid Status: "
            f"{[t.path.name for t in invalid]}"
        )

    return _seal_archive(workspace, milestone_id, tasks)


# ---------------------------------------------------------------------------
# Seal-flow state machine (ADR-0004 §2.1.2, revised 2026-09-01)
#
#   Full Matrix (align, no prompt)
#     -> enter-seal prompt (NO countdown; N = treat as normal commit)
#     -> mandatory audit via k3dit peer (pipeline transports)
#     -> parse 待修 / 有意留 / 已修
#         有意留 -> LEFTOVERS.md, proceeds
#         待修 > 0 -> "agent 修?" prompt (countdown, timeout default = fix) -> fix -> re-audit (loop)
#         待修 = 0 -> verify (best-effort) -> seal (archive + version + milestone bump)
#
# k3dge never audits or scores; it invokes the k3dit lens and gates on the
# produced 12-col report. The work agent fixes; k3dit audits; k3dge routes.
# ---------------------------------------------------------------------------

# A-1 第四块：report 查找/归类/计数已抽到 `audit_report`；re-export 兼容调用面。
from k3dge.engine.audit_report import (  # noqa: E402
    _AUDIT_HEADER,
    _QUALITY_MARKER_RE,
    _find_audit_report,
    _find_report,
    _parse_audit_stats,
    _report_kind,
)


def _align_review_path(workspace: Path, milestone_id: str) -> Optional[Path]:
    """Locate the generated align review scaffold for a milestone."""
    reviews = workspace / "docs" / "reviews"
    if not reviews.is_dir():
        return None
    for f in sorted(reviews.iterdir()):
        if (
            f.is_file()
            and f.suffix == ".md"
            and "-align.md" in f.name
            and _has_milestone_token(f.name, milestone_id)
        ):
            return f
    return None


def _strip_align_stub(workspace: Path, milestone_id: str) -> None:
    """Mark the align scaffold as filled so the seal gate (align-stub check) passes.

    The mandatory audit now *is* the real verification; the align scaffold is a
    structural placeholder only.
    """
    p = _align_review_path(workspace, milestone_id)
    if not p:
        return
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    if _ALIGN_STUB_MARKER in text:
        p.write_text(text.replace(_ALIGN_STUB_MARKER, "").strip() + "\n", encoding="utf-8")


def persist_external_audit_report(
    workspace: Path,
    milestone_id: str,
    content: str,
    scope: str = "external",
    kind: str = "audit",
) -> Path:
    """Persist a human/agent-submitted audit report as the canonical on-disk report.

    External audit sources (a human pasting a report into the dialog, or an agent
    forwarding one) must be landed under docs/reviews/ so the seal flow can gate on
    it via `_find_audit_report` / `_parse_audit_stats`. If the content lacks the
    12-col header, a canonical header is prepended so downstream parsing works; the
    latest submission for a (milestone, scope) overwrites any prior one.
    """
    id_err = _validate_milestone_id(milestone_id)
    if id_err:
        raise ValueError(id_err)
    if scope and not _SAFE_MILESTONE_ID_RE.fullmatch(scope):
        raise ValueError(
            f"Invalid scope '{scope}': use a letter/digit start, then letters, "
            "digits, '.', '_' or '-' only (no path separators)."
        )
    reviews = workspace / "docs" / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    norm = (content or "").replace(" ", "")
    if _AUDIT_HEADER.replace(" ", "") not in norm:
        header = (
            f"# 外部审计报告（人工提交，milestone {milestone_id}）\n\n"
            "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        )
        content = header + (content.strip() + "\n" if content.strip() else "")
    today = datetime.date.today().isoformat()
    if kind == "quality" and not _QUALITY_MARKER_RE.search(content):
        content = f"<!-- k3dge:kind: quality -->\n{content}"
    suffix = "quality" if kind == "quality" else "audit"
    path = reviews / f"{today}-{milestone_id}-{scope}-{suffix}.md"
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def _ensure_leftovers(workspace: Path, text: str, report_path: Path) -> None:
    """Append 有意留 rows to docs/reviews/LEFTOVERS.md (idempotent by row ID)."""
    counts = _parse_audit_stats(text)
    if counts["有意留"] == 0:
        return
    ids = counts.get("_ids_有意留", [])
    if not ids:
        return
    leftover_path = workspace / "docs" / "reviews" / "LEFTOVERS.md"
    existing = leftover_path.read_text(encoding="utf-8") if leftover_path.is_file() else ""
    new_lines = []
    for rid in ids:
        marker = f"| {rid} |"
        if marker in existing or marker in "\n".join(new_lines):
            continue
        new_lines.append(f"> | {rid} | 有意留 | 见 {report_path.name} |")
    if not new_lines:
        return
    block = "\n".join(new_lines) + "\n"
    if "## 有意留" not in existing:
        block = "\n## 有意留（审计有意保留，非待修）\n" + block
    leftover_path.write_text(existing + block, encoding="utf-8")


from k3dge.engine.prompt import Prompt as _Prompt  # A-1 首块：Prompter 已抽到 prompt.py；保留名兼容调用面


def _write_closure_note(workspace: Path, milestone_id: str) -> Path:
    """Emit the context-compression closure checklist for a sealed milestone.

    k3dge seals the mechanical part (archive + version + pointer); the real
    "收摊" is compressing context — documenting the unadopted/failed options,
    pruning unrelated context, updating design docs, then committing. k3dge
    cannot judge what is unrelated, so it lays down the checklist and stops.
    """
    today = datetime.date.today().isoformat()
    try:
        from k3dge.engine.version import get_version

        sealed_version = get_version(workspace) or "?"
    except Exception:
        sealed_version = "?"
    audit_reports = ",".join(
        sorted(f.name for f in (workspace / "docs" / "reviews").glob(f"*-{milestone_id}-*.md")
               if f.name.endswith(("-audit.md", "-quality.md")))) or "-"
    p = workspace / "docs" / "reviews" / f"{today}-{milestone_id}-closure.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        return p
    p.write_text(
        "\n".join(
            [
                f"# 封板收摊清单（上下文压缩）: {milestone_id}",
                "",
                f"- **Sealed**: {today}",
                "- 归档/版本/指针已由 `seal` 完成；以下由人/agent 补齐（k3dit 判内容，k3dge 不替判）：",
                "",
                "## 1. 落盘失败/未采用的方案",
                "- [ ] 本里程碑讨论过但**未采用**的方案 → 写 `docs/adr/`（含被否原因）或 `docs/incidents/`（B-T-D）",
                "- [ ] 失败尝试 → `docs/incidents/INC-YYYYMMDD-<TYPE>-<slug>.md`",
                "",
                "## 2. 清理无关上下文",
                "- [ ] 删除/折叠与现行方案无关的草稿、分支说明",
                "",
                "## 3. 更新设计文档",
                "- [ ] `docs/architecture/overview.md` 对齐到已封板的现实",
                "- [ ] 相关 ADR 标注 supersedes / 现行范围",
                "",
                "## 4. 提交里程碑",
                "- [ ] `k3dge check` 绿 → 提交（归档 + 收摊 + 文档一起进一个 commit）",
                "",
                "## 5. 决策轨迹（TSV：show-me-your-work 洁净室移植——ts/phase/decision/why/evidence/result，evidence=指针非散文）",
                "ts\tphase\tdecision\twhy\tevidence\tresult",
                f"{today}\tseal\tseal {milestone_id}\t审计双腿闭环\t{audit_reports}\t{sealed_version}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return p


# A-1 第五块：doc-audit 族已抽到 `doc_audit`；re-export 兼容调用面。
from k3dge.engine.doc_audit import (  # noqa: E402
    _attach_k3che_hints,
    _changed_docs,
    _ensure_doc_audit_task,
    _new_archive_without_note,
    _related_doc_hints,
    _similar_task_hints,
    run_doc_audit,
)


def _audit_mode(workspace: Path, role: str = "audit") -> str:
    """审计腿形状：`[roles.audit] mode="ratchet"`＝工单模式（ADR-0025）；缺省 scaffold（旧形）。"""
    try:
        try:
            import tomllib
        except ModuleNotFoundError:  # pragma: no cover
            import tomli as tomllib  # type: ignore

        data = tomllib.loads((workspace / ".agent" / "pipeline.toml").read_text(encoding="utf-8"))
        return str((data.get("roles") or {}).get(role, {}).get("mode", "scaffold")).lower()
    except Exception:
        return "scaffold"


def _ratchet_audit_step(workspace: Path, milestone_id: str, io=None, role: str = "audit") -> Tuple[str, str]:
    """审计腿一步（ratchet）：建单→探单→collect→（merge 欠账幂等重试）。一步一返回，进程不等人。"""
    from k3dge.engine import audit_flow
    from k3dge.engine import worktree as _wt

    state = audit_flow._load_state(workspace)
    mine = [j for j in state.get("jobs", []) if j.get("milestone_id") == milestone_id
            and j.get("role", "audit") == role]
    pending_merge = [j for j in mine if j.get("state") == "collected" and not j.get("merge_ok", True)]
    if pending_merge:
        j = pending_merge[-1]
        # 编排自家产物（state/checklist/reviews/tasks）不是"人的未提交"；原则性白名单
        r = _wt.merge_back(workspace, j.get("milestone_id") or "adhoc",
                           accept_dirty=(audit_flow.STATE_REL, ".agent/audit_checklist.json",
                                         "docs/reviews/", "docs/tasks/"))
        if r.get("ok"):
            j["merge_ok"] = True
            audit_flow._save_state(workspace, state)
            return "closed", f"写回重试成功（{r.get('mode')}）。"
        return "stalled", f"写回仍未闭（{r.get('mode')}）：{r.get('message', '')[:90]}——人工 rebase 后再跑本命令幂等重试。"
    inflight = [j for j in mine if j.get("state") not in ("collected", "failed")]
    if not inflight:
        done = [j for j in mine if j.get("state") == "collected" and j.get("merge_ok", True)
                and j.get("report") and (j.get("counts") or {}).get("待修", 0) == 0]
        if done:  # 本里程碑已有签署报告且**待修=0**并写回闭 ⇒ 审计腿即成（报告在场不代表闭环）
            return "closed", f"本里程碑签署报告已闭环（{done[-1]['report']}；待修 {done[-1].get('counts', {}).get('待修', '?')}）。"
        r = audit_flow.submit_audit(workspace, milestone_id, io=io, role=role)
        if not r.get("ok"):
            return "stalled", f"建单失败：{str(r.get('detail') or r.get('state'))[:120]}"
        return "progress", f"棘轮工单已建：{r['job_id']}（{role} 腿判据在机构侧席位，k3dge 不代笔）。"
    j = inflight[-1]
    st = audit_flow.peer_status(workspace, j["job_id"], io=io)
    if not st.get("ok"):
        return "progress", f"工单 {j['job_id']} 对端不可探：{str(st.get('message', ''))[:80]}"
    if st.get("escalated"):
        return "stalled", f"工单 {j['job_id']} 有升级条目 {st['escalated']}：等人 k3dit adjudicate。"
    if st.get("state") == "done":
        c = audit_flow.collect_audit(workspace, milestone_id, j["job_id"], io=io)  # role 随工单记录走
        if c.get("ok"):
            if c.get("state") == "open":
                # 报告已落盘但 `待修>0`（未尽项完结 / 未清）⇒ 不闭环、不 merge；交回 [NEXT] audit_open
                return "open", (f"未尽项报告已落盘 {c.get('report')}（待修 {c.get('pending')}）："
                                "需人工/CLI agent 处理未关项后重审（如配对文件只需 `k3dge sync`）。")
            if c.get("merge", {}).get("ok") is False:
                return "stalled", f"报告已落盘但写回未闭：{c['merge'].get('message', '')[:90]}"
            return "closed", f"签署报告落盘 {c.get('report')}；写回 {c.get('merge', {}).get('mode', 'n/a')}；待修 {c.get('pending')}。"
        return "progress", f"collect 未通过：{str(c.get('message') or c.get('error') or c.get('state'))[:100]}"
    return "progress", f"工单 {j['job_id']} 对端态 {st.get('state')}，open={st.get('open', [])}。"


def run_audit_flow(
    workspace: Path,
    milestone_id: str,
    *,
    prompter: Optional[_Prompt] = None,
    max_verify_attempts: int = 3,
) -> Tuple[str, str]:
    """Independent audit entry: the merged audit module (ADR-0025) produces ONE
    12-col report (k3dit audit leg; quality is a window inside the module, not an
    independent peer). 待修==0 counts as "audited once"; verify checks that one
    report. Returns (status, message); status ∈ {audited, rejected, escalated}.
    Seal unlocks only after this closes (`run_seal_flow`).
    """
    from k3dge.engine import audit_checklist as ac, nextstep
    from k3dge.engine.pipeline_runner import run_action

    prompt = prompter or _Prompt.default()
    # Initiating an audit resets the condition checklist (fresh verify budget +
    # started_at stamp), whether triggered manually (`milestone audit`) or via a hook.
    ac.reset_for_audit(workspace, milestone_id)

    ratchet = _audit_mode(workspace) == "ratchet"
    if ratchet:
        # 审计腿＝工单步进（ADR-0025）：一次调用推一步，绝不在闸里等席；步没 closed 就交回 [NEXT]。
        step_status, step_msg = _ratchet_audit_step(workspace, milestone_id, io=prompt.out_stream)
        if step_status != "closed":
            if step_status == "progress":
                return "ratchet_open", step_msg + "\n" + nextstep.NextStep.from_state(
                    "ratchet_open", milestone_id, reasons=[step_msg[:120]]).render_cli()
            if step_status == "open":
                return "audit_open", step_msg + "\n" + nextstep.NextStep.from_state(
                    "audit_open", milestone_id, reasons=[step_msg[:160]]).render_cli()
            return "escalated", step_msg + "\n" + nextstep.NextStep.from_state(
                "escalated", milestone_id).render_cli()

    # 单报告（ADR-0025 合并审计模块）：一轮 = 一份 12 列；quality 是模块内窗口，
    # 不再是独立 peer/report。ratchet 模式下审计腿已由步进器闭环，streams 空。
    streams = {"audit": ("k3dit.actions.audit", "k3dit.actions.verify")}
    if ratchet:
        streams.pop("audit")

    # mandatory audit + fix loop, capped at `max_verify_attempts` verifies.
    while True:
        attempts = ac.get_verify_attempts(workspace)
        if attempts >= max_verify_attempts:
            msg = f"verify 已超过 {max_verify_attempts} 次仍未闭环，停止自动 loop，转人工干预。"
            return "escalated", msg + "\n" + nextstep.NextStep.from_state("escalated", milestone_id).render_cli()
        ac.bump_verify_attempt(workspace)

        # produce phase: run every stream, then collect its report.
        pending_total = 0
        for kind, (produce_action, _verify_action) in streams.items():
            # Action-level arguments only — no pass numbers (ADR-0006 §2.3.8). The lens
            # entry decides internally how many passes that takes.
            produced = run_action(
                workspace,
                produce_action,
                io=prompt.out_stream,
                arguments={"target_scope": f"milestone {milestone_id}", "milestone_id": milestone_id},
            )
            found = _find_report(workspace, milestone_id, kind)
            if found is None:
                hint = ""
                try:
                    import json as _json

                    _body = _json.loads(produced.payload) if produced.payload else {}
                    if _body.get("report_path"):
                        hint = (
                            f" {produced.provider} 已给出落点建议 `{_body['report_path']}`"
                            f"（lens_count={_body.get('lens_count')}）；k3dge 不代笔正文。"
                        )
                except (ValueError, AttributeError):
                    pass
                msg = (
                    f"Audit is mandatory: no 12-col {kind} report found under docs/reviews/. "
                    f"Persist one (`k3dge milestone audit-submit {milestone_id} ... --scope ...` "
                    f"or run the peer per docs/protocols/) and re-run audit.{hint}"
                    + ("" if not produced.downgrades else
                       f" [本轮降级：{'; '.join(produced.downgrades)}]")
                )
                return "rejected", msg + "\n" + nextstep.next_for_rejection(milestone_id, msg).render_cli()
            report_path, report_text = found
            stats = _parse_audit_stats(report_text)
            _ensure_leftovers(workspace, report_text, report_path)
            pending_total += stats["待修"]

        if pending_total == 0:
            break
        # 待修 > 0 across reports -> surface the next-step hint, then ask agent to fix.
        prompt._write(
            nextstep.NextStep.from_state("audit_open", milestone_id, pending=pending_total).render_cli() + "\n"
        )
        if not prompt.ask(
            f"审计/质量共发现 {pending_total} 项待修。是否由 agent 修复？（超时默认修复）",
            countdown=60,
            default_yes=True,
        ):
            msg = f"Audit open: {pending_total} 项待修未修复且 agent 拒绝修复。"
            return "rejected", msg + "\n" + nextstep.NextStep(
                state="rejected", milestone=milestone_id, note="stop / 转人工干预（待修未修复且 agent 拒绝修复）"
            ).render_cli()
        # agent fixes externally -> loop re-runs the audit report
        continue

    # verify phase: secondary cross-check of the audit report.
    for _kind, (_produce_action, verify_action) in streams.items():
        # Verify is per-report and needs to be told *which* report (the check tools take a
        # path); without this the mcp transport can never succeed and falls to manual.
        found = _find_report(workspace, milestone_id, _kind)
        verify_args = {"milestone_id": milestone_id}
        if found:
            verify_args["path"] = str(found[0].relative_to(workspace).as_posix())
        try:
            run_action(workspace, verify_action, io=prompt.out_stream, arguments=verify_args)
        except Exception:
            pass
    ac.reset_verify_attempts(workspace)
    msg = f"Milestone {milestone_id}: 审计闭环（合并审计模块 12 列报告 待修=0），可以谈封板。"
    return "audited", msg + "\n" + nextstep.NextStep.from_state("seal_ready", milestone_id).render_cli()


def run_seal_flow(
    workspace: Path,
    milestone_id: str,
    *,
    prompter: Optional[_Prompt] = None,
    skip_enter_prompt: bool = False,
) -> Tuple[str, str]:
    """Seal = archive + version + pointer. Requires a *closed* audit first.

    The boundary is not "when does a milestone end" (no ruler) — it is the audit
    loop closing (12-col, 待修==0). Only after that do we ask "封板?", which is
    really "要不要压缩上下文并收摊". status ∈ {sealed, deferred, audit_needed}.
    """
    from k3dge.engine import nextstep
    from k3dge.engine.audit_trigger import audit_closed

    prompt = prompter or _Prompt.default()

    if "audit_closed" in gates.preconditions(workspace, "seal") and not audit_closed(workspace, milestone_id):
        msg = f"Milestone {milestone_id}: 未审计（待修未归零或无 12 列报告），不可封板。"
        return "audit_needed", msg + "\n" + nextstep.NextStep.from_state("audit_needed", milestone_id).render_cli()

    # enter-seal prompt — NO countdown; N = keep milestone open. Skipped with --yes.
    if not skip_enter_prompt and not prompt.ask(
        f"里程碑 {milestone_id} 审计已闭环，封板？", default_yes=False
    ):
        msg = f"Milestone {milestone_id}: seal deferred — 不封，里程碑继续挂着。"
        return "deferred", msg + "\n" + nextstep.NextStep.from_state("deferred", milestone_id).render_cli()

    # 动作：读「硬闸契约」`[checks.seal].actions`（ADR-0001 §2 第 8 条）——执行器按声明跑；
    # 未实现的 id 视为配置错（拒绝，不让声明空转）。
    def _full_matrix():
        ok, amsg, _ = run_milestone_alignment(workspace, milestone_id)
        if not ok:
            return False, amsg
        _strip_align_stub(workspace, milestone_id)
        return True, ""

    def _archive():
        err = seal_preconditions_error(workspace, milestone_id)
        if err:
            return False, err
        return seal_milestone(workspace, milestone_id)

    def _closure_note():
        p = _write_closure_note(workspace, milestone_id)
        return True, f"\n  收摊清单: {p.relative_to(workspace)}"

    def _prune():
        try:  # end-flow 清理钩子：派生件（worktree/已并入的审计线）收口即删；史在主干
            from k3dge.engine.audit_flow import prune_finished

            pr = prune_finished(workspace)
            if pr.get("pruned"):
                return True, f"\n  审计派生件清理: {pr['pruned']} 组"
        except Exception:
            pass
        return True, ""

    registry = {"full_matrix": _full_matrix, "archive": _archive,
                "closure_note": _closure_note, "prune": _prune}
    msg = ""
    for aid in gates.actions(workspace, "seal"):
        fn = registry.get(aid)
        if fn is None:
            msg = f"[SEAL REJECTED] gate contract references unknown action id: '{aid}'"
            return "rejected", msg + "\n" + nextstep.next_for_rejection(milestone_id, msg).render_cli()
        ok, out = fn()
        if not ok:
            return "rejected", out + "\n" + nextstep.next_for_rejection(milestone_id, out).render_cli()
        msg += out
    return "sealed", msg + "\n" + nextstep.NextStep.from_state("sealed", milestone_id).render_cli()
