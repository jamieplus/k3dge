"""审计入口：外部报告落盘、有意留登记、审计腿（ratchet 步进 / loop）。

Extracted from `engine/milestone.py` (A-1 第十二块).
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from k3dge.engine import gates
from k3dge.engine.audit_report import (
    _AUDIT_HEADER,
    _QUALITY_MARKER_RE,
    _find_report,
    _parse_audit_stats,
)
from k3dge.engine.milestone_pointer import _SAFE_MILESTONE_ID_RE, _validate_milestone_id
from k3dge.engine.prompt import Prompt as _Prompt


def scan_pending_findings(workspace: Path) -> Tuple[int, List[str]]:
    """未决 findings（语法 v1：pending/disputed/fixnote 计 open）。

    薄委托 `engine/markers.py`，保留历史返回 (count, ["path#ID", ...])。leftover（有意留）
    照旧不计时；删标（已修）不计时。语法违规**不改计数口径**，由 `k3dge markers --check` 暴露。
    """
    from k3dge.engine import markers as _mk

    ms, _problems = _mk.extract(workspace)
    samples = _mk.open_samples(ms)
    return (len(samples), samples)


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


def _audit_mode(workspace: Path, role: str = "audit") -> str:
    """审计腿形状：`[roles.audit] mode="ratchet"`＝工单模式（ADR-0025）；缺省 oneshot（旧一次性形）。

    名称纪律：不得叫 `scaffold`——该词已指 `templates/scaffold.py` 的脚手架生成工具
    （`k3dge init` 调用），一词两义违反 `docs/adr/AUTHORING.md` 术语规则。
    """
    try:
        try:
            import tomllib
        except ModuleNotFoundError:  # pragma: no cover
            import tomli as tomllib  # type: ignore

        data = tomllib.loads((workspace / ".agent" / "pipeline.toml").read_text(encoding="utf-8"))
        return str((data.get("roles") or {}).get(role, {}).get("mode", "oneshot")).lower()
    except Exception:
        return "oneshot"


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
    from k3dge.engine import audit_checklist as ac, audit_flow, nextstep
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
    # 外部步读**声明面**（gates [checks.audit].stages_produce/stages_verify），
    # 不再硬编码 action ref —— 原 pipeline.toml 的 [pipelines.*] 只有校验、无执行者。
    from k3dge.engine import gates as _gates

    _produce = _gates.stages(workspace, "audit", "produce")
    _verify = _gates.stages(workspace, "audit", "verify")
    streams = {"audit": (_produce[0] if _produce else "", _verify[0] if _verify else "")}
    if ratchet or not _produce:
        streams.pop("audit", None)

    # mandatory audit + fix loop, capped at `max_verify_attempts` verifies.
    degraded = False  # 任一跳降级（downgrades 非空）⇒ 结果记 degraded-manual（ADR-0004 §2.1.11）
    while True:
        attempts = ac.get_verify_attempts(workspace)
        if attempts >= max_verify_attempts:
            msg = f"verify 已超过 {max_verify_attempts} 次仍未闭环，停止自动 loop，转人工干预。"
            _ns = nextstep.NextStep.from_state("escalated", milestone_id)
            nextstep.persist(workspace, _ns)
            return "escalated", msg + "\n" + _ns.render_cli()
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
            # 先判"这一跳是否真跑过"，再谈报告在不在（ADR-0004 §2.1.11）。少了这一步，
            # 仓里一份旧报告就能把 skip / 传输失败兜成闭环——"保证 audit"的第一道。
            call = audit_flow.audit_call_result(produced)
            if call == "refused":
                why = "被跳过（skip 传输）" if produced.skipped else "未成功"
                msg = (
                    f"审计未成：{produce_action} 这一跳{why}（provider={produced.provider}；"
                    f"{produced.detail[:80]}）——空转不得被仓里已有的报告兜成闭环"
                    "（ADR-0004 §2.1.11）；确认传输链与透镜可达后重跑。"
                )
                _ns = nextstep.next_for_rejection(
                    milestone_id, gates.Rejection("audit_noop", msg)
                )
                nextstep.persist(workspace, _ns)
                return "refused", msg + "\n" + _ns.render_cli()
            degraded = degraded or (call == "degraded-manual")
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
                _ns = nextstep.next_for_rejection(
                    milestone_id, gates.Rejection("audit_report_missing", msg)
                )
                nextstep.persist(workspace, _ns)
                return "rejected", msg + "\n" + _ns.render_cli()
            report_path, report_text = found
            if degraded:  # 降级不静默：署名是降级可接受的前提（ADR-0004 §2.1.11）
                from k3dge.engine.process_audit import _SIGN_KEYS, _field

                missing = [k for k in _SIGN_KEYS if not _field(report_text, k)]
                if missing:
                    msg = (
                        f"审计降级到 manual 但报告缺署名/来源 {missing}（{report_path.name}）——"
                        "降级不静默：署名后可记 `degraded-manual` 继续（ADR-0004 §2.1.11）。"
                    )
                    _ns = nextstep.next_for_rejection(
                        milestone_id, gates.Rejection("audit_degraded_unsigned", msg)
                    )
                    nextstep.persist(workspace, _ns)
                    return "refused", msg + "\n" + _ns.render_cli()
            stats = _parse_audit_stats(report_text)
            _ensure_leftovers(workspace, report_text, report_path)
            pending_total += stats["待修"]

        if pending_total == 0:
            break
        # 待修 > 0 across reports -> surface the next-step hint, then ask agent to fix.
        prompt._write(
            nextstep.NextStep.from_state("audit_open", milestone_id, pending=pending_total).render_cli() + "\n"
        )
        # 文案单源：STATE_OPTIONS["audit_open"].question（与 [NEXT] 的 fact 同一判定的两个投影）；
        # countdown/default_yes 是**通道行为**，留在调用点。
        if not prompt.ask(
            nextstep.question_text("audit_open", milestone_id, n=pending_total),
            countdown=60,
            default_yes=True,
        ):
            msg = f"Audit open: {pending_total} 项待修未修复且 agent 拒绝修复。"
            _ns = nextstep.next_for_rejection(
                milestone_id, gates.Rejection("audit_open_declined", msg)
            )
            nextstep.persist(workspace, _ns)
            return "rejected", msg + "\n" + _ns.render_cli()
        # agent fixes externally -> loop re-runs the audit report
        continue

    # verify phase: secondary cross-check of the audit report.
    for _kind, (_produce_action, verify_action) in streams.items():
        if not verify_action:
            continue   # 声明面没给 verify 步（下游可配）⇒ 不做二次核对，不拿空 ref 去跑
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
    result = "degraded-manual" if degraded else "closed"
    status = "audited_degraded" if degraded else "audited"
    msg = (
        f"Milestone {milestone_id}: 审计闭环（{result}；合并审计模块 12 列报告 待修=0），可以谈封板。"
    )
    if degraded:
        msg += ("\n[降级告知] 本轮走了 manual 协议（非独立透镜）且报告已署名，"
                "结果记为 degraded-manual（ADR-0004 §2.1.11）。")
    _ns = nextstep.seal_ready_for(workspace, milestone_id)
    nextstep.persist(workspace, _ns)
    return status, msg + "\n" + _ns.render_cli()
