"""交付包**三路合并**：把审计返回的修复并进**已经往前走的主干**（消费侧的核心动作）。

为什么需要（2026-09-27 真跑）：包里的补丁是对**审计当时的基线**生成的；主干随后会动（落钉、别的修复、
重构）。只会 `git apply` 时，一遇到"同一文件的上下文变过"就整包落不下（实测：旧包在 `flowlint.py` 冲突
⇒ 24 条修复全废）。但两侧手里其实都有完整信息：

    base  = 包的可重放基线（`code/` 反序反向应用补丁 ⇒ 审前语义层；见 `audit_verify.replay_to_baseline`）
    theirs= 包的 `code/`（审后，含修复与新钉）
    ours  = 当前主干

⇒ 标准三路合并（`git merge-file`）。钉与修复**不重叠**时能自动合（我们落的钉是独占行注释，审计的修复是代码行），
重叠时如实报冲突文件（fail-clear，交人裁），**不静默丢修复**。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from k3dge.engine.audit_verify import replay_to_baseline


def touched_files(bundle: Path) -> Set[str]:
    """包内补丁触及的文件（`+++ b/<rel>`）。"""
    out: Set[str] = set()
    for name in ("fix.patch", "pins.patch"):
        p = Path(bundle) / name
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("+++ b/"):
                out.add(line[6:].strip())
    return out


def _merge_file(ours: Path, base: Path, theirs: Path) -> Dict[str, Any]:
    """单文件三路合并（`git merge-file`）：返回 {ok, text, conflict}。"""
    tmp = Path(tempfile.mkdtemp(prefix="k3dge-merge-"))
    try:
        a = tmp / "ours"
        b = tmp / "base"
        c = tmp / "theirs"
        a.write_bytes(ours.read_bytes() if ours.is_file() else b"")
        b.write_bytes(base.read_bytes() if base.is_file() else b"")
        c.write_bytes(theirs.read_bytes() if theirs.is_file() else b"")
        rc = subprocess.run(["git", "merge-file", "-p", str(a), str(b), str(c)],
                            capture_output=True)
        text = rc.stdout.decode("utf-8", "replace")
        if rc.returncode == 0:
            return {"ok": True, "text": text, "conflict": False}
        if 1 <= rc.returncode <= 127:
            # `git merge-file` 的返回码＝**冲突个数**（不是错误码！）⇒ rc=2 是"2 处冲突"。
            # 真跑实测：把 `>1` 当错误 ⇒ 只要文件里 ≥2 处冲突就误报"合并失败"（detail 空）。
            return {"ok": False, "text": text, "conflict": True, "conflicts": rc.returncode}
        return {"ok": False, "text": "", "conflict": False,
                "detail": (rc.stderr or b"").decode("utf-8", "replace")[:200]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _hunks(patch_text: str) -> Dict[str, List[Dict[str, Any]]]:
    """拆 unified diff：`{rel: [{src_start, src_len, lines}]}`（只认我们生成的形状：`+++ b/<rel>` + `@@ -a,b +c,d @@`）。"""
    out: Dict[str, List[Dict[str, Any]]] = {}
    rel = ""
    cur: Optional[Dict[str, Any]] = None
    for line in (patch_text or "").splitlines(keepends=True):
        if line.startswith("+++ b/"):
            rel = line[6:].strip()
            out.setdefault(rel, [])
            cur = None
        elif line.startswith("@@") and rel:
            m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if not m:
                cur = None
                continue
            cur = {"src_start": int(m.group(1)), "src_len": int(m.group(2) or 1), "lines": [line]}
            out[rel].append(cur)
        elif cur is not None and (line.startswith((" ", "+", "-", "\\")) or line.strip() == ""):
            cur["lines"].append(line)
    return out


def hunks_overlapping(patch_text: str, rel: str, lines: List[int], *, slack: int = 2) -> Dict[str, Any]:
    """**只取与给定行重叠的 hunk**（用于把"未关项那几段"从落地里剔出去，其余修复照落）。

    用户裁定（2026-09-27）："已修的为什么不能落，不是 git 管理吗？" —— git 本就是按 hunk 的；
    文件级排除会把同文件里的已修一起挡掉（真跑实测：11 条修复与 3 条未关项同在两个文件里 ⇒ 一条也落不进）。
    返回 {patch, dropped: [(start, len)], detail}；无重叠 ⇒ patch 为空。
    """
    hs = _hunks(patch_text).get(rel, [])
    if not hs or not lines:
        return {"patch": "", "dropped": [], "detail": ""}
    hit = []
    for h in hs:
        lo, hi = h["src_start"] - slack, h["src_start"] + max(h["src_len"], 1) + slack
        if any(lo <= int(ln) <= hi for ln in lines):
            hit.append(h)
    if not hit:
        return {"patch": "", "dropped": [], "detail": ""}
    header = f"--- a/{rel}\n+++ b/{rel}\n"
    return {"patch": header + "".join("".join(h["lines"]) for h in hit),
            "dropped": [(h["src_start"], h["src_len"]) for h in hit], "detail": ""}


def merge_into(workspace: Path, bundle: Path, *, exclude: Iterable[str] = ()) -> Dict[str, Any]:
    """把包合进 `workspace`（**只算不写**）：返回 {ok, merged{rel: text}, conflicts[], excluded[], pins_rels[], detail}。

    按包的**两层语义**分开处理（这是它能自动合的关键）：
      1. `fix.patch`＝语义层（代码）：base＝包的可重放基线，mid＝"只反向 pins 后"的中间树（＝基线+修复）
         ⇒ 对每个文件做**三路合并** `merge-file(ours, base, mid)`（两边都在顶部加行时也能各自保留）；
      2. `pins.patch`＝标注层（钉，纯增量）：由调用方在合并后的树上**正向**应用（失败则按文件并集合并，
         因为"两边都加了钉"的正确结果就是**两枚钉都在**）。
    `exclude`＝显式排除（不做猜测）。
    """
    workspace, bundle = Path(workspace), Path(bundle)
    excluded = {str(x) for x in exclude}
    rep = replay_to_baseline(bundle)
    if not rep.get("ok"):
        return {"ok": False, "merged": {}, "conflicts": [], "excluded": sorted(excluded),
                "detail": rep.get("detail") or "无法重放基线"}
    facts = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    order = [str(x) for x in (facts.get("apply_order") or [])]
    pins_in_code = bool((facts.get("pins") or {}).get("in_code"))
    # "修复后树"（fix 合并的 theirs）怎么取：
    #   inplace + 有 pins.patch ⇒ `code/` 是"基线+修复+**钉**" ⇒ 先把钉反向掉 ⇒ 得"基线+修复"；
    #   否则（artifact，或无 pins.patch）⇒ `code/` 本身就是"基线+修复" ⇒ **直接用它**。
    # （此前无 pins.patch 时错取 base ⇒ theirs==base ⇒ 修复根本没进合并 ⇒ 后面对它剔 hunk 必然失败。）
    need_pins_replay = bool(pins_in_code and (bundle / "pins.patch").is_file())
    mid = replay_to_baseline(bundle, only=["pins.patch"]) if need_pins_replay else {"ok": False}
    base_root = Path(rep["root"])
    theirs_root = Path(bundle) / "code"
    if need_pins_replay and mid.get("ok"):
        mid_root = Path(str(mid["root"]))
        tmp_mid = str(mid_root)
    else:
        mid_root, tmp_mid = theirs_root, ""      # 复用包的 `code/`（**别 rmtree 它**）
    try:
        fix_rels = sorted(t for t in touched_files(bundle) - excluded
                          if t in set(_rels_of_patch(bundle, "fix.patch")) or True)
        fix_only = sorted(set(_rels_of_patch(bundle, "fix.patch")) - excluded)
        merged: Dict[str, str] = {}
        conflicts: List[str] = []
        missing: List[str] = []
        for rel in fix_only or fix_rels:
            theirs = mid_root / rel if (mid_root / rel).is_file() else theirs_root / rel
            if not theirs.is_file():
                missing.append(rel)
                continue
            res = _merge_file(workspace / rel, base_root / rel, theirs)
            if res.get("ok"):
                merged[rel] = str(res["text"])
            elif res.get("conflict"):
                conflicts.append(rel)
            else:
                return {"ok": False, "merged": merged, "conflicts": conflicts,
                        "excluded": sorted(excluded), "detail": f"{rel}: {res.get('detail', '')}"}
        return {"ok": not conflicts and not missing, "merged": merged, "conflicts": conflicts,
                "missing": missing, "excluded": sorted(excluded),
                "pins_patch": "pins.patch" if (bundle / "pins.patch").is_file() and "pins.patch" in order else "",
                "detail": ""}
    finally:
        shutil.rmtree(base_root, ignore_errors=True)
        if tmp_mid:
            shutil.rmtree(tmp_mid, ignore_errors=True)


def _rels_of_patch(bundle: Path, name: str) -> Set[str]:
    p = Path(bundle) / name
    if not p.is_file():
        return set()
    return {line[6:].strip() for line in p.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.startswith("+++ b/")}


def union_pins(workspace: Path, bundle: Path, rel: str) -> Dict[str, Any]:
    """钉的并集合并（两边都加了钉 ⇒ 两枚都留）：`merge-file --union`，不产生冲突标记。"""
    import subprocess as _sp

    base = replay_to_baseline(bundle, only=(["pins.patch"] if True else []))
    if not base.get("ok"):
        return {"ok": False, "text": "", "detail": base.get("detail") or "重放失败"}
    tmp = Path(tempfile.mkdtemp(prefix="k3dge-union-"))
    try:
        a, b, c = tmp / "ours", tmp / "base", tmp / "theirs"
        a.write_bytes((workspace / rel).read_bytes() if (workspace / rel).is_file() else b"")
        b.write_bytes((Path(base["root"]) / rel).read_bytes() if (Path(base["root"]) / rel).is_file() else b"")
        c.write_bytes((Path(bundle) / "code" / rel).read_bytes())
        rc = _sp.run(["git", "merge-file", "--union", "-p", str(a), str(b), str(c)], capture_output=True)
        return {"ok": rc.returncode == 0, "text": rc.stdout.decode("utf-8", "replace"),
                "detail": (rc.stderr or b"").decode("utf-8", "replace")[:200]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(Path(base["root"]), ignore_errors=True)
