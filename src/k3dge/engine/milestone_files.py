"""Milestone file-name / review-file helpers (extracted from `engine/milestone.py`, A-1 第三块).

Pure, low-coupling predicates/regexes.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

# Docs that live inside a docs/<type>/ directory but are never content items:
# scaffolding/authoring files. Single source — task scanning and review scanning
# used to keep their own copies and drifted (AUTHORING.md leaked into `task list`).
_DOC_AUX_NAMES = frozenset({"README.md", "AUTHORING.md", "_template.md"})

_REVIEW_AUX = _DOC_AUX_NAMES | frozenset({"LEFTOVERS.md", "leftovers.md"})

_FILENAME_MILESTONE_RE = re.compile(r"(?:^|[._-])(M\d+)(?:[._-]|$)", re.IGNORECASE)


def _has_milestone_token(text: str, milestone_id: str) -> bool:
    """True iff `milestone_id` appears as a path/word token, not a substring of a longer id.

    `M1` must not match `M10` in filenames (`2026-08-23-M10-align.md`) or review body text.
    **实现在零依赖层**（`pure_refs.has_milestone_token`）：闸核也要判同一件事
    （`check_task_consistency` 的 milestone↔文件名一致性），两处不得各写一套正则。
    """
    from k3dge.engine import pure_refs

    return pure_refs.has_milestone_token(text, milestone_id)


def _is_doc_aux(name: str) -> bool:
    """True for structural files inside docs/<type>/ that are never items."""
    return name in _DOC_AUX_NAMES or name.startswith(".")


def _is_review_aux(name: str) -> bool:
    return name in _REVIEW_AUX or name.startswith(".")


def _filename_milestone(name: str) -> str | None:
    m = _FILENAME_MILESTONE_RE.search(name)
    return m.group(1) if m else None      # 原样返回；比较侧负责大小写（见 267 的两处调用方）

def _git(workspace: Path, *args: str) -> tuple:
    import subprocess

    try:
        r = subprocess.run(["git", "-C", str(workspace), *args], capture_output=True, text=True)
    except OSError as exc:  # pragma: no cover - 环境异常
        return 127, str(exc)
    return r.returncode, (r.stdout or "").strip()


def _git_err(workspace: Path, *args: str) -> tuple:
    """同上但回 stderr（`cat-file -e` 的失败原因写在这里）。"""
    import subprocess

    try:
        r = subprocess.run(["git", "-C", str(workspace), *args], capture_output=True, text=True)
    except OSError as exc:  # pragma: no cover
        return 127, str(exc)
    return r.returncode, (r.stderr or "").strip()


_SAFE_MILESTONE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def milestone_tags(workspace: Path) -> dict:
    """本仓的**里程碑边界 tag** → `{tag: sha}`（ADR-0004 §2.1.9：`tag <M> = <B>`）。"""
    rc, out = _git(workspace, "tag", "--list")
    if rc != 0:
        return {}
    tags = {}
    for name in out.splitlines():
        name = name.strip()
        if not name or not _SAFE_MILESTONE_ID.fullmatch(name):
            continue
        rc2, sha = _git(workspace, "rev-parse", f"refs/tags/{name}^{{commit}}")
        if rc2 == 0 and sha:
            tags[name] = sha
    return tags


def tasks_after_boundary(workspace: Path) -> List[Tuple[str, str, str]]:
    """边界之后出现、却仍挂在**已封**里程碑上的票 → `[(rel, milestone, msg)]`。

    为何：ADR-0004 §2.1.9 定"边界＝`tag <M> = <B>`；B 之后的改动归下一个里程碑"。有了边界
    就有窗口期——票在 B 之后新开而指针未前进，就会挂在 M 上，下一版的任务集随之错。

    判定用 git 的**存在性**而非提交区间：`git cat-file -e <M>:<票路径>`——边界那一版**还没有**
    这张票（含"已提交但边界之后才加"与"尚未提交"两种情形，工作树视角一致）而它挂着 `M`
    ⇒ 报。用区间（`--diff-filter=A`）会漏掉"新建但还没提交"这一最常见情形。

    这是 **advisory 事实**（不阻断）：k3dge 不判"这张票该归哪一版"，只指出"边界那一版还没有
    它，而它挂在边界那一版上"。
    """
    from k3dge.engine import pure_refs

    tags = milestone_tags(workspace)
    if not tags:
        return []
    tasks_dir = workspace / "docs" / "tasks"
    if not tasks_dir.is_dir():
        return []
    out: List[Tuple[str, str, str]] = []
    for path in sorted(tasks_dir.glob("*.md")):
        if _is_doc_aux(path.name):   # 复用单源，别在这里再写一份排除规则（ocr-268）
            continue
        try:
            fm = dict(pure_refs.parse_frontmatter_pairs(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
        ms = (fm.get("milestone") or "").strip()
        if not ms or ms not in tags:
            continue
        rel = path.relative_to(workspace).as_posix()
        rc, err = _git_err(workspace, "cat-file", "-e", f"{ms}:{rel}")   # 判据在 stderr，不是 stdout
        if rc == 0:
            continue                      # 边界那一版已有它 ⇒ 属该里程碑，正常
        _absent = ("invalid object name" in err.lower() or "but not in" in err.lower())
        if rc != 1 and not _absent:   # rc=1 / "rev 不存在" / "该 rev 里没有此路径" 都是"那一版没有它"
            # rc=1（或 rev 本身不存在的 128）＝"那一版没有这个路径" ⇒ 该报；
            # 其余 128/127（仓损坏、并发 lock、git 不可用）不得当成"没有"（ocr-269）。
            print(f"[milestone_files] WARN: cat-file 探测失败（rc={rc}: {err.strip()[:120]}）"
                  f"⇒ {rel} 的边界判定跳过", file=__import__("sys").stderr)
            continue
        out.append((rel, ms, (
            f"{rel}: 这张票在 {ms} 的边界（tag {ms}）那一版里**还不存在**，却挂在 {ms} 上"
            f"——按 ADR-0004 §2.1.9，边界之后的改动归下一个里程碑")))
    return out
