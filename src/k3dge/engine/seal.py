"""封版闸 + 纯归档动作：`seal_preconditions_error`（策略层）+ `seal_milestone`（归档动作）。

Extracted from `engine/milestone.py` (A-1 第十一块).

预审清单（ADR-0004 §2.1.9 相位 1）＝形式闸那一批：报告存在性/新鲜度已移出
（报告降为可选产物、边界改由 `tag <M>=<B>` 表达），审计本身由 `seal` 的 `audit` 动作跑。
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from k3dge.engine import adr_gate, gates
from k3dge.engine.align import _ALIGN_STUB_MARKER, _align_pass_marker
from k3dge.engine.milestone_files import _has_milestone_token
from k3dge.engine.milestone_pointer import _validate_milestone_id, bump_milestone
from k3dge.engine.review_archive import (
    _reviews_to_archive,
    _rewrite_leftover_links,
    _safe_archive_dir,
)
from k3dge.engine.task_index import (
    _ALLOWED_STATUS,
    MilestoneTask,
    scan_milestone_tasks,
)
from k3dge.engine import task_index

def _missing_in(review, tasks) -> list:
    """已扫到的评审里缺哪些票名。

    拒绝消息以前**在这儿裸 `read_text` 二次读盘**：文件在扫描与渲染之间被移走/坏编码
    会让闸函数抛出而不是给出拒绝理由（460）⇒ 读不回就出声并给占位项。
    """
    try:
        text = review.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"[seal] WARN: {review.name} 复核时读不出（{type(exc).__name__}）⇒ 缺项清单不可得",
              file=sys.stderr)
        return ["<读不出>"]
    return [t.path.name for t in tasks if t.path.name not in text]


GUIDE_STUB_RE = re.compile(r"<!--\s*k3dge:guide-stub\s*-->", re.IGNORECASE)


def _strip_code(text: str) -> str:
    """去掉围栏与行内代码，只留正文（桩判定看的是**真桩**，不是"提到桩"）。"""
    from k3dge.engine import pure_refs

    return pure_refs.strip_code_spans(pure_refs.strip_fences(text))


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
        except (OSError, UnicodeDecodeError) as exc:
            # 仍**拦**（读不出不能当"已填"），但理由要说清：旧写法把它混进"未填桩"名单，
            # 消息对该文件是错的（GBK 存过的指南会被喊成"请补完文档"，459）
            out.append(f"{g.name}（读不出：{type(exc).__name__}）")
            continue
        # 只认**真桩**：行内代码/围栏里"提到"这行标记不算（本仓 guides/README 解释这条闸时就把它
        # 写进了反引号里 ⇒ 全文子串搜索会把已写好的文档判成未填，卡住 guides_filled）
        if GUIDE_STUB_RE.search(_strip_code(text)):
            out.append(g.name)
    return out


def _seal_review_gate(workspace: Path, milestone_id: str, tasks: List[MilestoneTask]) -> Optional[str]:
    """Gate 1: a filled audit review listing every task. Returns rejection msg or None."""
    reviews_dir = workspace / "docs" / "reviews"
    matching_reviews = []
    stub_reviews = []
    missing_pass = []
    incomplete_reviews: list[Path] = []
    unreadable: list[Path] = []
    pass_mark = _align_pass_marker(milestone_id)
    if reviews_dir.exists():
        for f in reviews_dir.iterdir():
            if not f.is_file() or not _has_milestone_token(f.name, milestone_id):
                continue
            # 只验对齐报告：12 列审计稿没有 align-pass marker，拿它们充 missing_pass
            # 会在「align 已写、只是任务清单缺一张票」时误报「无 marker」（真跑相位 3）。
            if "-align.md" not in f.name:
                continue
            try:
                content = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                # 权限拒绝/竞态删除不能穿透闸函数（ocr2-307），也不能静默当"缺报告"：
                # 记不可读，缺匹配时一并报出。
                incomplete_reviews.append(f)
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
            f"  Missing in {incomplete_reviews[0].name}: {_missing_in(incomplete_reviews[0], tasks)}\n"
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
    link_notes: list[str] = []
    try:
        for t in tasks:
            target = task_archive / t.path.name
            shutil.move(str(t.path), str(target))
            moved_records.append((target, t.path))
        for rev in to_archive_reviews:
            target = review_archive / rev.name
            shutil.move(str(rev), str(target))
            moved_records.append((target, rev))
            _ok, _note = _rewrite_leftover_links(
                workspace, rev.name, f"archive/{milestone_id}/{rev.name}")
            if not _ok:
                link_notes.append(_note)   # 不回滚（文件已移走是对的），但必须让操作者看见
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
        + ((" " + "；".join(link_notes)) if link_notes else "")
    )
    try:
        nxt = bump_milestone(workspace)
        return True, f"{sealed} Next milestone: {nxt}"
    except Exception as exc:
        # 指针没前进是**事实**：吞掉异常 ⇒ 调用方（seal_flow._archive 只看 ok）无从得知原因（461）
        return True, f"{sealed} ⚠️ 里程碑指针未前进（{type(exc).__name__}: {exc}）⇒ 手工 'k3dge milestone' 查因"


def _docs_normalized_error(workspace: Path) -> Optional[str]:
    """`docs_normalized` 前置闸：docs 可确定修的规约偏差必须归零（ADR-0022 §2.2 🅰1.4）。

    为何是**前置闸**而不是 seal 的动作：规约化若在审计闭环之后改文档，刚闭环的审计证据
    （审的是旧文档）就失效了 ⇒ 必须在封板前做完，由 `k3dge doc fix`（[NEXT] 引导的主动动作）
    完成；seal 只验"做没做"。语义类偏差（要读懂内容的）不在此闸，归里程碑轮的外部透镜。
    """
    from k3dge.engine import doc_fix

    dev = doc_fix.scan(workspace)
    if not dev:
        return None
    rules = sorted({d["rule"] for d in dev})
    return (f"[SEAL REJECTED] docs/ 有 {len(dev)} 处可确定修的规约偏差（{', '.join(rules)}）；"
            f"先跑 `k3dge doc fix`（可加 --dry-run 预览），再封板。")


def seal_preconditions_error(workspace: Path, milestone_id: str) -> Optional[gates.Rejection]:
    """策略层：按「硬闸契约」`[checks.seal].preconditions` 求值全部前置闸，返回首个拒绝（None=全绿）。

    返回 `gates.Rejection`（str 子类）：消息文本不变，额外携带闭集 `gate_id`（＝契约里
    声明的闸 id），供 `nextstep.GATE_NEXT` 表驱动派发——消费方不再从文案里搜关键词。

    与 `seal_milestone`（纯归档动作）分离：**何时可封＝策略（本函数）**，封板归档＝动作。
    未实现的 id 视为配置错（拒绝，不让声明空转）。
    """
    from k3dge.engine import nodes

    refs = _seal_gate_registry(workspace, milestone_id)
    ok, out = nodes.run_phase(workspace, "seal", "preconditions", refs["fns"], refs["ctx"])
    return None if ok else out


def _seal_gate_registry(workspace: Path, milestone_id: str) -> dict:
    """seal 前置闸的注册表 + ctx（**唯一构造处**：单错报告与全量查询共用一份判据）。"""
    tasks = scan_milestone_tasks(workspace, milestone_id)
    pending = task_index.work_pending(tasks, workspace)
    unfilled = scan_unfilled_guides(workspace)
    gate_fns = {
        "tasks_all_done": lambda _ctx: (
            f"Cannot seal milestone '{milestone_id}'. Tasks not done: "
            f"{[t.path.name for t in pending]}" if pending else None
        ),
        "align_pass": lambda _ctx: _seal_review_gate(workspace, milestone_id, tasks),
        "guides_filled": lambda _ctx: (
            f"[SEAL REJECTED] Unfilled guide stubs detected in docs/guides/: {unfilled}.\n"
            f"  Complete the documentation before milestone seal." if unfilled else None
        ),
        "adrs_all_accepted": lambda _ctx: adr_gate.adrs_all_accepted(workspace),
        "adr_landed": lambda _ctx: adr_gate.adr_landed(workspace),
        "adr_amend_format": lambda _ctx: adr_gate.amend_format(workspace),
        "docs_normalized": lambda _ctx: _docs_normalized_error(workspace),
    }
    ctx = {"workspace": workspace, "milestone_id": milestone_id,
           "tasks": tasks, "pending": pending, "unfilled": unfilled}
    return {"fns": gate_fns, "ctx": ctx}


def seal_checklist(workspace: Path, milestone_id: str) -> list:
    """**全量**封板前置清单：`[(gate_id, ok, message, auto)]`，顺序＝声明序。

    为什么需要全量：`seal_preconditions_error` 只报**首个**失败（闸的语义是"停"），
    于是操作者实际体验是"跑 seal → 修一个 → 再跑 → 又发现一个"的试错。清单让
    "封板前必须做的事"一次看清（`k3dge milestone seal-check <id>`），
    `[NEXT]` 的 blockers 与 seal 的拒绝信息都从这一份数据投影。
    """
    from k3dge.engine import nodes

    refs = _seal_gate_registry(workspace, milestone_id)
    auto = nodes.satisfied_ids(workspace, "seal")
    out = []
    for gid in gates.preconditions(workspace, "seal"):
        fn = refs["fns"].get(gid)
        if fn is None:
            out.append((gid, False, f"gate contract references unknown gate id: '{gid}'", False))
            continue
        err = fn(refs["ctx"])
        # `auto`：现在不过，但 seal 自己的动作会先跑它（如 `full_matrix` → 写 align-pass marker）
        out.append((gid, not err, "" if not err else str(err), bool(err) and gid in auto))
    return out


def unmet_seal_preconditions(workspace: Path, milestone_id: str) -> list:
    """**需人先办**的未过闸 `[(gate_id, message)]`（由 `seal_checklist` 派生，单一判据源）。

    不含"seal 自己会跑"的项（`nodes.satisfied_ids`）——把 `align_pass` 列成"需你先办"是
    误导：`seal` 的第一个动作就是 `full_matrix`（跑 align + 写 marker），前置闸是在它之后
    才评估的。这类项在清单里以 ⚙️ 呈现（跑失败则以 align 的理由拒）。
    """
    return [(gid, msg) for gid, ok, msg, auto in seal_checklist(workspace, milestone_id)
            if not ok and not auto]


def render_checklist(workspace: Path, milestone_id: str) -> str:
    """清单的人读投影（✓/✗ + 原因），供 seal 拒绝信息与 `seal-check` 共用。"""
    rows = seal_checklist(workspace, milestone_id)
    ok_ids = [gid for gid, ok, _m, _a in rows if ok]
    auto = [gid for gid, ok, _m, a in rows if a]
    bad = [gid for gid, ok, _m, a in rows if not ok and not a]
    lines = [f"封板前置清单（{milestone_id}）：{len(ok_ids)}/{len(rows)} 通过"
             + (f"，{len(auto)} 项由 seal 自动完成" if auto else "")]
    for gid, ok, msg, is_auto in rows:
        first = msg.splitlines()[0] if msg else ""
        if ok:
            lines.append(f"  ✅ {gid}")
        elif is_auto:
            lines.append(f"  ⚙️ {gid} —— seal 会先跑它（{first[:90]}）；跑失败则以该理由拒")
        else:
            lines.append(f"  ❌ {gid} —— {first[:110]}")
    if bad:
        lines.append(f"  ⇒ 需你先办 {len(bad)} 项：{', '.join(bad)}；"
                     f"`k3dge milestone seal-check {milestone_id}` 可随时复查")
    if auto:
        lines.append(f"  ⇒ ⚙️ {'、'.join(auto)} 由 seal 自己的动作完成，无需你预先处理")
    return "\n".join(lines)


# ── 封版记录：trailer + 边界 tag（ADR-0004 §2.1.9/§2.1.10 的 durable 面）──────
#: 封版提交的 trailer 键（**唯一格式源**：写入与读回都走本模块的 format/parse）。
SEAL_TRAILER_KEYS = ("seal-milestone", "audit-baseline", "audit-seat", "audit-result")
#: annotated tag 与封版提交同一进程身份（runner 默认没有 user.name；缺 ident 会空 stderr 失败）。
_PROCESS_GIT = ("-c", "user.name=k3dge-process", "-c", "user.email=noreply@k3dge.local")


def _git(workspace: Path, *args: str) -> tuple[int, str]:
    """`git -C <ws> …` → (rc, stdout) 成功；(rc, stderr) 失败。异常也落成 rc≠0（判定不抛）。"""
    import subprocess

    try:
        r = subprocess.run(["git", "-C", str(workspace), *args], capture_output=True, text=True)
    except OSError as exc:  # pragma: no cover - git 缺失属环境异常
        return 127, str(exc)
    if r.returncode == 0:
        return 0, (r.stdout or "").strip()
    return r.returncode, ((r.stderr or "").strip() or (r.stdout or "").strip())


def head_commit(workspace: Path) -> str:
    """当前 HEAD 的完整 hash（审计基线 B 的取值：**审计前**取一次，之后不再动）。"""
    rc, out = _git(workspace, "rev-parse", "HEAD")
    return out if rc == 0 else ""


#: 允许出现在 trailer 值里的闭集（审计结果）；其余值按事实文本净化，不判对错。
def _trailer_value(value: str) -> str:
    """外部（报告/环境/CI）取来的值净化成**单行、不含键形**的文本。

    含换行/空行会把最后一段拆开 ⇒ git 不再当 trailer 块，四键整体读不回；
    值里再出现 `": "` 会被下游按 `Key: value` 多解析出一个键（占位 `-` 也让
    「键齐全」判据失去意义）。净化＝压空白 + `": "`→`"; "` + 长度封顶（ocr-306）。
    """
    s = " ".join(str(value or "").split())
    s = s.replace(": ", "; ")
    return (s[:200] or "-")


def _same_commit(full: str, given: str) -> bool:
    """`rev-parse` 永远回 40 位小写；入参允许缩写/大写（上面的 fullmatch）⇒ 比"同一个 commit"。

    比字符串会把 `--baseline a7259c2` 误判成"边界冲突"（ocr-307）。
    """
    a, b = (full or "").strip().lower(), (given or "").strip().lower()
    return bool(a) and bool(b) and (a == b or a.startswith(b) or b.startswith(a))


def format_seal_trailers(milestone_id: str, baseline: str, seat: str, result: str) -> str:
    """封版提交 trailer 文本（git 认 `Key: value`；键用 `SEAL_TRAILER_KEYS`）。"""
    return "\n".join(
        [
            f"Seal-milestone: {_trailer_value(milestone_id)}",
            f"Audit-baseline: {_trailer_value(baseline)}",
            f"Audit-seat: {_trailer_value(seat)}",
            f"Audit-result: {_trailer_value(result)}",
        ]
    )


def parse_seal_trailers(text: str) -> dict:
    """`git log --format=%(trailers)` / 提交正文 → `{key: value}`（键小写）。

    读回与写入同源（`SEAL_TRAILER_KEYS`），故不必猜格式；缺键就是**缺记录**，
    由消费方决定"缺就提示"还是"缺就拒"。
    """
    out: dict = {}
    for line in (text or "").splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        k = key.strip().lower()
        if k in SEAL_TRAILER_KEYS:
            out[k] = value.strip()
    return out


def tag_audit_baseline(
    workspace: Path, milestone_id: str, baseline: str, *, trailers: str = ""
) -> Tuple[bool, str]:
    """`tag <M> = B`（annotated）：边界＝审的那一版（ADR-0004 §2.1.9）。

    幂等：同指向 ⇒ 绿（已立）；指向不同 ⇒ **拒**（静默移动 tag 会毁掉边界事实）。

    `trailers` 也写进注解正文：**零改动的封版没有提交可挂**（`_commit_all` 不造空提交）
    ⇒ tag 是记录的第二载体；`audit_evidence` 两处都读（先提交、后注解）。
    """
    id_err = _validate_milestone_id(milestone_id)
    if id_err:
        return False, id_err
    if not baseline or not re.fullmatch(r"[0-9a-fA-F]{7,40}", baseline):
        return False, f"审计基线不可用（{baseline!r}）：tag 不立，边界不明就不假装有边界。"
    rc, existing = _git(workspace, "rev-parse", f"refs/tags/{milestone_id}^{{commit}}")
    if rc == 0 and existing:
        # rev-parse 永远回 40 位小写；入参允许缩写/大写（上面的 fullmatch）⇒ 比"同一 commit"
        # 而不是比字符串，否则 `--baseline a7259c2` 会误判成"边界冲突"（ocr-307）
        if _same_commit(existing, baseline):
            return True, f"边界 tag 已在（{milestone_id} = {baseline[:12]}）"
        return False, (f"tag {milestone_id} 已存在且指向 {existing[:12]} ≠ 本次基线 "
                       f"{baseline[:12]}：不移动（边界事实不可改写），请人工裁决。")
    note = f"Seal boundary for {milestone_id}: audited baseline {baseline[:12]}"
    if trailers:
        note += "\n\n" + trailers
    rc, out = _git(workspace, *_PROCESS_GIT, "tag", "-a", milestone_id, "-m", note, baseline)
    if rc != 0:
        return False, f"建边界 tag 失败：{out[:160]}"
    return True, f"边界 tag：{milestone_id} = {baseline[:12]}"


def _commit_all(workspace: Path, msg: str) -> Tuple[bool, str]:
    """暂存全部改动并以**进程身份**提交（`--no-verify`：被审仓的 pre-commit 管人的提交，
    机械件不过它——同 `worktree.advance` 口径）。空改动 ⇒ `(True, "")`（不造空提交）。"""
    import tempfile

    rc, dirty = _git(workspace, "status", "--porcelain")
    if rc != 0:
        return False, f"不是 git 工作树（{dirty[:120]}）"
    if not dirty.strip():
        return True, ""
    rc, out = _git(workspace, "add", "-A")
    if rc != 0:
        return False, f"暂存失败：{out[:160]}"
    from k3dge.engine.attest import append_to_message

    msg = append_to_message(workspace, msg, who="k3dge-process")
    with tempfile.NamedTemporaryFile("w", suffix=".msg", delete=False, encoding="utf-8") as fh:
        fh.write(msg)
        tmp = fh.name
    try:
        rc, out = _git(workspace, *_PROCESS_GIT, "commit", "--no-verify", "-F", tmp)
    finally:
        try:
            Path(tmp).unlink()
        except OSError:
            pass
    if rc != 0:
        return False, f"提交失败：{out[:200]}"
    return True, head_commit(workspace)


def seal_record(
    workspace: Path,
    milestone_id: str,
    *,
    baseline: str,
    seat: str = "",
    result: str = "",
    subject: str = "",
) -> Tuple[bool, str]:
    """相位 3 的持久记录：**封版提交**（归档/提版/收摊/审计产出一起进）+ 边界 tag。

    为什么由 k3dge 自己提交：记录必须落在**必然产生的那次提交**上。审计常常零提交
    （`worktree.advance` 只在脏时提交；线 tip == 主干头 ⇒ 无新提交），报告也只落在工作树里
    ⇒ 把记录挂在"审计的提交"上会没有载体（本会话实测）。封版动作本身必然产生改动，
    所以这里一定有载体。
    """
    trailers = format_seal_trailers(milestone_id, baseline, seat, result)
    msg = (subject or f"chore(seal): seal milestone {milestone_id} "
                       f"(audit {result or '?'}; baseline {(baseline or '?')[:12]})")
    msg += "\n\n" + trailers
    ok, out = _commit_all(workspace, msg)
    if not ok:
        return False, out
    committed = out
    tag_ok, tag_msg = tag_audit_baseline(workspace, milestone_id, baseline, trailers=trailers)
    if not tag_ok:
        return False, tag_msg
    return True, f"封版提交 {committed[:12] or '(无改动，未提交)'}；{tag_msg}"


def seal_milestone(workspace: Path, milestone_id: str) -> Tuple[bool, str]:
    """纯归档动作：id 合法 + 有任务 + 状态合法 → `_seal_archive`。策略闸在 `seal_preconditions_error`。"""
    id_err = _validate_milestone_id(milestone_id)
    if id_err:
        return False, gates.Rejection("milestone_id_invalid", id_err)

    tasks = scan_milestone_tasks(workspace, milestone_id)
    if not tasks:
        from k3dge.engine.task_index import premature_archive_hint

        return False, gates.Rejection(
            "no_tasks",
            premature_archive_hint(workspace, milestone_id)
            or f"No tasks to seal for milestone '{milestone_id}'.",
        )

    invalid = [t for t in tasks if t.status not in _ALLOWED_STATUS]
    if invalid:
        return False, gates.Rejection(
            "invalid_task_status",
            f"Cannot seal milestone '{milestone_id}'. Invalid Status: "
            f"{[t.path.name for t in invalid]}",
        )

    ok, out = _seal_archive(workspace, milestone_id, tasks)
    if ok:
        return True, out
    return False, gates.rejection(out, "archive_failed")
