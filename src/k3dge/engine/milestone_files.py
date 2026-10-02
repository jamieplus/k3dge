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
# Casefolded: lowercase/mixed-case scaffolding (`readme.md`, `_Template.md`) leaks
# in as content otherwise (ocr2-274).
_DOC_AUX_NAMES = frozenset({"readme.md", "authoring.md", "_template.md"})

_REVIEW_AUX = _DOC_AUX_NAMES | frozenset({"leftovers.md"})

_FILENAME_MILESTONE_RE = re.compile(r"(?:^|[._-])(M\d+)(?:[._-]|$)", re.IGNORECASE)


from k3dge.engine.pure_refs import has_milestone_token as _has_milestone_token


def _is_doc_aux(name: str) -> bool:
    """True for structural files inside docs/<type>/ that are never items."""
    return name.casefold() in _DOC_AUX_NAMES or name.startswith(".")


def _is_review_aux(name: str) -> bool:
    return name.casefold() in _REVIEW_AUX or name.startswith(".")


def _filename_milestone(name: str) -> str | None:
    m = _FILENAME_MILESTONE_RE.search(name)
    return m.group(1) if m else None      # 原样返回；比较侧负责大小写（见 267 的两处调用方）

def _git(workspace: Path, *args: str) -> tuple:
    import subprocess

    try:
        # timeout：卡死的 git（index lock/NFS）不得无限期挂住整条闸（ocr2-275）。
        # 显式 utf-8：git plumbing 输出是 UTF-8，locale 解码在非 UTF-8 环境下抛
        # UnicodeDecodeError（不是 OSError，会穿透调用方）。
        r = subprocess.run(["git", "-C", str(workspace), *args], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover - 环境异常
        return 127, str(exc)
    return r.returncode, (r.stdout or "").strip()


def _git_err(workspace: Path, *args: str) -> tuple:
    """同上但回 stderr（`cat-file -e` 的失败原因写在这里）。"""
    import subprocess

    try:
        r = subprocess.run(["git", "-C", str(workspace), *args], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover
        return 127, str(exc)
    return r.returncode, (r.stderr or "").strip()


_SAFE_MILESTONE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
#: 里程碑边界 tag 形状：**必须以字母开头、以数字结尾**（`M10`/`R21`/`v1`）。
#: `_SAFE_MILESTONE_ID` 只挡参数注入，放行的裸年份 `2024` 会被 `_tag_number` 排到真边界
#: `M10` 之前 ⇒ CHANGELOG 区间切错（ocr2-276）。
_MILESTONE_TAG_RE = re.compile(r"[A-Za-z]+\d+")


def milestone_tags(workspace: Path) -> dict:
    """本仓的**里程碑边界 tag** → `{tag: ""}`（键＝集合，ADR-0004 §2.1.9：`tag <M> = <B>`）。

    便宜面：绝大多数消费者只问"这个号是不是边界"（`milestone_files` 的归属提醒、
    `changelog` 的区间切分）， sha 值无人读 ⇒ 每个 tag 一次的 `rev-parse` 子进程纯属浪费（433）。
    需要 sha 的调用点自己 `rev-parse`（目前全仓没有）。
    """
    rc, out = _git(workspace, "tag", "--list")
    if rc != 0:
        # git 不可用/仓损坏 ⇒ `{}` 与"确实没有 tag"不可分，下游会把"不知道"读成"干净"（ocr2-277）。
        print(f"[milestone_files] WARN: git tag --list 失败（rc={rc}: {out.strip()[:120]}）"
              "⇒ 边界 tag 事实不可用", file=__import__("sys").stderr)
        return {}
    tags = {}
    for name in out.splitlines():
        name = name.strip()
        if not name or not _SAFE_MILESTONE_ID.fullmatch(name):
            continue
        if not _MILESTONE_TAG_RE.fullmatch(name):   # 非里程碑形状（裸年份等）不参与边界（ocr2-276）
            continue
        tags[name] = ""
    return tags


def tasks_after_boundary(workspace: Path) -> List[Tuple[str, str, str]]:
    """边界之后出现、却仍挂在**已封**里程碑上的票 → `[(rel, milestone, msg)]`。

    为何：ADR-0004 §2.1.9 定"边界＝`tag <M> = <B>`；B 之后的改动归下一个里程碑"。有了边界
    就有窗口期——票在 B 之后新开而指针未前进，就会挂在 M 上，下一版的任务集随之错。

    判定用 git 的**存在性**而非提交区间：列出边界那一版的 `docs/tasks`（`git ls-tree -r
    <M> -- docs/tasks`，每个边界一次调用）——边界那一版**还没有**这张票（含"已提交但边界
    之后才加"与"尚未提交"两种情形，工作树视角一致）而它挂着 `M` ⇒ 报。用区间
    （`--diff-filter=A`）会漏掉"新建但还没提交"这一最常见情形。

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
    tags_by_lower = {t.lower(): t for t in tags}
    candidates: List[Tuple[str, str]] = []
    for path in sorted(tasks_dir.glob("*.md")):
        # `glob("*.md")` 也会命中**目录**（本仓 fixture 就有）⇒ 必须先判 is_file（ocr2-278）。
        if _is_doc_aux(path.name) or not path.is_file():
            continue
        try:
            # 键归一小写：`Milestone:`/`MILESTONE:` 与 `pure_refs` 的口径一致（ocr2-278）。
            fm = {k.lower(): v for k, v in pure_refs.parse_frontmatter_pairs(
                path.read_text(encoding="utf-8"))}
        except (OSError, UnicodeDecodeError) as exc:
            # 读不出不得静默从 advisory 里消失（与下一分支同样出声，ocr2-278）。
            print(f"[milestone_files] WARN: 票不可读，跳过边界判定（{path.name}: "
                  f"{type(exc).__name__}）", file=__import__("sys").stderr)
            continue
        ms = str(fm.get("milestone") or "").strip()
        resolved = tags_by_lower.get(ms.lower())
        if not resolved:
            continue
        candidates.append((path.relative_to(workspace).as_posix(), resolved))
    if not candidates:
        return []
    # 每个边界**一次** git 调用：旧实现按候选票逐个 `cat-file` ⇒ O(#tasks) 个子进程（ocr2-279）。
    trees: dict = {}
    for ms in sorted({m for _, m in candidates}):
        rc, tree_out = _git(workspace, "ls-tree", "-r", "--name-only", ms, "--", "docs/tasks")
        if rc == 0:
            trees[ms] = set(tree_out.splitlines())
        else:
            trees[ms] = None
            print(f"[milestone_files] WARN: ls-tree {ms} 失败（rc={rc}: {tree_out.strip()[:120]}）"
                  f"⇒ 该边界的票判定跳过", file=__import__("sys").stderr)
    out: List[Tuple[str, str, str]] = []
    for rel, ms in candidates:
        tree = trees.get(ms)
        if tree is None:
            continue
        if rel in tree:
            continue                      # 边界那一版已有它 ⇒ 属该里程碑，正常
        out.append((rel, ms, (
            f"{rel}: 这张票在 {ms} 的边界（tag {ms}）那一版里**还不存在**，却挂在 {ms} 上"
            f"——按 ADR-0004 §2.1.9，边界之后的改动归下一个里程碑")))
    return out
