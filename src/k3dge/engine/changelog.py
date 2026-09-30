"""CHANGELOG 生成：**提交区间**（封版时一次生成）——不再是每张票 done 各写一行。

ADR-0004 §2.1.12（🅰1）：来源＝`<上一里程碑 tag>..HEAD` 的**非机械提交**，类型取
conventional 前缀；闸只验**不漏项**，写得好归人。理由：提交**不可漏**（每次改动必有提交），
票可漏（没开票也能改）；且区间由边界 tag 界定，"发布说明收哪一段"不再靠"谁记得写"。

**唯一写手是封版**（`seal_flow._version_bump` → `version.append_changelog`）。票侧写手
（`_append_to_unreleased` 一族）已于 2026-09-21 删除——它没有生产调用方（只有测试在养），
且"票各写一行"正是 §2.1.12 要消掉的双写来源。
"""
from __future__ import annotations

import re
from pathlib import Path

# ── 提交区间 → 版本段条目（ADR-0004 §2.1.12）──────────────────────────────
#: conventional 提交前缀 → Keep a Changelog 小节（与 `version._CT_MAP` 同口径；多取几个前缀
#: 是为了"提交闸允许的类型"都能落进某节，不被静默丢掉）。
_RANGE_TYPES = {
    "feat": "Added", "add": "Added",
    "fix": "Fixed", "audit": "Fixed", "sec": "Security",
    "docs": "Changed", "refactor": "Changed", "chore": "Changed", "perf": "Changed",
    "style": "Changed", "build": "Changed", "ci": "Changed", "test": "Changed",
    "revert": "Removed", "remove": "Removed", "deprecate": "Deprecated",
}
_SUBJECT_RE = re.compile(r"^([a-z]+)(?:\([^)]*\))?!?:\s*(.+)$", re.IGNORECASE)
_TRAILER_SEAL = "seal-milestone"


def _tag_number(tag: str) -> tuple:
    """里程碑 tag 的排序键：先按数字、再按原串（`M10` > `M9`；非数字 id 退化为字典序）。"""
    # 里程碑 tag 形如 `M11`：取**整串**首字母+数字。`findall` 取最后一段数字会被 `v1.2.3`
    # 这类非里程碑 tag 干扰（3 > 11 的比较会选错边界，且候选集没过滤里程碑形状，ocr-222）。
    m = re.fullmatch(r"([A-Za-z]*)(\d+)", tag.strip())
    if m:
        return (1, int(m.group(2)), m.group(1))
    digits = re.findall(r"\d+", tag)
    return (0, int(digits[-1]) if digits else -1, tag)


def _try(workspace: Path, *args: str):
    """不抛的 git 调用（git 缺失/不可执行 ⇒ None）。`_git` 的 fail-loud 语义保持不变。"""
    import subprocess

    try:
        return subprocess.run(["git", *args], cwd=str(workspace), capture_output=True, text=True)
    except OSError:
        return None


def _git(workspace: Path, *args: str) -> str:
    import subprocess

    # **失败要出声**：把"区间内没有提交"（rc=0、空输出）与"previous_tag 不存在/git 故障"（rc≠0）分开。
    # 旧行为把两者都压成 "" ⇒ 边界 tag 误删时封版写一条通用行、静默丢掉整段 CHANGELOG（ocr-057）。
    try:
        r = subprocess.run(["git", "-C", str(workspace), *args], capture_output=True, text=True)
    except OSError as exc:
        raise RuntimeError(f"git 不可用：{exc}") from exc
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{(r.stderr or '').strip()[:200]}")
    return r.stdout.strip()


def mechanical_commit(subject: str, body: str) -> bool:
    """**机器造的**提交（不该进 CHANGELOG，也不算"漏项"）。

    `sha` 参数已删：判据只用 subject/body，留着只是让调用方与测试传占位（411）。

    - `round work <job>`：`worktree.advance` 的进程提交（审计线现场）
    - 带 `Seal-milestone:` trailer：封版提交（归档/提版/收摊，不是人的工作内容）

    注意**不包含**"subject 不是 conventional"那种：那种要进 `uncovered`（**漏项信号**），
    静默滤掉等于把"没写清类型的提交"变成看不见——那正是本票要治的病。
    """
    if subject.startswith("round work ") or subject.startswith("round work\t"):
        return True
    # trailer 只在**末段**（`Key: value` 行）；正文/引用/测试里写过 `seal-milestone:` 不该把一条
    # 人工提交判成机械件而从 CHANGELOG 里消失（全文子串匹配过宽，ocr-223）。
    tail = (body or "").rstrip().split("\n\n")[-1] if (body or "").strip() else ""
    return any(ln.strip().lower().startswith(_TRAILER_SEAL + ":") for ln in tail.splitlines())


def build_notes_from_range(workspace: Path, previous_tag: str = "") -> tuple:
    """`<previous_tag>..HEAD` 的非机械提交 → `(notes, uncovered)`。

    `previous_tag` 为空时自动取**编号最大且是 HEAD 祖先**的里程碑 tag（排除 HEAD 自身所在
    的封版提交）；找不到 ⇒ `("", [])`（首个里程碑：调用方回落 `consume_unreleased`）。
    `uncovered` 是"解析不出类型"的提交 subject（供告警；正常应被 `mechanical_commit` 过滤）。
    """
    from k3dge.engine.milestone_files import milestone_tags

    if not previous_tag:
        import subprocess

        cands = []
        for tag in milestone_tags(workspace):
            r = _try(workspace, "merge-base", "--is-ancestor", tag, "HEAD")
            if r is not None and r.returncode == 0:   # 只认是 HEAD 祖先的边界（别的分支的 tag 不算）
                cands.append(tag)
        if not cands:
            return "", []
        previous_tag = max(cands, key=_tag_number)
    raw = _git(workspace, "log", "--no-merges", "--format=%H%x1f%s%x1f%b%x1e",
               f"{previous_tag}..HEAD")
    by_section: dict = {}
    uncovered: list = []
    for rec in raw.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        parts = rec.split("\x1f")
        sha, subject = parts[0], (parts[1] if len(parts) > 1 else "")
        body = parts[2] if len(parts) > 2 else ""
        if mechanical_commit(subject, body):
            continue
        m = _SUBJECT_RE.match(subject)
        if not m:
            uncovered.append(subject)
            continue
        kind = m.group(1).lower()
        text = m.group(2).strip()
        section = _RANGE_TYPES.get(kind)
        if section is None:
            uncovered.append(subject)
            continue
        by_section.setdefault(section, []).append(text)
    lines = []
    for section in ("Added", "Changed", "Fixed", "Deprecated", "Removed", "Security"):
        items = by_section.get(section)
        if not items:
            continue
        lines.append(f"### {section}")
        lines.extend(f"- {item}" for item in items)
        lines.append("")
    return "\n".join(lines).rstrip("\n"), uncovered
