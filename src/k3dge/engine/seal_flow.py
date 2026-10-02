"""封板流程状态机（`run_seal_flow`）+ align 收尾 helper。

Extracted from `engine/milestone.py` (A-1 第十三块).
`nextstep`/`audit_closed`/`prune_finished`/`get_version` imported lazily (avoid cycles).
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path
from typing import Optional, Tuple

from k3dge.engine import gates
from k3dge.engine.align import _ALIGN_STUB_MARKER, run_milestone_alignment
from k3dge.engine.milestone_files import _has_milestone_token
from k3dge.engine.prompt import Prompt as _Prompt
from k3dge.engine import seal as seal_mod
from k3dge.engine.seal import seal_milestone, seal_preconditions_error


def _align_review_paths(workspace: Path, milestone_id: str) -> list:
    """该里程碑生成的 align 桩文件（**全部**）。

    桩闸（`seal_preconditions_error` → `_seal_review_gate`）扫的是 `docs/reviews/` 下
    **所有** `-align.md`，只要有一个还带 stub 就判红；这里只回字典序第一个 ⇒ 第二个桩
    永远清不掉，封板在前置闸处死循环（ocr-309）。
    """
    reviews = workspace / "docs" / "reviews"
    if not reviews.is_dir():
        return []
    return [
        f for f in sorted(reviews.iterdir())
        if f.is_file() and f.suffix == ".md" and "-align.md" in f.name
        and _has_milestone_token(f.name, milestone_id)
    ]


def _strip_align_stub(workspace: Path, milestone_id: str) -> None:
    """Mark the align scaffold as filled so the seal gate (align-stub check) passes.

    The mandatory audit now *is* the real verification; the align scaffold is a
    structural placeholder only.
    """
    for p in _align_review_paths(workspace, milestone_id):
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _ALIGN_STUB_MARKER not in text:
            continue
        try:                     # 读保护过、写裸奔 ⇒ OSError 冒穿 run_phase（无异常兜底）→ seal 崩（ocr-310）
            p.write_text(text.replace(_ALIGN_STUB_MARKER, "").strip() + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"[seal_flow] WARN: 清 align 桩写不回 {p.name}（{type(exc).__name__}: {exc}）"
                  "⇒ 桩闸仍会红", file=sys.stderr)


def _report_seat(workspace: Path, milestone_id: str) -> str:
    """审计席位（封版提交 trailer 的 `Audit-seat`）：取自落盘报告的 `审计人`。

    报告缺席或没署名 ⇒ 空串（trailer 记 `-`）。不猜、不从本地 job 账里抄——本地账是运行态。
    """
    try:
        from k3dge.engine.audit_report import _find_report
        from k3dge.engine.process_audit import _field

        found = _find_report(workspace, milestone_id, "audit")
        return _field(found[1], "审计人") if found else ""
    except Exception:
        return ""


def _boundary_tag_before(workspace: Path, milestone_id: str) -> Optional[str]:
    """最近一个**别人**的边界 tag（`M<n>`；排当前里程碑自己）。无则空串，git 失败则 None。

    git 失败回空串 ⇒ 调用方当"首个里程碑"跳过对账，真失败变假成功（ocr2-075）。必须区分。
    """
    from k3dge.engine import seal as _seal
    from k3dge.engine.changelog import _tag_number

    best = ""
    rc, out = _seal._git(workspace, "tag", "--list", "M*")
    if rc != 0:
        return None
    for name in out.splitlines():
        name = name.strip()
        if not name or name == milestone_id:
            continue
        # 前缀 `M*` 粗筛配上"取最后一个数字段"的排序键 ⇒ `Milestone-2024-09-29`(29)、`MAJOR-1.0`
        # 会盖过真正的 M10/M0，边界选错后 diff 区间与 CHANGELOG 全漂（ocr-311）
        if not re.fullmatch(r"M\d+", name):
            continue
        if _tag_number(name) > _tag_number(best or "M0"):
            best = name
    return best


def _architecture_staleness(workspace: Path, milestone_id: str) -> str:
    """架构文档自上一个边界以来的新鲜度（人读陈述；不判定“该不该改”）。

    背景（2026-09-21 盘点）：`docs/architecture/overview.md` 的更新一直只写在收摊清单的
    advisory 里，从来没有“什么时候该看它”的事实 ⇒ 跨里程碑静默漂移。这里把事实算出来，
    让 seal 那一刻**必须看见**（仍不阻断：写得好不好归人/k3dit，见 `AGENTS.md` §12）。
    """
    from k3dge.engine import seal as _seal

    tag = _boundary_tag_before(workspace, milestone_id)
    if tag is None:
        return "（列边界 tag 时 git 失败，未能对账架构文档；非首个里程碑，请人工核对）"
    if not tag:
        return "无上一个边界 tag（首个里程碑）：架构文档按现状保留，无需对账"
    rc, out = _seal._git(workspace, "diff", "--name-only", f"{tag}..HEAD")
    if rc != 0:
        return f"（读 {tag}..HEAD 失败，未能对账架构文档）"
    files = [f for f in out.splitlines() if f.strip()]
    docs = ("docs/architecture/overview.md", "docs/architecture/encyclopedia.md")
    code = [f for f in files if f.startswith(("src/", "docs/specs/"))]
    touched = [d for d in docs if d in files]
    missing = [d for d in docs if d not in files]
    if not code:
        return f"✅ 自 `{tag}` 以来 `src/`/`docs/specs/` 无改动 ⇒ 设计文档无需对账"
    if not missing:
        return f"✅ `{'`/`'.join(docs)}` 在 `{tag}..HEAD` 区间内都已更新（{len(code)} 个 src/spec 文件也变过）"
    if touched:
        return (f"⚠️ `{'`/`'.join(missing)}` 自 `{tag}` 以来**未更新**（`{'`/`'.join(touched)}` 已更新），"
                f"而区间内 `src/`/`docs/specs/` 有 {len(code)} 个文件改动 ⇒ 收摊时对齐（无变化就注明“无需改”）")
    return (
        f"⚠️ `{'`/`'.join(missing)}` 自 `{tag}` 以来**未更新**（两件都没动），而区间内 `src/`/`docs/specs/` 有 "
        f"{len(code)} 个文件改动 ⇒ 本里程碑收摊时对齐（无实际变化就在清单里注明“无需改”）"
    )


def _refresh_projections(workspace: Path, failures: Optional[list] = None) -> list:
    """相位 3 的**纯投影**刷新：`docs/generated/{api,domains,docs-index}.md|json`、符号索引、README 自动块。

    返回**实际变化**的相对路径（人读；没变就不列）。全部幂等、零判断；任一件失败 ⇒ 跳过该件
    （投影坏不得拦住封板收尾，但会写进事件面）。
    """
    changed: list = []
    failures = failures if failures is not None else []

    def _track(path: Path, fn) -> None:
        # 读前后字节也必须**逐件**兜异常：某件不可读不得穿透到外层 try 而中止其余投影（ocr2-312）。
        try:
            before = path.read_bytes() if path.is_file() else None
        except Exception as exc:
            failures.append(f"{path.name}: {type(exc).__name__}: {exc}")
            print(f"[seal_flow] WARN: 投影读前失败 {path}（{type(exc).__name__}: {exc}）",
                  file=sys.stderr)
            return
        try:
            fn()
        except Exception as exc:
            # 吞掉具体错误 ⇒ "投影失败"被渲染成"无变化/已与事实一致"（ocr-312/314）
            failures.append(f"{path.name}: {type(exc).__name__}: {exc}")
            print(f"[seal_flow] WARN: 投影刷新失败 {path}（{type(exc).__name__}: {exc}）",
                  file=sys.stderr)
            return
        try:
            after = path.read_bytes() if path.is_file() else None
        except Exception as exc:
            failures.append(f"{path.name}: {type(exc).__name__}: {exc}")
            print(f"[seal_flow] WARN: 投影读后失败 {path}（{type(exc).__name__}: {exc}）",
                  file=sys.stderr)
            return
        if after != before and after is not None:
            try:
                changed.append(str(path.relative_to(workspace)))
            except ValueError:
                pass

    try:
        from k3dge.engine.doc_catalog import INDEX_REL, write_docs_index
        from k3dge.engine.generated_docs import render_manual_docs_content, render_readme_layout
        from k3dge.engine.manifest import Manifest
        from k3dge.engine.search import index_path, write_symbol_index

        try:
            manifest = Manifest.load(workspace)
        except Exception as exc:      # 外层曾经把 Manifest 读坏也一起静默跳过全部投影
            failures.append(f"manifest: {type(exc).__name__}: {exc}")
            print(f"[seal_flow] WARN: manifest 读不出 ⇒ 本轮不刷投影（{exc}）", file=sys.stderr)
            return changed
        for path, content in render_manual_docs_content(workspace, manifest).items():
            _track(path, lambda path=path, content=content: (
                path.parent.mkdir(parents=True, exist_ok=True),
                path.write_text(content, encoding="utf-8"),
            ))
        _track(workspace / "README.md", lambda: render_readme_layout(workspace, manifest))
        _track(workspace / INDEX_REL, lambda: write_docs_index(workspace))
        _track(index_path(workspace), lambda: write_symbol_index(workspace))
    except Exception as exc:  # pragma: no cover - import/结构异常
        failures.append(f"projections: {type(exc).__name__}: {exc}")
        print(f"[seal_flow] WARN: 投影刷新整体失败（{type(exc).__name__}: {exc}）", file=sys.stderr)
    return changed


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

        # 相位序：version_bump 在本函数之前 ⇒ 记当前终版，不要再 _next_version（M10 写成 0.1.13、实为 0.1.12）。
        sealed_version = get_version(workspace) or "?"
    except Exception:
        sealed_version = "?"
    reviews = workspace / "docs" / "reviews"
    report_files = list(reviews.glob(f"*-{milestone_id}-*.md"))
    archived = reviews / "archive" / milestone_id
    if archived.is_dir():
        report_files.extend(archived.glob(f"*-{milestone_id}-*.md"))
    audit_reports = ",".join(
        sorted({f.name for f in report_files if f.name.endswith(("-audit.md", "-quality.md"))})
    ) or "-"
    arch_fact = _architecture_staleness(workspace, milestone_id)
    # 幂等重入：同一天重跑不得把人已在 `## 1..4` 勾过的清单擦成空桩；跨天重跑也不该另起一份
    # 把旧的变成孤儿 ⇒ 按里程碑找**已有**清单复用（ocr-313）
    existing = sorted(reviews.glob(f"*-{milestone_id}-closure.md"))
    p = existing[0] if existing else reviews / f"{today}-{milestone_id}-closure.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = (
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
                f"- [ ] 设计文档（`overview.md` / `encyclopedia.md`）对齐到已封板的现实 —— {arch_fact}",
                "- [ ] 相关 ADR 标注 supersedes / 现行范围",
                "",
                "## 4. 提交里程碑",
                "- [ ] 封版提交已含归档/收摊清单；人补的设计文档另提",
                "",
                "## 5. 决策轨迹（TSV：show-me-your-work 洁净室移植——ts/phase/decision/why/evidence/result，evidence=指针非散文）",
                "ts\tphase\tdecision\twhy\tevidence\tresult",
                f"{today}\tseal\tseal {milestone_id}\t审计闭环（合并审计模块单份 12 列，待修=0）\t{audit_reports}\t{sealed_version}",
                "",
            ]
        )
    )
    if p.is_file():
        try:
            keep = bool(p.read_text(encoding="utf-8").strip())
        except (OSError, UnicodeDecodeError) as exc:
            # 读不出 ≠ 空：不能把可能的人改内容当空桩覆盖掉（ocr2-313）。
            print(f"[seal_flow] WARN: 收摊清单 {p} 读不出（{type(exc).__name__}: {exc}）"
                  "⇒ 保留原文件，不覆盖", file=sys.stderr)
            return p
        if keep:
            return p          # 幂等重入：人勾过的清单不擦（旧实现无条件 write_text 覆盖）
    p.write_text(body + "\n", encoding="utf-8")
    return p


def _milestone_already_sealed(workspace: Path, milestone_id: str) -> bool:
    """本里程碑**已封过**没有——判据只认 git 事实（边界 tag），不读本地账（ADR-0004 §2.1.10）。

    读不出证据时按"未封"处理并出声：宁可照常提版（可见、可回滚），也不静默跳过相位 3①
    ——跳过会让操作者以为版本已动，而 tag/记录其实不在。
    """
    try:
        from k3dge.engine import audit_flow

        return bool(audit_flow.audit_evidence(workspace, milestone_id).get("tag"))
    except Exception as exc:
        print(f"[seal_flow] WARN: 封版证据读不出（{type(exc).__name__}: {exc}）⇒ 本轮按未封处理",
              file=sys.stderr)
        return False


def run_seal_flow(
    workspace: Path,
    milestone_id: str,
    *,
    prompter: Optional[_Prompt] = None,
    skip_enter_prompt: bool = False,
    no_version_bump: bool = False,
) -> Tuple[str, str]:
    """封板＝三相位（ADR-0004 §2.1.9）：**预审 → 审计 → 审核后自动**。

    唯一入口：人发起 `seal` 就是在宣布"要收这一章"；幂等重入（预审失败可修完再 seal）。
    审计是封板的**主体**（相位 2，本流程自己跑，不靠外部 hook 先跑一遍）；审计正常返回
    status 闭集＝{sealed, seal_declined, rejected, audit_open, escalated}：审计在办/升级态**原样返回**（不是 docstring 漏掉的野值），只有 `sealed` 代表收章完成（462）
    """
    from k3dge.engine import nextstep
    from k3dge.engine.seal import render_checklist, unmet_seal_preconditions

    prompt = prompter or _Prompt.default()

    # 相位 1·预审（进审计的**门槛**）：形式闸先过——不进审计就不必审（ADR-0004 §2.1.9）。
    # `align_pass` 虽在清单里，却由本单元第一个动作 `full_matrix` 满足
    # （`[nodes.full_matrix].satisfies`）⇒ `unmet_*` 已按声明排除 auto 项，此处只看"需人先办"。
    unmet = unmet_seal_preconditions(workspace, milestone_id)
    if unmet:
        gid, gmsg = unmet[0]
        rej = gates.Rejection(gid, gmsg)
        _ns = nextstep.next_for_rejection(milestone_id, rej)
        nextstep.persist(workspace, _ns)
        # 同 `_archive` 的拒绝路径：给**全量清单**（否则操作者只看到第一项，补完再跑又发现下一项）
        return "rejected", str(rej) + "\n" + render_checklist(workspace, milestone_id) + "\n" + _ns.render_cli()

    # enter-seal prompt — NO countdown; N = keep milestone open. Skipped with --yes.
    # 文案单源：STATE_OPTIONS["seal_ready"].question（与 [NEXT] 的 fact 同一判定的两个投影）；通道行为（default_yes）留在此处。
    if not skip_enter_prompt and not prompt.ask(
        nextstep.question_text("seal_ready", milestone_id), default_yes=False
    ):
        msg = f"Milestone {milestone_id}: seal declined — 不封，里程碑继续挂着。"
        _ns = nextstep.NextStep.from_state("seal_declined", milestone_id)
        nextstep.persist(workspace, _ns)
        return "seal_declined", msg + "\n" + _ns.render_cli()

    # 动作：读「硬闸契约」`[checks.seal].actions`（ADR-0001 §2 第 8 条）——执行器按声明跑；
    # 未实现的 id 视为配置错（拒绝，不让声明空转）。
    from k3dge.engine import nodes

    def _full_matrix(_ctx):
        ok, amsg, _ = run_milestone_alignment(workspace, milestone_id)
        if not ok:
            return False, amsg
        _strip_align_stub(workspace, milestone_id)
        return True, ""

    def _audit(ctx):
        """相位 2：**审计是封板的主体**（ADR-0004 §2.1.9）。

        只在闭集里的 `closed` / `degraded-manual` 能过（§2.1.11）——`skip`/空转会在
        `run_audit_flow` 里被拦成 `refused`。基线 B 在审计**之前**取（审哪版封哪版），
        席位取自落盘报告；两者都进相位 3 的封版提交 trailer。
        """
        from k3dge.engine.audit_flow import SEALABLE_AUDIT_RESULTS, audit_result_of
        from k3dge.engine.milestone_audit import run_audit_flow

        baseline = seal_mod.head_commit(workspace)  # B：审计输入标识（git hash，不用 job id）
        status, amsg = run_audit_flow(workspace, milestone_id, prompter=prompt)
        result = audit_result_of(status)
        ctx["audit_status"] = status
        if result not in SEALABLE_AUDIT_RESULTS:
            return False, gates.Rejection(
                "audit_noop",
                f"审计未正常返回（status={status}，result={result}）：封板停下。\n{amsg}",
            )
        ctx["audit_baseline"] = baseline
        ctx["audit_result"] = result
        ctx["audit_seat"] = _report_seat(workspace, milestone_id)
        return True, f"\n  审计: {result}（{status}；基线 {baseline[:12]}）"

    def _archive(_ctx):
        err = seal_preconditions_error(workspace, milestone_id)
        if err:
            return False, err
        return seal_milestone(workspace, milestone_id)

    def _version_bump(_ctx):
        """相位 3①：**版号在审计正常返回后前进**（ADR-0004 §2.1.9/§2.1.11），不管有没有报告。

        失败不中断（ADR-0004 §2.3 失败语义：seal 后 bump 失败不回滚已归档 tasks，只告警）。
        `--no-version-bump` 是显式逃生口（不动版本文件，其余照旧）。
        """
        if no_version_bump:
            return True, "\n  版本: 跳过（--no-version-bump）"
        if _milestone_already_sealed(workspace, milestone_id):
            # 幂等重入守卫（本流程明写支持"预审失败可修完再 seal"）：已立边界 tag ⇒ 记录面已在，
            # 重跑**不得再推一格版号**（旧实现第二次 seal 会静默二次 patch-bump + 再写 CHANGELOG；
            # 09-28 审计 code-7，与 ocr-443「kind/on_rerun 未被执行器强制」同族）
            return True, f"\n  版本: 跳过（{milestone_id} 已封过：边界 tag 已在，重入不重复提版）"
        # 提版成功但立 tag 失败 ⇒ HEAD 是封版提交却无边界 tag：重跑再提版会 double-bump（ocr2-076）。
        # 认出"上一轮的封版提交"就跳过提版，直接去立 tag（`_seal_record` 会处理）。
        try:
            from k3dge.engine import seal as _seal_mod

            _rc, _head_msg = _seal_mod._git(workspace, "log", "-1", "--format=%s")
            if _rc == 0 and _head_msg.strip().startswith(f"chore(seal): seal milestone {milestone_id}"):
                return True, (f"\n  版本: 跳过（HEAD 已是 {milestone_id} 的封版提交但无边界 tag："
                               f"上一轮提版成功立 tag 失败，重入不重复提版）")
        except Exception:
            pass
        try:
            from k3dge.engine.changelog import build_notes_from_range
            from k3dge.engine.version import append_changelog, bump_version, consume_unreleased

            # CHANGELOG 由**提交区间**生成（ADR-0004 §2.1.12）：上一里程碑边界 tag .. HEAD 的
            # 非机械提交，类型取 conventional 前缀。首个里程碑（无边界 tag）⇒ 回落
            # Unreleased 累积（历史遗留路径）+ 通用行，不假装有区间。
            notes, uncovered = build_notes_from_range(workspace)
            if not notes:
                notes = consume_unreleased(workspace) or f"Seal milestone {milestone_id}."
            new_v = bump_version(workspace, part="patch")
            append_changelog(workspace, new_v, notes=notes)
            gap = f"；{len(uncovered)} 条提交无 conventional 前缀（未成条目）" if uncovered else ""
            return True, f"\n  版本: {new_v}{gap}"
        except Exception as exc:  # 告警而非静默：版本一半的状态必须可见
            return True, f"\n  版本: bump 失败（{str(exc)[:110]}）——已归档内容不回滚，人工确认"

    def _seal_record(ctx):
        """相位 3②：**封版提交 + 边界 tag**（ADR-0004 §2.1.9/§2.1.10 的 durable 面）。

        记录挂在**必然发生的这次提交**上（审计常常零提交 ⇒ 挂在"审计的提交"上没有载体），
        tag 指向审计基线 B（审哪版封哪版）。
        """
        ok, rmsg = seal_mod.seal_record(
            workspace, milestone_id,
            baseline=str(ctx.get("audit_baseline") or ""),
            seat=str(ctx.get("audit_seat") or ""),
            result=str(ctx.get("audit_result") or ""),
        )
        if not ok:
            return False, gates.Rejection("seal_record_failed", rmsg)
        return True, "\n  记录: " + rmsg

    def _closure_note(_ctx):
        # 先刷**纯投影**（docs/generated/* + README 自动块 + 符号索引），再写清单 ⇒ 刷出来的内容
        # 落进随后的封版提交。**不跑整条 sync**：spec 接口块/契约哈希与 ADR reconcile 是**事实源写**，
        # 在审计之后动它们等于改审计看过的内容（ADR-0004 §2.1.9「审哪版封哪版」）。
        proj_failures: list = []
        refreshed = _refresh_projections(workspace, proj_failures)
        p = _write_closure_note(workspace, milestone_id)
        if proj_failures:
            note = f"\n  派生件: ⚠️ {len(proj_failures)} 件投影刷新失败（{'；'.join(proj_failures[:3])}）"
        else:
            note = f"\n  派生件: {'、'.join(refreshed) if refreshed else '已与事实一致'}"
        # 架构文档新鲜度：清单里已写具体事实，这里再投影一次到 seal 输出（同一判定，两处显示）
        return True, (note
                      + f"\n  收摊清单: {p.relative_to(workspace)}"
                      + f"\n  架构文档: {_architecture_staleness(workspace, milestone_id)}")

    def _prune(_ctx):
        try:  # end-flow 清理钩子：派生件（worktree/已并入的审计线）收口即删；史在主干
            from k3dge.engine.audit_flow import prune_finished

            pr = prune_finished(workspace)
            if pr.get("pruned"):
                return True, f"\n  审计派生件清理: {pr['pruned']} 组"
        except Exception as exc:      # 清理失败不该阻断封板，但**必须可见**（不再静默 pass，ocr-047）
            return True, f"\n  审计派生件清理: 跳过（{type(exc).__name__}: {exc}）"
        return True, ""

    registry = {"full_matrix": _full_matrix, "audit": _audit, "archive": _archive,
                "version_bump": _version_bump, "seal_record": _seal_record,
                "closure_note": _closure_note, "prune": _prune}
    ctx = {"workspace": workspace, "milestone_id": milestone_id}
    ok, out = nodes.run_phase(workspace, "seal", "actions", registry, ctx)
    if not ok:
        inflight = ctx.get("audit_status")
        if inflight in ("audit_open", "escalated"):
            # run_audit_flow 已 persist 在办态；再 persist rejected 会双 [NEXT]（M10 真跑）。
            from k3dge.engine.seal import render_checklist

            return inflight, str(out) + "\n" + render_checklist(workspace, milestone_id)
        rej = gates.rejection(out, "unknown_action_id")
        _ns = nextstep.next_for_rejection(milestone_id, rej)
        nextstep.persist(workspace, _ns)
        from k3dge.engine.seal import render_checklist

        return "rejected", str(rej) + "\n" + render_checklist(workspace, milestone_id) + "\n" + _ns.render_cli()
    msg = str(out)
    if ctx.get("audit_baseline"):
        msg += (f"\n  边界: tag {milestone_id} = {str(ctx['audit_baseline'])[:12]}"
                f"（审哪版封哪版；之后的改动归下一个里程碑，见 ADR-0004 §2.1.9）")
    from k3dge.engine import events
    events.emit(workspace, "sealed", milestone=milestone_id,
                audit_result=ctx.get("audit_result"))
    _ns = nextstep.NextStep.from_state("sealed", milestone_id)
    nextstep.persist(workspace, _ns)
    return "sealed", msg + "\n" + _ns.render_cli()
