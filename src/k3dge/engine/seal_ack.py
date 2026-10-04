"""审计确认（硬闸，主观）+ 封板增量（ADR-0004 §2.1.14）。

- 确认记 `.agent/seal_ack.json`（运行态投影，gitignored）：`{milestone: {baseline, confirmed_at}}`。
  丢了大不了再提醒一次；不防伪造、不限类型、不追责（单人流）。
- 增量＝`B_ack..HEAD` 去掉审计自身改动 + 引用封版 hash 的提交。非空 ⇒ 提醒增量审计。
- 未确认 ⇒ 提醒（三出路），seal 不推进（硬闸，不可绕过；`--confirm-audit` 替人打勾）。
"""

from __future__ import annotations

import datetime
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ACK_REL = ".agent/seal_ack.json"


def _ack_path(workspace: Path) -> Path:
    return Path(workspace) / ACK_REL


def load_ack(workspace: Path) -> Dict[str, dict]:
    """读确认账（坏/缺 ⇒ 空 dict，不抛）。"""
    try:
        data = json.loads(_ack_path(workspace).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_ack(workspace: Path, milestone_id: str, baseline: str) -> None:
    """人确认（或授权替打勾）：记 milestone → baseline。失败不抛（调用方按未确认处理）？

    不：写不出确认＝无法证明已确认 ⇒ 抛出来让调用方按失败收（fail-clear，不能当已确认）。
    """
    p = _ack_path(workspace)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        data = load_ack(workspace)
        data[str(milestone_id)] = {
            "baseline": str(baseline or ""),
            "confirmed_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise OSError(f"审计确认写不进 {ACK_REL}：{exc}") from exc


def _git(workspace: Path, *argv: str) -> Tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(workspace), *argv],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError) as exc:
        # git 挂起（TimeoutExpired 是 SubprocessError，不是 OSError）/ 输出非 UTF-8 都要按
        # "git 不可用" fail-clear，不得让异常逃出封板硬闸。
        return 128, str(exc)
    return r.returncode, (r.stdout or "")


def _is_audit_own(full_msg: str) -> bool:
    """审计/封板自身的提交（seal trailer 系）：不计入增量。"""
    m = full_msg or ""
    return ("Audit-baseline:" in m) or ("Seal-milestone:" in m) or m.lstrip().startswith("chore(seal):")


def _cites_hash(full_msg: str, seal_hash: str) -> bool:
    """引用本次封版 hash 的提交（trailer 如 `Audit-covered: <hash>`）：带即豁免。"""
    if not seal_hash:
        return False
    m = full_msg or ""
    return (seal_hash in m) or (len(seal_hash) >= 12 and seal_hash[:12] in m)


def compute_increment(workspace: Path, b_ack: str, seal_hash: str) -> Optional[List[str]]:
    """`B_ack..HEAD` 中**真更新**（去审计自身 + 去引用 hash）。返回 `["<sha12> <subject>", ...]`。

    git 读不出（非仓/git 坏/超时）⇒ 返回 `None` 哨兵，**不**返回空列表：空列表会被
    `audit_confirmed` 读成"仅覆盖改动"⇒ 静默判确认（fail-open）。调用方见 None 必须 fail-clear。
    """
    if not b_ack:
        return []
    rc, out = _git(workspace, "log", "--format=%H%x1f%s%x1f%b%x1e", f"{b_ack}..HEAD")
    if rc != 0:
        return None
    inc: List[str] = []
    for rec in out.split("\x1e"):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        parts = rec.split("\x1f")
        sha = (parts[0] if len(parts) > 0 else "").strip()
        subj = (parts[1] if len(parts) > 1 else "").strip()
        body = (parts[2] if len(parts) > 2 else "")
        full = subj + "\n" + body
        if _is_audit_own(full):
            continue
        if _cites_hash(full, seal_hash or b_ack):
            continue
        inc.append(f"{sha[:12]} {subj}" if sha else subj)
    return inc


def _is_ancestor(workspace: Path, anc: str, desc: str) -> bool:
    if not anc or not desc:
        return False
    rc, _ = _git(workspace, "merge-base", "--is-ancestor", anc, desc)
    return rc == 0


def audit_confirmed(workspace: Path, milestone_id: str, head: str) -> Tuple[bool, str, List[str]]:
    """审计确认是否成立（硬闸判据）。返回 (ok, reason, increment)。

    - 无记录 ⇒ (False, "未确认", [])。
    - `B_ack == head` ⇒ (True, "基线一致", [])。
    - `B_ack` 是 head 祖先 ⇒ 算增量；空 ⇒ (True, "仅覆盖改动", [])；非空 ⇒ (False, "增量非空", [...])。
    - 否则（确认基线不在当前历史）⇒ (False, "确认基线不在当前历史", [])。
    - git 不可用 ⇒ (False, "git 不可用，无法核对", [])（fail-clear）。
    """
    data = load_ack(workspace)
    ent = data.get(str(milestone_id)) if isinstance(data, dict) else None
    b_ack = str((ent or {}).get("baseline") or "").strip() if isinstance(ent, dict) else ""
    if not b_ack:
        return False, "未确认：本里程碑没有审计确认记录", []
    if not head:
        return False, "git 不可用，无法核对确认基线", []
    if b_ack == head:
        return True, "已确认（确认基线即当前 HEAD）", []
    if _is_ancestor(workspace, b_ack, head):
        inc = compute_increment(workspace, b_ack, b_ack)
        if inc is None:
            # git 读不出增量 ⇒ 无法证明"只有覆盖改动" ⇒ fail-clear（不得当空增量判确认）。
            return False, "git 不可用，无法核对确认后的增量", []
        if not inc:
            return True, "已确认（确认之后只有覆盖改动：审计自身/引用封版 hash）", []
        return False, f"确认已过期：确认之后有 {len(inc)} 笔真更新", inc
    return False, "确认基线不在当前历史（可能 rewound/换仓），需重新确认", []


def format_reminder(workspace: Path, milestone_id: str, increment: List[str], head: str) -> str:
    """未确认时的提醒（三出路 + 冻结警告 + 增量清单）。"""
    lines = [
        f"[{milestone_id}] 审计未确认：封版要求先确认“已做过全版 audit”（ADR-0004 §2.1.14，硬闸）。",
        "判据是人主观确认，不是机器验证；第三方工具可替代 audit；想先只审、再让 agent 修也行。",
        "",
        "三条出路（任选其一）：",
        f"  1) 去执行审计：用第三方审计，或跑 `k3dge milestone audit {milestone_id}`（透镜/预算见 `[roles.audit]`）；",
        f"     审完确认当前即审后状态，再封。",
        f"  2) 确认当前即审后状态（替人打勾，不跑审计）：`k3dge milestone seal {milestone_id} --confirm-audit`；",
        "  3) 若已在别处审过：同样用 `--confirm-audit` 确认即可（主观确认，不另验）。",
        "",
        "增量审计提醒：确认绑定基线；确认之后**不要再改源码**，否则下次封版会再次触发本提醒。",
    ]
    if increment:
        lines += ["", f"自上次确认之后有 {len(increment)} 笔真更新（审计自身/引用 hash 已排除），增量审计应覆盖："]
        lines += [f"  - {s}" for s in increment[:12]]
        if len(increment) > 12:
            lines.append(f"  …等共 {len(increment)} 笔")
    else:
        lines += ["", "（尚无确认记录；确认后记基线 %s。）" % ((head or "")[:12])]
    return "\n".join(lines)
