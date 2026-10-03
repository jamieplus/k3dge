"""Task 写入核心：创建 / 关闭（含报告闸、回填、重挂）。

Extracted from `engine/milestone.py` (A-1 第九块). All deps come from leaf modules
(task_index / audit_report / milestone_pointer / milestone_files) — no cycle.
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path
import json
from typing import List, Optional, Tuple

from k3dge.engine import report_table
from k3dge.engine.audit_report import _parse_audit_stats
from k3dge.engine.milestone_files import _has_milestone_token, _is_doc_aux, _is_review_aux
from k3dge.engine.milestone_pointer import _validate_milestone_id, get_current_milestone
from k3dge.engine.task_index import MILESTONE_RE, TITLE_RE, parse_frontmatter

_TASK_TYPES = frozenset({"audit", "feat", "fix", "docs", "chore", "refactor"})
_TASK_PRIORITIES = frozenset({"P0", "P1", "P2", "P3"})


def _review_has_audit_table(text: str) -> bool:
    """报告是否像审计报告（宽松表头判定，不改口径）。"""
    if "ID|严重度|优先级|类型|问题描述|位置|状态|处置|验证" in text.replace(" ", ""):
        return True
    return "ID" in text and "问题描述" in text and "状态" in text


def _review_in_scope(text: str, title_token: str, stem_token: str, milestone_token: str) -> bool:
    """有里程碑的票只碰提到该里程碑的报告；未提到时退回标题/stem 匹配（k8d3e-a78 形状）。"""
    if not milestone_token or _has_milestone_token(text, milestone_token):
        return True
    return title_token in text or stem_token[:20] in text


#: 模糊配对的前缀子串最小长度：短中文描述（"无"/"路径错"）会让
#: "短串出现在标题里"退化成近乎无条件命中（ocr2-322）。
_MIN_MATCH = 6


def _row_hits_task(row: dict, title_token: str, stem_token: str) -> bool:
    """模糊配对（遗留启发式，本函数只判不改口径）：标题/描述前 15 字子串，或行 ID 在票名里。"""
    desc = str(row.get("问题描述", "") or "").strip()
    fid = str(row.get("ID", "") or "")
    title_token = (title_token or "").strip()
    return bool(
        (len(title_token) >= _MIN_MATCH and title_token[:15] in desc)
        or (fid and fid in stem_token)
        or (len(desc) >= _MIN_MATCH and desc[:15] in title_token)
    )


def _flip_pending_rows(
    lines: List[str],
    header: List[str],
    rows: List[Tuple[int, dict]],
    title_token: str,
    stem_token: str,
    task_name: str,
) -> Tuple[List[str], bool, str]:
    """把命中该票的 `待修` 行翻 `已修`；返回 (new_lines, changed, 最后一个待修行 fid)。"""
    new_lines = lines[:]
    changed = False
    fid = ""            # 表无匹配行时的绑定兜底（最后一个待修行）
    matched_fid = ""    # 真正被翻成 已修 的那一行（旧实现返回"末个待修行"，会把别人的 ID 写进回填，ocr-114）
    for i, row in rows:
        if row.get("状态") != "待修":
            continue
        fid = row.get("ID", "")
        if not _row_hits_task(row, title_token, stem_token):
            continue
        matched_fid = row.get("ID", "")
        row["状态"] = "已修"
        disp = row.get("处置", "")
        if "已修" not in disp:
            row["处置"] = (f"已修 → {task_name}（{disp[:40]}）" if disp
                           else f"已修 → {task_name}")
        new_lines[i] = "| " + " | ".join(row[h] for h in header) + " |"
        changed = True
    return new_lines, changed, (matched_fid or fid)


def _new_backfill_lines(task_name: str, fid: str) -> List[str]:
    """无 `## 回填` 段时新建（引用块，避免 second-table 机检）。"""
    return [
        "",
        "## 回填 — 自动（`k3dge task done`）",
        "",
        f"> | {fid or 'ID'} | 待修 | 已修 | {task_name} | 自动回填 |",
        f"> | 已修 → {task_name} |",
    ]


def _insert_into_backfill_block(new_lines: List[str], task_name: str) -> None:
    """已有 `## 回填` 段 ⇒ 在其引用块末尾插一行（原地改）。"""
    for j, ln in enumerate(new_lines):
        if not ln.strip().startswith("## 回填"):
            continue
        insert_at = j + 1
        while insert_at < len(new_lines) and not new_lines[insert_at].strip():
            insert_at += 1
        k = insert_at
        while k < len(new_lines) and new_lines[k].lstrip().startswith(">"):
            k += 1
        new_lines.insert(k, f"> | {task_name} | 已修 | 自动回填 |")
        return


def _backfill_block_text(lines: List[str]) -> str:
    """取 `## 回填` 段正文（到下一个 `## ` 标题为止）；无段 ⇒ 空串。"""
    out: List[str] = []
    in_block = False
    for ln in lines:
        if ln.strip().startswith("## 回填"):
            in_block = True
            continue
        if in_block and ln.startswith("## "):
            break
        if in_block:
            out.append(ln)
    return "\n".join(out)


def _ensure_backfill_section(new_lines: List[str], text: str, task_name: str, fid: str) -> None:
    """回填段幂等：票名已在**回填段**里 ⇒ 什么都不做。"""
    # 幂等判据限定在回填段内：整篇搜票名会被 `处置` 单元格 / 别条回填 / 相关票清单命中，
    # 于是行翻转已做却不写回填（半改，ocr2-323）。
    if task_name in _backfill_block_text(new_lines):
        return
    # 与 `_insert_into_backfill_block` 用**同一个**判据（整行 startswith）。子串判据会把
    # `### 回填 …` 当成"已有回填段"，于是插入函数找不到锚行、什么都不写 ⇒ 静默漏回填（332）
    if not any(ln.strip().startswith("## 回填") for ln in text.splitlines()):
        new_lines.extend(_new_backfill_lines(task_name, fid))
        return
    _insert_into_backfill_block(new_lines, task_name)


def _backfill_one_review(
    review_path: Path, title_token: str, stem_token: str, milestone_token: str, task_name: str
) -> Tuple[bool, str]:
    """单份报告：命中就改写落盘，返回 (是否改写, 绑定的 finding ID)。"""
    try:
        text = review_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False, ""
    if not _review_has_audit_table(text):
        return False, ""
    if not _review_in_scope(text, title_token, stem_token, milestone_token):
        return False, ""
    header, rows = report_table.parse_rows(
        text, required=("ID", "问题描述", "状态", "处置"))
    if header is None:
        return False, ""
    new_lines, changed, fid = _flip_pending_rows(
        text.splitlines(), header, rows, title_token, stem_token, task_name)
    if not changed:
        return False, ""
    _ensure_backfill_section(new_lines, text, task_name, fid)
    review_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True, fid


def _auto_backfill_reviews(workspace: Path, task_path: Path, task_title: str, milestone: str | None) -> None:
    """Best-effort auto-backfill for audit reviews when a task is marked done.

    ADR-0022:35 遗留兜底（只对**无** `report:` 指针的旧票生效；见 `_backfill_task_reviews`）。
    骨架 = 遍历 + 单份处理（`_backfill_one_review`）+ 日志；模糊配对口径集中在
    `_row_hits_task` / `_review_in_scope`，回填段手术集中在 `_ensure_backfill_section`。
    Never raises; prints WARN on failure (P3 light, not blocking).

    value-20 的拆分账（M10 修席）：本体曾 97 行 / 分支复杂度 36（全仓最高），现 18 行 / 7，
    六个子件各自 ≤7。拆分**只搬代码不改判读**——`title[:15] in desc` / `desc[:15] in title` /
    `fid in stem` 三条模糊命中、里程碑未命中时的标题回退、宽松表头判定、`处置` 截 40 字、
    幂等（票名已出现 ⇒ 不再动回填段）全部原样保留，故本函数仍是那条"易误翻状态"的启发式，
    只是字符串手术的作用域从 97 行收到三个小函数里（复核要收紧口径时只需改 `_row_hits_task`）。
    反证：若本函数或任一子件复杂度仍 >10，或上述任一匹配条件被顺手收紧/放宽，即没修对。
    """
    try:
        reviews_dir = workspace / "docs" / "reviews"
        if not reviews_dir.is_dir():
            return
        title_token = task_title.strip()
        stem_token = task_path.stem  # e.g. 2026-08-27-M6-fix-fix_AGENTS_route_05...
        milestone_token = (milestone or "").strip()
        for review_path in sorted(reviews_dir.glob("*.md")):
            if _is_review_aux(review_path.name):
                continue
            written, fid = _backfill_one_review(
                review_path, title_token, stem_token, milestone_token, task_path.name)
            if written:
                print(f"[INFO][REVIEW BACKFILL] {review_path.name}: {fid} → 已修 ({task_path.name})",
                      file=sys.stderr)
    except Exception as exc:
        print(f"[WARN][REVIEW BACKFILL] failed for {task_path.name}: {exc}", file=sys.stderr)


def create_task(
    workspace: Path,
    title: str,
    *,
    typ: str = "fix",
    slug: Optional[str] = None,
    milestone: Optional[str] = None,
    priority: str = "P2",
    report: Optional[str] = None,
    context: Optional[str] = None,
) -> Tuple[bool, str, Optional[Path]]:
    """Write a living task file. Returns (ok, message, path).

    `report` (ADR-0022): a `docs/reviews/<file>.md` pointer binding this task to an
    audit report — 1 report = 1 task. When set, `mark_task_done` requires the report
    to reach 待修==0 before the task can close.

    `context`: body for `## 上下文/切入点`. Callers that already know the concrete
    scope (e.g. the files a scan reported) must pass it — omitting it makes
    all three body sections repeat the title, producing a ticket nobody can execute.
    """
    if typ not in _TASK_TYPES:
        return False, f"invalid type '{typ}'", None
    if milestone is not None:
        err = _validate_milestone_id(milestone)
        if err:
            return False, err, None
    # `priority` 是唯一没有闭集校验的元数据字段，且 `priority`/`report` 未做换行过滤：
    # 换行会打断 YAML frontmatter（注入/解析错乱），非法优先级会让排序/筛选静默失准（ocr2-082）。
    if priority not in _TASK_PRIORITIES:
        return False, f"invalid priority '{priority}'（须为 P0/P1/P2/P3）", None
    if report is not None:
        # 取首行去空白：换行会打断 YAML frontmatter（ocr2-082）。越界路径由 `_report_open_findings` 挡。
        report = str(report).strip().splitlines()[0] if str(report).strip() else None
    raw_slug = (slug if slug is not None else title).strip()
    norm = re.sub(r"[^A-Za-z0-9]+", "_", raw_slug).strip("_")
    if not norm:
        return False, "slug must contain alphanumeric characters", None
    if milestone is None:
        try:
            milestone = get_current_milestone(workspace)
        except Exception:
            milestone = None
    date = datetime.date.today().isoformat()
    if milestone:
        fname = f"{date}-{milestone}-{typ}-{norm}.md"
    else:
        fname = f"{date}-{typ}-{norm}.md"
    target = workspace / "docs" / "tasks" / fname
    if target.exists():
        return False, f"already exists: {target.relative_to(workspace)}", target
    target.parent.mkdir(parents=True, exist_ok=True)
    # Frontmatter 是任务元数据的**唯一源**（docs/tasks/AUTHORING.md）：正文不复写
    # status/milestone/priority/date/report——第二源只能漂移（机检码 TASK_BODY_META_REDUNDANT）。
    fm_lines = ["---", f"status: idea"]
    if milestone:
        fm_lines.append(f"milestone: {milestone}")
    fm_lines.append(f"priority: {priority}")
    fm_lines.append(f"date: {date}")
    if report:
        fm_lines.append(f"report: {report}")
    fm_lines.append("---")
    fm_block = "\n".join(fm_lines)
    content = (
        f"{fm_block}\n\n"
        f"# {title}\n\n"
        f"\n"
        f"## 已确认意图\n{title}\n\n"
        f"## 可检索摘要\n{title}\n\n"
        f"## 上下文/切入点\n{context or title}\n"
    )
    target.write_text(content, encoding="utf-8")
    return True, f"created {target.relative_to(workspace)}", target


def _task_report_pointer(content: str) -> str:
    """A task's bound report path (frontmatter `report:` or body `- **Report**:`)."""
    fm = parse_frontmatter(content)
    rep = (fm.get("report") or "").strip()
    if not rep:
        m = re.search(r"-\s+\*\*Report\*\*:\s*`?([^`\n]+?)`?\s*$", content, re.MULTILINE)
        rep = m.group(1).strip() if m else ""
    return rep


def _report_open_findings(workspace: Path, report_rel: str) -> Optional[List[str]]:
    """待修 IDs still open in a report; None if the report can't be read.

    None ≠ 干净：调用方必须把"不可读"当"无法验证"拒绝关票，不能当"无待修"放行（ocr2-083）。"""
    from k3dge.engine.pure_refs import inside_workspace

    if not inside_workspace(workspace, report_rel):
        # report 来自票的 frontmatter（外部可控）：绝对路径/`..` 会让 `workspace / report_rel`
        # 读到仓外文件（333）
        print(f"[task_write] WARN: report 指针越出本仓 ⇒ 忽略（{report_rel!r}）", file=sys.stderr)
        return None
    p = workspace / report_rel
    if not p.is_file():
        return None
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return _parse_audit_stats(text).get("_ids_待修", [])


def _resolve_task_target(workspace: Path, ident: str, tasks_dir: Path, archive_dir: Path) -> Tuple[Optional[Path], Optional[str]]:
    """Resolve a done target from an exact path or unique filename substring; (path, error)."""
    raw = Path(ident)
    cand = raw if raw.is_absolute() else (workspace / ident)
    try:
        resolved = cand.resolve()
        resolved.relative_to(tasks_dir.resolve())
        # 阻断对 archive/ 目录内任务的修改（不可变性）
        if archive_dir.exists():
            try:
                resolved.relative_to(archive_dir.resolve())
                return None, f"cannot modify archived task: {ident}"
            except ValueError:
                pass
        if resolved.is_file() and not _is_doc_aux(resolved.name):
            return resolved, None
    except (ValueError, OSError):
        pass
    name_only = Path(ident).name
    matches = [
        p
        for p in sorted(tasks_dir.glob("*.md"))
        if not _is_doc_aux(p.name) and (ident in p.name or ident in p.stem or name_only == p.name)
    ]
    if not matches:
        return None, f"no task matching '{ident}'"
    if len(matches) > 1:
        names = ", ".join(p.name for p in matches)
        return None, f"multiple matches for '{ident}': {names}"
    return matches[0], None


def _rename_task_done(target: Path) -> Tuple[Path, str]:
    """Rename to `.done.md`；返回 `(路径, 告警)`。

    旧实现在目标名已占时**静默返回原路径**：调用方拿不到失败信号 ⇒ frontmatter 已写
    `status: done` 而文件名没改（468）——那正是 `status: done ⇔ .done.md` 闸要抓的形状。
    """
    if target.name.endswith(".done.md"):
        return target, ""
    new_path = target.parent / (target.name[:-3] + ".done.md")
    if new_path.exists():
        return target, (f"{new_path.name} 已存在 ⇒ 未改名（status 已 done，"
                        "文件名与状态不一致，请人工并表）")
    target.rename(new_path)
    return new_path, ""


def _backfill_task_reviews(workspace: Path, target: Path) -> None:
    """Best-effort audit-review backfill when a task closes (never raises)."""
    try:
        t_content = target.read_text(encoding="utf-8")
        if _task_report_pointer(t_content):
            # ADR-0022（1 report = 1 task）：绑定报告的票，其报告行由席位翻钉 + `待修==0`
            # 关票闸收口。这里再拿标题/描述前 15 字去**全仓** reviews 里模糊匹配，只会在
            # 别的报告里误翻相近行（value-20 的害）⇒ 有 `report:` 指针就不猜。
            return
        t_m = TITLE_RE.search(t_content)
        t_title = t_m.group(1).strip() if t_m else target.stem
        fm2 = parse_frontmatter(t_content)
        t_ms = fm2.get("milestone", "").strip() if fm2 else ""
        if not t_ms:
            mm = MILESTONE_RE.search(t_content)
            t_ms = mm.group(1).strip() if mm else ""
        _auto_backfill_reviews(workspace, target, t_title, t_ms)
    except Exception as exc:
        print(f"[WARN] task done: 报告自动回填跳过（{target.name}: {exc}）；报告仍未回填，封板闸会兜底", file=sys.stderr)


def _finalize_task_done(workspace: Path, target: Path, content: str, fm: dict) -> Tuple[bool, str, Optional[Path]]:
    """Report gate -> flip status -> rename -> review backfill（CHANGELOG 归封版，见 §2.1.12）。"""
    # ADR-0022: a task bound to an audit report can only close when that report has
    # no open 待修 findings (1 report = 1 task; closing the task == audit closure).
    report_rel = _task_report_pointer(content)
    # frontmatter 是**唯一源**：有 frontmatter 时不得让正文游离的 `Status: done` 绕过报告闸
    # （status: idea + 正文 done ⇒ 旧实现跳闸关门，ocr2-324）；正文正则只留给无 frontmatter 的遗留票。
    if fm:
        already_done = fm.get("status", "").lower() == "done"
    else:
        already_done = bool(re.search(r"-\s+\*\*Status\*\*:\s*done\b", content, re.IGNORECASE))
    if report_rel and not already_done:
        pending = _report_open_findings(workspace, report_rel)
        if pending is None:
            # 报告指针存在但不可读（缺失/越界/解码失败）⇒ 无法验证闭环，不能当"干净"放行（ocr2-083）。
            # 旧实现把 None 当"无待修"直接关票＝fail-open。
            return False, (
                f"报告 {report_rel} 不可读（缺失/越界/解码失败），无法验证闭环 ⇒ 不关票；"
                f"先修好指针或报告（悬空指针另有 DANGLING_REPORT_REF 闸）。"
            )
        if pending:
            return False, (
                f"报告 {report_rel} 仍有 {len(pending)} 条待修（{', '.join(pending[:8])}）；"
                f"先把这些行改成 已修/有意留 再关 task"
                f"（特别大的单条可在 `处置` 写 `转 sub-task <id>` 例外拆出）。"
            ), target
    if fm and "status" in fm:
        # Strict frontmatter path（唯一源；正文不再有 Status 副本可同步）
        if fm.get("status", "").lower() == "done":
            return True, f"already done: {target.name}", target
        new_content = re.sub(r"(?m)^status:\s*.*$", "status: done", content, count=1)
        if new_content == content:
            return False, f"no Status field in {target.name}", target
        target.write_text(new_content, encoding="utf-8")
    else:
        # 遗留票（无 frontmatter）：body 即唯一源，仍按旧路改正文
        if re.search(r"-\s+\*\*Status\*\*:\s*done\b", content, re.IGNORECASE):
            return True, f"already done: {target.name}", target
        new_content = re.sub(r"-\s+\*\*Status\*\*:\s*[\w-]+", "- **Status**: done", content, count=1)
        if new_content == content:
            return False, f"no Status field in {target.name}", target
        target.write_text(new_content, encoding="utf-8")
    target, rename_note = _rename_task_done(target)
    # 不代写结案段：自动占位 = 伪合规（pure_refs._CLOSURE_HEADINGS 注释）。缺段让
    # TASK_CLOSURE_MISSING 红。collect 关工单票时自己写带报告指针的 ## 结案。
    # CHANGELOG **不在这里写**（ADR-0004 §2.1.12）：它由封版时的提交区间生成——
    # 每票各写一行是双写的来源（票改了 CHANGELOG 没改、没开票的改动漏掉，本会话反复遇到）。
    _backfill_task_reviews(workspace, target)
    from k3dge.engine import events
    events.emit(workspace, "task_done", task=target.name)
    return True, (f"marked done: {target.name}" + (f"；⚠️ {rename_note}" if rename_note else "")), target


def mark_task_done(workspace: Path, ident: str) -> Tuple[bool, str, Optional[Path]]:
    """Mark one living task done. Prefer exact path from list_tasks; else unique filename substring."""
    ident = ident.strip().replace("\\", "/")
    if not ident:
        return False, "done requires a path or unique filename substring", None
    tasks_dir = workspace / "docs" / "tasks"
    archive_dir = tasks_dir / "archive"
    if not tasks_dir.is_dir():
        return False, "docs/tasks/ missing", None
    target, err = _resolve_task_target(workspace, ident, tasks_dir, archive_dir)
    if target is None:
        return False, err or f"no task matching '{ident}'", None
    try:
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return False, str(exc), target
    return _finalize_task_done(workspace, target, content, parse_frontmatter(content))


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
    excl = None
    if exclude is not None:
        try:
            # `exclude` 是任意公开参数：不在 workspace 下时 `relative_to` 抛 ValueError，
            # 会穿透"永不阻断创建"的承诺（ocr2-325）。
            excl = exclude.relative_to(workspace).as_posix()
        except ValueError:
            excl = None
    out: List[Tuple[str, str]] = []
    for r in env.get("results") or []:
        # 信封元素可能是字符串/None（对端未守约）：裸 `.get` 会 AttributeError（ocr2-325）。
        if not isinstance(r, dict):
            continue
        p = str(r.get("path") or "")
        if not p or p == excl:
            continue
        out.append((p, str(r.get("title") or "")))
        if len(out) >= 3:
            break
    return out

#: 任务文件名：`<date>-[<milestone>-]<type>-<slug>[.done].md`（type 是闭集，故能定位段位）
_TASK_NAME_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})-(?:(?P<ms>[A-Za-z0-9._-]+?)-)?"
    r"(?P<type>audit|feat|fix|docs|chore|refactor)-(?P<slug>.+?)(?P<done>\.done)?\.md$"
)


def split_task_name(name: str) -> Optional[dict]:
    """拆任务文件名 → `{date, ms, type, slug, done}`；不合规 ⇒ None（不猜）。"""
    m = _TASK_NAME_RE.match(name)
    return m.groupdict() if m else None


def build_task_name(parts: dict, milestone: Optional[str]) -> str:
    """按拆解结果重建文件名（milestone=None ⇒ 无里程碑段）。"""
    seg = f"{parts['date']}-" + (f"{milestone}-" if milestone else "")
    return f"{seg}{parts['type']}-{parts['slug']}{parts['done'] or ''}.md"


def reassign_task_milestone(
    workspace: Path, path: Path, new_milestone: Optional[str], *, dry_run: bool = False
) -> Tuple[bool, str, Optional[Path]]:
    """把一张票**重挂**到另一个里程碑（ADR-0004 §2.1.9：B 之后的改动归下一个里程碑）。

    票的里程碑事实在两处物理位置：frontmatter `milestone:` 与文件名里的 `<M>` 段
    （`docs/tasks/AUTHORING.md`）。**必须同一次改两处**——否则 `TASK_MILESTONE_MISMATCH`
    立刻红（闸恰好保证"没有半吊子重挂"）。返回 `(ok, msg, 新路径)`；幂等（同号 ⇒ no-op）。
    """
    if new_milestone is not None:
        err = _validate_milestone_id(new_milestone)
        if err:
            return False, err, None
    if not path.is_file():
        return False, f"no such task: {path}", None
    parts = split_task_name(path.name)
    if parts is None:
        return False, (f"文件名不合 `YYYY-MM-DD-<Ms>-<type>-<slug>[.done].md` 约定：{path.name}"
                       f"（不猜段位，重挂拒绝）"), None
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False, f"{path.name}: 无 frontmatter，里程碑事实无处可改（拒绝）", None
    head, _, tail = text[3:].partition("\n---")
    new_head_lines = []
    had = False
    for line in head.splitlines():
        if re.match(r"^\s*milestone\s*:", line):
            had = True
            if new_milestone is None:
                continue                                   # 摘掉里程碑段
            new_head_lines.append(f"milestone: {new_milestone}")
        else:
            new_head_lines.append(line)
    if new_milestone is not None and not had:
        new_head_lines.append(f"milestone: {new_milestone}")
    target_name = build_task_name(parts, new_milestone)
    target = path.with_name(target_name)
    if target == path and f"milestone: {new_milestone}" in head:
        return True, f"已是 {new_milestone}（幂等）", path
    if dry_run:
        return True, f"[dry-run] {path.name} -> {target_name}", target
    if target != path and target.exists():
        # 先查目标存在性再动盘：frontmatter 已重写后才发现撞名 ⇒ 内容说新里程碑、文件名还是旧的，
        # 票就腐了（ocr2-084）。 existence 检查必须在写之前。
        return False, f"目标已存在：{target.name}（先人工处理，原文未动）", None
    path.write_text("---" + "\n".join(new_head_lines) + "\n---" + tail, encoding="utf-8")
    if target != path:
        path.rename(target)
    return True, f"{path.name} -> {target_name}", target


def reassign_milestone(
    workspace: Path, from_milestone: str, to_milestone: str, *, dry_run: bool = False
) -> Tuple[bool, List[str]]:
    """把 `docs/tasks/` 顶层**全部** `from_milestone` 的票重挂到 `to_milestone`（幂等、逐张报）。"""
    tasks_dir = workspace / "docs" / "tasks"
    lines: List[str] = []
    ok_all = True
    if not tasks_dir.is_dir():
        return False, [f"no tasks dir: {tasks_dir}"]
    # **先读完再改**：旧实现在循环里裸 `read_text`，坏文件让整批以异常中断，而它前面的票
    # 已经改完 ⇒ 部分迁移（334）。读不出的票记 FAIL 并跳过，迁移不因此中断。
    scanned: list = []
    for p in sorted(tasks_dir.glob("*.md")):
        if p.name in ("README.md", "AUTHORING.md") or p.name.startswith("_"):
            continue
        try:
            fm = parse_frontmatter(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as exc:
            lines.append(f"FAIL {p.name}: 读不出（{type(exc).__name__}）⇒ 跳过")
            ok_all = False
            continue
        if (fm.get("milestone") or "").strip() != from_milestone:
            continue
        scanned.append(p)
    for p in scanned:
        # apply 阶段也要逐张兜异常：read/write/rename 在竞态/权限下会抛，不得让整批半途中止
        # （前面已迁移、后面的没动，ocr2-326）。
        try:
            ok, msg, _newp = reassign_task_milestone(workspace, p, to_milestone, dry_run=dry_run)
        except (OSError, UnicodeDecodeError) as exc:
            ok, msg = False, f"{p.name}: 应用失败（{type(exc).__name__}: {exc}）⇒ 跳过"
        lines.append(("OK  " if ok else "FAIL") + " " + msg)
        ok_all = ok_all and ok
    if not lines:
        lines.append(f"没有 {from_milestone} 的票可重挂（幂等，无需动作）")
    return ok_all, lines
