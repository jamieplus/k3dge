"""Two-state audit orchestration — peer contract §1 (submit → 协议外等待 → collect).

设计纪律（规则 08）：
- k3dge 只认角色 `audit`（`[roles.audit] bind` 决定实现），代码路径上不出现具体 harness 名；
- 等待不占协议：`job_id` 落编排状态（`.agent/audit_jobs.json`），何时 collect 由外层决定；
- k3dge 只验信封与形式（kind / provenance.baseline / 12 列计数），机械落盘对端字节，不补内容；
- 失败按契约错误码分类透传（报原因，不探内部）；
- `STATE_REL`（`.agent/audit_jobs.json`）是**运行态投影**（ADR-0004 §2.1.10）：本地、
  可重建、**不作判据**——判据只认 git 事实（`audit_evidence()`：边界 tag + 封版提交 trailer），
  两者冲突以 git 为准。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

# 两态 verb 移除后这些导入/常量已无引用（ocr-397）：`datetime`、`run_action`、
# `_REPORT_HEADER_TOKEN`（连带只服务它的 `report_table` 导入）——表格口径单源在
# `report_table.count_statuses`，由 `audit_report._parse_audit_stats` 委托。

#: 审计单编排状态的运行态投影（k3dge 自己的事实；`.agent/audit_jobs.json`）。
STATE_REL = ".agent/audit_jobs.json"

#: 审计结果的**闭集**（ADR-0004 §2.1.11）。唯一源：CLI / MCP / seal / 封版提交 trailer
#: 都读这里，不得各自写字符串。前两个允许推进版号，后两个不许。
AUDIT_RESULTS = ("closed", "degraded-manual", "escalated", "refused")
SEALABLE_AUDIT_RESULTS = ("closed", "degraded-manual")

#: 它们表示"审计还没正常返回"，自然不推进版号。
_STATUS_RESULTS = {
    "audited": "closed",
    "audited_degraded": "degraded-manual",
    "escalated": "escalated",
    "rejected": "refused",
    "refused": "refused",
}


def audit_call_result(produced) -> str:
    """一跳传输的结果 → `AUDIT_RESULTS` 里的一档（ADR-0004 §2.1.11）。

    先判"这一跳是否真跑过"，再谈报告在不在——否则仓里一份旧报告就能把"什么都没跑"
    兜成闭环（本会话 M10 实测过这个洞）。`skip` 与 `ok=False` 一律 `refused`。

    `degraded-manual` 判**事实**不判位置（🅰2）：`provider == "manual"` 一律算——不管它是
    链里的降级位还是首选位。理由：`_run_manual` 自己声明产出"NOT an independent audit"
    （ADR-0006 §2.4），"没有独立透镜看过这版"是同一个事实；只看 `downgrades` 会把
    "manual 排第一位"变成绕开署名要求的路（且 trailer 会记成 `closed`＝高估记录）。
    """
    if not getattr(produced, "ok", False) or getattr(produced, "skipped", False):
        return "refused"
    if getattr(produced, "provider", None) == "manual" or getattr(produced, "downgrades", None):
        return "degraded-manual"
    return "closed"


def audit_result_of(status: str) -> Optional[str]:
    """审计流程状态 → 闭集值；in-flight（尚未正常返回）⇒ None。"""
    return _STATUS_RESULTS.get(status)


def audit_evidence(workspace: Path, milestone_id: str) -> dict:
    """审计的 **durable 证据**（判据只认这些）：边界 tag + 封版提交 trailer。

    与本地账（`.agent/audit_jobs.json` / `.agent/audit_checklist.json`）的关系是
    **写源/投影**（ADR-0004 §2.1.10）：本地账可重建、可删，**不作判据**；两者冲突
    以本函数为准（例：job.state=`collected` 但仓里无 tag/trailer ⇒ 判"未封"）。

    返回 `{"tag": <sha 或 "">, "trailers": {...}, "sealed": bool}`；非 git 仓 ⇒ 全空/False。
    """
    import subprocess

    from k3dge.engine.seal import SEAL_TRAILER_KEYS

    def _run(*args: str):
        try:
            return subprocess.run(["git", "-C", str(workspace), *args], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            return None

    # "仓里没有封版证据"与"证据读不出来（git 故障）"必须分开（ocr-045）：后者给 error 字段，
    # 让调用方显示"无法判定"而不是假阴性的"未封"。
    gd = _run("rev-parse", "--git-dir")
    if gd is None or gd.returncode != 0:
        return {"tag": "", "trailers": {}, "sealed": False,
                "error": "git 不可用" if gd is None else (gd.stderr or "not a git repository").strip()}
    tag = ""
    err = ""
    rv = _run("rev-parse", "--verify", "--quiet", f"refs/tags/{milestone_id}^{{commit}}")
    if rv is not None and rv.returncode == 0:
        tag = rv.stdout.strip()
    elif rv is None:
        err = "git 不可用（tag 读不出）"
    elif not (rv.returncode == 1 and not (rv.stderr or "").strip()):
        # `--verify --quiet` 下"tag 不存在"是 rc=1 且无 stderr；其余失败（坏 ref/对象缺失/pack 损坏）
        # 是"读不出来"，必须报 error 而不是"未封"（ocr2-206）。
        err = f"tag 读不出（git rev-parse rc={rv.returncode}）：{(rv.stderr or '').strip()[:160]}"
    trailers: dict = {}
    if tag:
        # **因果绑定 + 有界**：封版提交必在基线 tag 之后 ⇒ 只在 `tag..HEAD` 找带 trailer 的提交，
        # 不再全历史扫描（ocr-046；旧行为会把无关历史线上带同名 trailer 的提交判成本轮封版）。
        lg = _run("log", f"{tag}..HEAD", "--format=%H%x1f%(trailers)%x1e")
        if lg is not None and lg.returncode == 0:
            for rec in lg.stdout.split("\x1e"):
                rec = rec.strip("\n")
                if not rec:
                    continue
                _sha, _, body = rec.partition("\x1f")
                cand = _parse_trailers(body)
                if cand.get("seal-milestone") == milestone_id:
                    trailers = cand
                    break
        elif not err:
            err = ("提交 trailer 读不出"
                   f"（git log rc={getattr(lg, 'returncode', '?')}）：{(getattr(lg, 'stderr', '') or '').strip()[:160]}"
                   if lg is not None else "git 不可用（提交 trailer 读不出）")
        if not trailers:
            # 第二载体：tag 注解正文（**零改动封版**没有提交可挂 ⇒ 记录只在注解里）
            rf = _run("for-each-ref", "--format=%(contents)", f"refs/tags/{milestone_id}")
            if rf is not None and rf.returncode == 0:
                cand2 = _parse_trailers(rf.stdout)
                # 与提交 trailer 路径同闸：`seal-milestone` 必须等于本轮（ocr2-207），
                # 否则别的轮次的注解会被算成本轮封版。
                if cand2.get("seal-milestone") == milestone_id:
                    trailers = cand2
                # 注解里是别轮的四键 ⇒ 不是本轮证据，当"无证据"（sealed=False），不报错。
            elif not err:
                err = ("tag 注解读不出"
                       f"（git for-each-ref rc={getattr(rf, 'returncode', '?')}）"
                       if rf is not None else "git 不可用（tag 注解读不出）")
    def _real(v: object) -> bool:
        # `seal.format_seal_trailers` 对缺失字段写 `-` ⇒ 四键齐全但全是占位的残缺记录也"键存在"
        # （本函数的定位恰恰是判据，必须核**值**，ocr-210）。
        s = str(v or "").strip()
        return bool(s) and s != "-"

    sealed = bool(tag) and set(trailers) >= set(SEAL_TRAILER_KEYS) and all(
        _real(trailers.get(k)) for k in SEAL_TRAILER_KEYS)
    base = str(trailers.get("audit-baseline") or "").strip()
    if sealed and base and tag:
        from k3dge.engine.seal import _same_commit

        if not _same_commit(tag, base):
            sealed = False      # trailer 的基线与边界 tag 不同指 ⇒ 记录与 tag 不是一对（因果未绑定）
    out: dict = {"tag": tag, "trailers": trailers, "sealed": sealed}
    if err:
        out["error"] = err
    return out


def _parse_trailers(text: str) -> dict:
    """薄委托 `seal.parse_seal_trailers`（记录格式的写源在那里，避免两处解析）。"""
    from k3dge.engine.seal import parse_seal_trailers

    return parse_seal_trailers(text)


# ---------- 两态入口 ----------
# 原 `_count_status` 已随两态 verb 退休（唯一消费者 `collect_audit` 不在；口径单源
# `report_table.count_statuses`，经 `audit_report._parse_audit_stats` 暴露）（ocr-398）



def prune_finished(workspace: Path) -> Dict[str, object]:
    """收口清理：删**已终态**审计单的派生件（worktree + 已并入主干的审计线分支）。

    源＝`STATE_REL`（`.agent/audit_jobs.json`，运行态投影，可重建）；史在主干，删的只是场地。
    返回 `{"pruned": n}`（有清理动作的单数）。**恢复：** `seal_flow._prune` 此前 import 本名
    但本模块已不再导出 ⇒ 每轮封版的清理静默空转（ocr-047）。
    """
    from k3dge.engine import worktree

    try:
        raw = json.loads((workspace / STATE_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"pruned": 0}
    # STATE_REL 是运行态投影（可被手改/半写）：顶层非对象 ⇒ 当"无单可清"，不崩（ocr2-209）。
    if not isinstance(raw, dict):
        return {"pruned": 0}
    jobs = raw.get("jobs") or []
    if not isinstance(jobs, list):
        return {"pruned": 0}
    terminal = {"collected", "done", "failed", "retired", "closed", "merged"}
    pruned = 0
    for j in jobs:
        # 元素形状同样不可信：坏元素跳过，不终止整个清理循环（ocr2-210）。
        if not isinstance(j, dict):
            continue
        jid = str(j.get("job_id") or "")
        if not jid or str(j.get("state") or "") not in terminal:
            continue
        try:
            if worktree.prune(workspace, jid).get("removed"):
                pruned += 1
        except Exception:      # 单只清理失败不连坐其余单
            continue
    return {"pruned": pruned}
