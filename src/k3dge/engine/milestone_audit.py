"""审计入口：外部报告落盘、有意留登记、审计腿（ratchet 步进 / loop）。

Extracted from `engine/milestone.py` (A-1 第十二块).
"""
from __future__ import annotations

import datetime
import json
import os
import tempfile
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


def _git_is_ancestor(workspace: Path, anc: str, desc: str) -> bool:
    """`anc` 是 `desc` 的祖先（含相等由调用方先判）。"""
    import subprocess

    try:
        r = subprocess.run(
            ["git", "-C", str(workspace), "merge-base", "--is-ancestor", anc, desc],
            capture_output=True, text=True,
        )
    except OSError:  # pragma: no cover - 环境异常
        return False
    return r.returncode == 0


def _git_tree(workspace: Path, oid: str) -> str:
    """commit 的 tree id；认不出则空串。"""
    import subprocess

    try:
        r = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", f"{oid}^{{tree}}"],
            capture_output=True, text=True,
        )
    except OSError:  # pragma: no cover
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _baseline_covers(
    workspace: Path, fresh: str, job_baseline: str, landed_head: str = ""
) -> bool:
    """`fresh`（本轮封版基线 B）是否被 job 的基线覆盖。

    相等，或 B 是 job 基线的祖先 ⇒ 这单审的是 B 当时或之后的内容（本轮）。
    反过来（job 基线是 B 的祖先）⇒ 更早的内容，**不是本轮**（INC-20260920-AST）。

    `landed_head`：`merge_back` 成功后的主干头。合线 rebase 改 hash 后，覆盖看
    **树是否还一样**（`landed_head^{tree} == fresh^{tree}`），不看作者/提交说明——
    改树就是新内容，空提交才树不变。
    """
    if not fresh or not job_baseline:
        return False
    if fresh == job_baseline or (landed_head and fresh == landed_head):
        return True
    if landed_head:
        t_land, t_fresh = _git_tree(workspace, landed_head), _git_tree(workspace, fresh)
        if t_land and t_land == t_fresh:
            return True
    return _git_is_ancestor(workspace, fresh, job_baseline)


def _closed_job_evidence(workspace: Path, job: dict, fresh_baseline: str) -> Tuple[bool, str]:
    """本地账里的"已闭环"job 是否真有**本轮**证据（ADR-0004 §2.1.10：以 git/磁盘为准）。

    本地账是**运行态投影**（可重建、可陈旧）：它说 `collected` + `待修=0` 不算数。要接受
    必须同时满足：
      ① 报告**文件在盘上**（账里写路径 ≠ 文件存在；报告可能已被归档/删除）
      ② 报告**自身**待修=0 且有序言（`_SIGN_KEYS`）——计数从文件重算，不用账里的 counts
      ③ 报告里的 `基线` 与 job 的 `基线` 一致（记录自洽：报告就是那单的产物）
      ④ job 的基线覆盖本轮 B（`_baseline_covers`，含合线 `landed_head`）——否则这是**旧内容**的审计
    """
    from k3dge.engine import audit_report as _ar
    from k3dge.engine.process_audit import _SIGN_KEYS, _field

    rel = str(job.get("report") or "")
    if not rel:
        return False, "账里没有报告路径"
    path = workspace / rel
    if not path.is_file():
        return False, f"报告不在盘上（{rel}）"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False, f"报告不可读（{rel}）"
    missing = [k for k in _SIGN_KEYS if not _field(text, k)]
    if missing:
        return False, f"报告缺署名/来源 {missing}（{path.name}）"
    if (_field(text, "基线") or "").split()[0].strip("`") != (job.get("baseline") or ""):
        return False, f"报告里的基线≠该单基线（{path.name}）"
    if _ar._parse_audit_stats(text)["待修"] != 0:
        return False, f"报告有待修（{path.name}）"
    if not _baseline_covers(
        workspace, fresh_baseline, str(job.get("baseline") or ""),
        landed_head=str(job.get("landed_head") or ""),
    ):
        return False, (f"该单基线 {str(job.get('baseline'))[:12]} 不覆盖本轮基线 "
                       f"{str(fresh_baseline)[:12]} ⇒ 是旧内容的审计")
    return True, f"本里程碑签署报告已闭环（{rel}；待修 0）"


def _role_opt(workspace: Path, role: str, key: str, default: str) -> str:
    """读 `[roles.<role>] <key>`（缺省 ⇒ default）。工具运行参数走声明面（唯一声明源），不在腿里写死。"""
    try:
        import tomllib
    except ModuleNotFoundError:      # pragma: no cover
        import tomli as tomllib      # type: ignore

    try:
        data = tomllib.loads((workspace / ".agent" / "pipeline.toml").read_text(encoding="utf-8"))
        val = (data.get("roles", {}).get(role) or {}).get(key)
        return str(val) if val not in (None, "") else default
    except Exception:
        return default


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


def _reject_step(
    workspace: Path,
    milestone_id: str,
    code: str,
    msg: str,
    *,
    status: str = "refused",
) -> Tuple[str, str]:
    """拒绝分支单源：Rejection → [NEXT] → persist → `(status, msg + CLI 尾行)`。

    原来五处各写一遍 render+persist，任何一处漏 persist 就会让 CLI 回执与持久态
    `[NEXT]` 分叉（value-23）。非拒绝态（escalated 等）不走这里。
    """
    from k3dge.engine import nextstep

    ns = nextstep.next_for_rejection(milestone_id, gates.Rejection(code, msg))
    nextstep.persist(workspace, ns)
    return status, msg + "\n" + ns.render_cli()


def _oneshot_audit_leg(
    workspace: Path,
    milestone_id: str,
    prompt: _Prompt,
    streams: dict,
    max_verify_attempts: int,
) -> Tuple[str, str]:
    """legacy oneshot 形状：produce → 收报告 → `待修>0` 就修 → verify 二次核对。

    与棘轮腿互斥（ADR-0025）：棘轮闭环后 `streams` 为空，本函数只跑共用尾。
    """
    from k3dge.engine import audit_checklist as ac, audit_flow, nextstep
    from k3dge.engine.pipeline_runner import run_action

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
                return _reject_step(workspace, milestone_id, "audit_noop", msg)
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
                return _reject_step(
                    workspace, milestone_id, "audit_report_missing", msg, status="rejected")
            report_path, report_text = found
            if degraded:  # 降级不静默：署名是降级可接受的前提（ADR-0004 §2.1.11）
                from k3dge.engine.process_audit import _SIGN_KEYS, _field

                missing = [k for k in _SIGN_KEYS if not _field(report_text, k)]
                if missing:
                    msg = (
                        f"审计降级到 manual 但报告缺署名/来源 {missing}（{report_path.name}）——"
                        "降级不静默：署名后可记 `degraded-manual` 继续（ADR-0004 §2.1.11）。"
                    )
                    return _reject_step(
                        workspace, milestone_id, "audit_degraded_unsigned", msg)
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
            return _reject_step(
                workspace, milestone_id, "audit_open_declined", msg, status="rejected")
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


def _tool_state_dir(workspace: Path) -> str:
    """工具状态目录（外部被审仓 ⇒ 缓存的确定性路径）。单一源在 `audit_bundle.tool_state_dir`。"""
    from k3dge.engine.audit_bundle import tool_state_dir

    return str(tool_state_dir(workspace))


def _bundle_audit_leg(
    workspace: Path,
    milestone_id: str,
    prompt: _Prompt,
    fresh_baseline: str,
) -> Tuple[Optional[Tuple[str, str]], str]:
    """**bundle 审计腿**（k3dit 仓 0008 消费方）：冻结基线 → k3dit 路径入口产包 → 消费侧验+落补丁。

    与 ratchet 的区别：不做"工单步进 / 写回重试"——一次性拿到**包**（`code/ report findings
    patches manifest`），由 k3dge 自己 apply 与落账（k3dit 仓 0008 §2.9：k3dit 不接管送审方版本）。
    返回 `(early, step_status)`：`early` 非 None ⇒ 未闭环，交回 `[NEXT]`；None ⇒ 已闭环，走共用尾。
    """
    from k3dge.engine import audit_bundle as ab

    if not ab.find_k3dit(workspace):
        return _reject_step(
            workspace, milestone_id, "audit_bundle_no_k3dit",
            "审计腿声明为 bundle，但找不到 k3dit（设 K3DIT_BIN 或装到 PATH/兄弟仓）"
            "——声明面与实现面不符时**不得**静默降级成别的形状（ADR-0004 §2.1.11）。"), ""

    # 包落在**仓外**（缓存目录）：k3dit 是命令行工具，它的中间产物理应与 `git` 的对象库一样不进被审树
    #（旧位置 `<workspace>/.k3dit/bundle-*` 会在被审仓里留未跟踪目录 ⇒ 消费方 status/gate 变脏）。
    cache_root = ab.audit_cache_root()
    out = cache_root / f"{milestone_id}-{(fresh_baseline or 'head')[:12]}"
    k3dit_mode = _role_opt(workspace, "audit", "k3dit_mode", "full")
    k3dit_pins = _role_opt(workspace, "audit", "k3dit_pins", "inplace")
    k3dit_scope = _role_opt(workspace, "audit", "k3dit_scope", "")
    if k3dit_mode not in ("full", "audit-only"):
        return _reject_step(workspace, milestone_id, "audit_bad_k3dit_mode",
                            f'[roles.audit] k3dit_mode={k3dit_mode!r} 不合法（full / audit-only）'), ""
    if k3dit_pins not in ("inplace", "artifact"):
        return _reject_step(workspace, milestone_id, "audit_bad_k3dit_pins",
                            f'[roles.audit] k3dit_pins={k3dit_pins!r} 不合法（inplace / artifact）'), ""
    # scope 是**相对仓根**的范围（逗号分隔）；绝对路径或 `..` 越界一律拒绝——送审范围是"哪一块自留地"，
    # 不该由旋钮把审计带到仓外去（越界值只可能是写错，静默接受会让报告范围与声明不符）。
    scope_err = ""
    for _seg in [s for s in str(k3dit_scope).split(",") if s.strip()]:
        _s = _seg.strip()
        if os.path.isabs(_s) or any(part == ".." for part in Path(_s).parts):
            scope_err = _s
            break
    if scope_err:
        return _reject_step(workspace, milestone_id, "audit_bad_k3dit_scope",
                            f'[roles.audit] k3dit_scope={scope_err!r} 不合法（相对仓根、不得含 .. 或绝对路径）'), ""
    # 工具调用的**墙钟预算**（声明面旋钮；缺省 1h）。真跑实测：8 文件的 full 跑超过 1h 被 `_run` 掐断
    # ⇒ 整轮白烧（判读+修+核都跑完了，包没产出来）。full 模式的修/复核轮数不可预估 ⇒ 默认放宽到 2h。
    _tmo_raw = _role_opt(workspace, "audit", "k3dit_timeout", "")
    _tmo = 3600
    if str(_tmo_raw).strip():
        try:
            _tmo = int(str(_tmo_raw).strip())
            if _tmo <= 0:
                raise ValueError
        except ValueError:
            return _reject_step(workspace, milestone_id, "audit_bad_k3dit_timeout",
                                f'[roles.audit] k3dit_timeout={_tmo_raw!r} 不合法（正整数秒）'), ""
    elif k3dit_mode == "full":
        _tmo = 7200
    _salv: dict = {}      # 抢救结果（仅失败路径填）
    _salv_ok = False      # 抢救成功标记（`ran` 会被改写 ⇒ 不能靠它反推）
    _dig = ""             # 运行摘要路径
    # 落地策略（**调用方定**，用户裁定）：`closed-only`（未关项不落）/`partial`（只剔未关项那些 hunk）/
    # `all`（全落，但行上标升级 ⇒ 封板仍被挡）。声明面旋钮，非法值显式拒绝。
    landing = _role_opt(workspace, "audit", "k3dit_landing", "partial")
    if landing not in ("closed-only", "partial", "all"):
        return _reject_step(workspace, milestone_id, "audit_bad_k3dit_landing",
                            f'[roles.audit] k3dit_landing={landing!r} 不合法（closed-only / partial / all）'), ""
    ran = ab.run_path_audit(workspace, out, mode=k3dit_mode, pins=k3dit_pins, scope=k3dit_scope,
                            timeout=_tmo)
    payload = ran.get("payload") or {}
    if not ran.get("ok"):
        # **抢救**（用户裁定：超时也要出报告，不能让流程停在中间）：工具被杀时不会 write_bundle，
        # 但它账本里状态是全的 ⇒ `k3dit hall export --latest` 抢救出"未完成导出"包，再照常验收/部分落地。
        _salv = ab.salvage_bundle(workspace, out)
        _dig = ab.write_run_digest(out, stage=("salvage-ok" if _salv.get("ok") else "run-failed"),
                                   rc=ran.get("rc"), detail=(ran.get("detail") or "")[:400],
                                   salvage_rc=_salv.get("rc"), salvage_detail=_salv.get("detail", ""),
                                   tool_state_dir=_tool_state_dir(workspace))
        if not _salv.get("ok"):
            # 抢救也失败 ⇒ 拒绝，但把**可操作提示 + 运行摘要路径**给出来（摘要随包留，事后可查）
            _hint = ""
            if int(ran.get("rc") or 0) == 124:
                _st = _tool_state_dir(workspace)
                _hint = (f"\n[提示] 工具调用被墙钟掐断（timeout）。工具状态在 {_st}：其中『在办单』会占住窗"
                         f"（重跑会被『站点占位』拒）⇒ 先 `k3dit hall prune --force <job>` 释放，"
                         f"或删除该状态目录后重跑。")
            return _reject_step(workspace, milestone_id, "audit_bundle_run_failed",
                                f"k3dit 产包失败（rc={ran.get('rc')}）：{ran.get('detail') or ''}{_hint}"
                                f"\n[运行摘要] {_dig or '（未写出）'}"), ""
        # 抢救成功 ⇒ **继续**走验收/部分落地（包自带「未完成导出」横幅 + `salvage:true`）
        _salv_ok = True
        _lm = out / "manifest.json"
        try:
            ran = {"ok": True, "payload": json.loads(_lm.read_text(encoding="utf-8")),
                   "detail": "salvaged"}
        except Exception:
            return _reject_step(workspace, milestone_id, "audit_bundle_run_failed",
                                f"抢救出的包不可读（{_lm}）\n[运行摘要] {_dig or '（未写出）'}"), ""
    # 纯审计（audit-only）：    # 纯审计（audit-only）：`status=partial` 是设计（钉留树）；它**只出证据，不构成封板依据** ⇒ 落报告后
    # 以 refused 交回（带理由），不推进任何"已审"判定。full 才要求闭环。
    # **闭环判据归 k3dge**：`consume` 里的 `audit_verify.verify_bundle_local` 从 findings 自己算未关项，
    # 产出方自报的 `payload.status` 只作交叉核（不一致会被验收报出来）；不在此处读它当闸。
    audit_only = k3dit_mode == "audit-only"
    salvaged = bool(_salv_ok and _salv.get("ok"))
    _salv_note = f"（工具被掐断 ⇒ 由 `hall export` **抢救**出包；摘要 {_dig}）" if salvaged else ""

    res = ab.consume(workspace, out, expect_input=str(workspace), require_closed=not audit_only,
                     landing=landing)
    if not res.get("ok"):
        # 消费失败（脏树/补丁打不上…）**不等于这一轮没产出**：报告必须在手，否则等于白跑一轮
        _sha = (ab.land_report(workspace, milestone_id, out,
                              why=f"消费被拒 {res.get('error')}").get("commit") or "")
        return _reject_step(
            workspace, milestone_id, "audit_bundle_consume_failed",
            f"消费交付包失败（{res.get('error')}）：{res.get('detail') or ''}"
            f"；报告已落 `docs/reviews/`{('（提交 ' + _sha[:12] + '）') if _sha else '（未提交）'}，"
            f"产物包留在 {out}"), ""
    # 包里那份 12 列报告就是**审计产物**：必须落到 `docs/reviews/`，否则判定面（checklist / 触发 /
    # judged 事实）看不到它——`_find_report` 只在 docs/reviews 里找。复用既有的落地器（统一命名/表头/覆盖规则）。
    # 落报告 + 重生投影 + **一次提交**（与拒绝路、手动入口**共用同一个函数**；此前这里另写了一份）
    files = list((res.get("apply") or {}).get("files") or [])
    digest = str((res.get("digest") or "")[:12])
    jid = str((res.get("facts") or {}).get("job_id") or "")
    _esc = [str(x) for x in (res.get("escalated") or [])]
    _excl = sorted({str(x) for x in (res.get("apply") or {}).get("excluded") or []} |
                   {str(x) for x in (res.get("unclosed_files") or [])})
    landed = ab.land_report(workspace, milestone_id, out, extra_files=files,
                            why=f"job {jid or '-'} 包 {digest}",
                            excluded=_excl, escalated=_esc)
    if not landed.get("ok"):
        return _reject_step(workspace, milestone_id, f"audit_bundle_{landed.get('error', 'report').lower()}",
                            f"落报告/投影/提交失败：{landed.get('detail') or landed.get('error')} ⇒ "
                            f"产物已在工作区（未提交），请人工提交或回退后重跑"), ""
    rel_report, commit = str(landed.get("report") or ""), str(landed.get("commit") or "")
    if audit_only:
        _esc_msg = (f"\n[升级·转人工] 未关 {len(_esc)} 项：{', '.join(_esc[:8]) or '-'}"
                    f"；排除文件 {len(_excl)} 个（其修复未落）。报告「验证」列已标。") if _esc else ""
        return _reject_step(
            workspace, milestone_id, "audit_evidence_only",
            f"纯审计（`k3dit_mode = \"audit-only\"`）只出证据，不构成封板依据：报告落盘 {rel_report}，"
            f"落 {len(files)} 文件{('，提交 ' + commit[:12]) if commit else ''}。要封板请把 "
            f'`[roles.audit] k3dit_mode` 改为 "full"（判读+修+复核，待修=0）再跑。{_esc_msg}{_salv_note}'), ""
    # **部分落地**（用户裁定 乙）：未关项不再整包拒 ⇒ 落已修、把未关项所在文件排除，并**由 k3dge 的审后闸
    # 报出升级**（k3dit 里没人看得到升级；报告行只在「验证」列加注，状态列保持产出方原样）。
    _part = bool(res.get("partial"))
    msg = (f"Milestone {milestone_id}: bundle 审计腿"
           f"{'**部分落地**（未闭环）' if _part else '闭环'}"
           f"（工具 k3dit job {jid or '-'}，包 {digest}，落 {len(files)} 文件，报告 {rel_report}"
           f"{('，提交 ' + commit[:12]) if commit else ''}）。{_salv_note}")
    if _part:
        msg += (f"\n[升级·转人工] 未关 {len(_esc)} 项：{', '.join(_esc[:8]) or '-'}"
                f"；排除文件 {len(_excl)} 个（其修复未落）。报告「验证」列已标，**封板判据须为空**。")
    return None, msg


def run_audit_flow(
    workspace: Path,
    milestone_id: str,
    *,
    prompter: Optional[_Prompt] = None,
    max_verify_attempts: int = 3,
    fresh_baseline: str = "",
) -> Tuple[str, str]:
    """Independent audit entry: the merged audit module (ADR-0025) produces ONE
    12-col report (k3dit audit leg; quality is a window inside the module, not an
    independent peer). 待修==0 counts as "audited once"; verify checks that one
    report. Returns (status, message); status ∈ {audited, rejected, escalated}.
    Seal unlocks only after this closes (`run_seal_flow`).

    两种审计腿形状各归其函数：`_bundle_audit_leg`（本地命令行工具 k3dit，产包→消费，推荐）与
    `_oneshot_audit_leg`（显式声明的外部 produce/verify 步，给真正的对等 harness）；本函数只做前置事实 + 路由。
    （棘轮形状已退休，声明它会被显式拒绝。）
    """
    from k3dge.engine import audit_checklist as ac
    from k3dge.engine import gates as _gates

    prompt = prompter or _Prompt.default()
    # Initiating an audit resets the condition checklist (fresh verify budget +
    # started_at stamp), whether triggered manually (`milestone audit`) or via a hook.
    ac.reset_for_audit(workspace, milestone_id)

    # 本轮基线 B（审计前取一次）：既是 durable 记录（trailer / tag）的取值，也是"本地账里那单
    # 是不是本轮审计"的判据（陈旧单不得充闭环）。
    if not fresh_baseline:
        from k3dge.engine.seal import head_commit

        fresh_baseline = head_commit(workspace)

    _mode = _audit_mode(workspace)
    if _mode == "bundle":
        # bundle 审计腿：k3dit 是**本地命令行工具**（与 `git` 同层）⇒ 按 argv 调用、读包、落树、落账。
        # 闭环后**落到共用尾**（verify 步 + nextstep persist），与 oneshot 腿同形；未闭环则提前返回。
        early, _bmsg = _bundle_audit_leg(workspace, milestone_id, prompt, fresh_baseline)
        if early is not None:
            return early
    elif _mode == "ratchet":
        # 棘轮形状已退休（2026-09-26）：它要的对端 verb（submit/collect/present/status）随 k3dit 的
        # MCP 服务端面一并消失。**显式拒绝**而不是静默换成别的形状（ADR-0004 §2.1.11）。
        return _reject_step(
            workspace, milestone_id, "audit_ratchet_retired",
            '审计腿声明为 `mode = "ratchet"`，但棘轮形状已退休：改用 `mode = "bundle"`（本地工具 k3dit，'
            '推荐）或 `mode = "oneshot"`（显式声明外部 produce/verify 步）。')

    ratchet = False
    # 单报告（ADR-0025 合并审计模块）：一轮 = 一份 12 列；quality 是模块内窗口，
    # 不再是独立 peer/report。ratchet 模式下审计腿已由步进器闭环，streams 空。
    # 外部步读**声明面**（gates [checks.audit].stages_produce/stages_verify），
    # 不再硬编码 action ref —— 原 pipeline.toml 的 [pipelines.*] 只有校验、无执行者。
    _produce = _gates.stages(workspace, "audit", "produce")
    _verify = _gates.stages(workspace, "audit", "verify")
    streams = {"audit": (_produce[0] if _produce else "", _verify[0] if _verify else "")}
    if not _produce:
        # 声明面留空 ⇒ **一次都没跑**（不是"无需审计"）：与 skip 同族，不得当已审——
        # 否则只要仓里有一份旧报告就能判闭环（本会话实测过这个配置层的洞）。
        msg = (
            "审计未声明：`[checks.audit].stages_produce` 为空 ⇒ 没有可跑的审计步；"
            "声明面没给 = 一次都没跑，不得当已审（ADR-0004 §2.1.9/§2.1.11）。"
            "要么在 `.agent/pipeline.toml` 声明审计步，要么不要 seal。"
        )
        return _reject_step(workspace, milestone_id, "audit_noop", msg)

    return _oneshot_audit_leg(workspace, milestone_id, prompt, streams, max_verify_attempts)
