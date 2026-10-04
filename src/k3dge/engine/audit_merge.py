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


def _owned_replay(bundle: Path, *, only: Optional[List[str]] = None) -> Dict[str, Any]:
    """`replay_to_baseline` 的**唯一内部入口**（value-8 报告）：把"谁拥有这棵重放树"写成契约——
    返回的 `root` 由**本模块自建**，所有权归**调用方**（用完自己 `rmtree`）。`owner` 字段显式标出。
    """
    res = replay_to_baseline(bundle, only=only)
    if res.get("ok"):
        res["owner"] = "caller"
    return res


def touched_files(bundle: Path) -> Set[str]:
    """包内补丁触及的文件＝两份补丁声明集的**并集**（value-4：规则只在 `patch_rels` 里写一遍）。"""
    out: Set[str] = set()
    for name in ("fix.patch", "pins.patch"):
        out |= patch_rels(bundle, name)
    return out


def _merge_file(ours: Path, base: Path, theirs: Path) -> Dict[str, Any]:
    """单文件三路合并（`git merge-file`）：返回 {ok, text, conflict}。"""
    tmp = Path(tempfile.mkdtemp(prefix="k3dge-merge-"))
    try:
        a = tmp / "ours"
        b = tmp / "base"
        c = tmp / "theirs"
        try:
            a.write_bytes(ours.read_bytes() if ours.is_file() else b"")
            b.write_bytes(base.read_bytes() if base.is_file() else b"")
            c.write_bytes(theirs.read_bytes() if theirs.is_file() else b"")
            rc = subprocess.run(["git", "merge-file", "-p", str(a), str(b), str(c)],
                                capture_output=True)
        except (OSError, FileNotFoundError) as exc:  # git 未装/无 exec 权/读源文件失败（ocr3-076）
            return {"ok": False, "error": f"merge-file 不可用: {exc}", "text": "", "conflict": False}
        if rc.returncode == 0:
            try:
                # `decode(..., "replace")` 把非 UTF-8（GBK/latin-1/二进制）换成 U+FFFD，落盘方
                # 再 `write_text` 写回 ⇒ 原字节不可恢复的静默改写（ocr-211）。宁可不出结果。
                return {"ok": True, "text": rc.stdout.decode("utf-8"), "conflict": False}
            except UnicodeDecodeError:
                return {"ok": False, "text": "", "conflict": False,
                        "detail": "merge 输出非 UTF-8（二进制/异编码）⇒ 不落地"}
        text = rc.stdout.decode("utf-8", "replace")
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
        if line.startswith("diff --git "):
            # 文件边界用 `diff --git`（**不能**用 `--- a/`：正文里被删的 `-- xxx` 行会显示成
            # `--- xxx`，前缀与 `--- a/` 无法区分 ⇒ 会把下一文件的头吞进上一 hunk，ocr-048）。
            rel = ""
            cur = None
        elif line.startswith("+++ b/"):
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


def _fail(detail: str, *, merged=None, conflicts=None, missing=None, excluded=(),
          pins_rels=(), pins_patch: str = "") -> dict:
    """失败面的**统一形状**：与成功面同键（缺 `missing`/`pins_rels`/`pins_patch`
    会让按成功面取值的调用方 KeyError，399）。"""
    return {"ok": False, "merged": merged or {}, "conflicts": conflicts or [],
            "missing": missing or [], "pins_rels": list(pins_rels), "pins_patch": pins_patch,
            "excluded": sorted(excluded), "detail": detail}


def merge_into(workspace: Path, bundle: Path, *, exclude: Iterable[str] = ()) -> Dict[str, Any]:
    """把包合进 `workspace`（**只算不写**）：返回 {ok, merged{rel: text}, conflicts[], excluded[], pins_rels[], detail}。

    按包的**两层语义**分开处理（这是它能自动合的关键）：
      1. `fix.patch`＝语义层（代码）：base＝包的可重放基线，mid＝"只反向 pins 后"的中间树（＝基线+修复）
         ⇒ 对每个文件做**三路合并** `merge-file(ours, base, mid)`（两边都在顶部加行时也能各自保留）；
      2. `pins.patch`＝标注层（钉，纯增量）：**本函数只报出 `pins_rels`**（`patch_rels` 单源），实际应用
         由落盘方 `audit_bundle._apply_sequential_merged` 做：先正向 `git apply pins.patch`，打不上再对该
         文件**并集**合并（`union_pins`：两边都加钉 ⇒ 两枚都留）。
    （code-8 报告原意是在本函数内做并集；但落盘方已在做同一件事 ⇒ 照做会成**两份实现**，故改为兑现契约的
    另一半：把 `pins_rels` 作为单源暴露出来、文档写清谁在应用。」
    `exclude`＝显式排除（不做猜测）。
    """
    workspace, bundle = Path(workspace), Path(bundle)
    excluded = {str(x) for x in exclude}
    rep = _owned_replay(bundle)
    if not rep.get("ok"):
        return _fail(rep.get("detail") or "无法重放基线", excluded=excluded)
    try:
        facts = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # 包缺/坏 manifest（外部交付包完全可能）⇒ fail-clear 且**清掉**刚建的重放树（ocr-049）。
        shutil.rmtree(Path(rep["root"]), ignore_errors=True)
        return _fail(f"manifest.json 不可读/不可解析：{exc}", excluded=excluded)
    # manifest 来自不可信交付包：合法 JSON 但非对象/字段形状不对时 `.get` 会抛
    # AttributeError/TypeError，且重放树会泄漏（ocr2-211）⇒ 先验形状再用。
    if not isinstance(facts, dict):
        shutil.rmtree(Path(rep["root"]), ignore_errors=True)
        return _fail(f"manifest.json 顶层不是对象（{type(facts).__name__}）", excluded=excluded)
    _raw_order = facts.get("apply_order") or []
    if not isinstance(_raw_order, list):
        shutil.rmtree(Path(rep["root"]), ignore_errors=True)
        return _fail(f"manifest.json apply_order 不是列表（{type(_raw_order).__name__}）",
                      excluded=excluded)
    order = [str(x) for x in _raw_order]
    _raw_pins = facts.get("pins") or {}
    pins_in_code = bool(_raw_pins.get("in_code")) if isinstance(_raw_pins, dict) else False
    # "修复后树"（fix 合并的 theirs）怎么取：
    #   inplace + 有 pins.patch ⇒ `code/` 是"基线+修复+**钉**" ⇒ 先把钉反向掉 ⇒ 得"基线+修复"；
    #   否则（artifact，或无 pins.patch）⇒ `code/` 本身就是"基线+修复" ⇒ **直接用它**。
    # （此前无 pins.patch 时错取 base ⇒ theirs==base ⇒ 修复根本没进合并 ⇒ 后面对它剔 hunk 必然失败。）
    need_pins_replay = bool(pins_in_code and (bundle / "pins.patch").is_file())
    base_root = Path(rep["root"])
    theirs_root = Path(bundle) / "code"
    mid = replay_to_baseline(bundle, only=["pins.patch"]) if need_pins_replay else {"ok": False}
    if need_pins_replay and not mid.get("ok"):
        # 重放不成还回落含钉的 `code/` 会把钉当"修复侧改动"合进来、再正向 apply pins.patch ⇒
        # `--union` 对同位置两侧新增都保留 ⇒ 同一枚钉写两遍（ocr-050）。如实报错，不静默降级。
        shutil.rmtree(base_root, ignore_errors=True)
        return _fail(f"pins 重放失败：{mid.get('detail') or '?'}（拒绝用含钉的 code/ 当修复侧）",
                     excluded=excluded)
    mid_root = Path(str(mid["root"])) if mid.get("ok") else theirs_root
    tmp_mid = str(mid_root) if mid.get("ok") else ""      # 复用包的 `code/`（**别 rmtree 它**）
    try:
        # code-4（报告）：原 `... or True` 是**恒真谓词** ⇒ 过滤完全失效。改成显式语义：
        # 回落集**只认 fix 层**：`fix_rels` 为空意味着"没有 fix.patch 或其文件全被排除"，
        # 用 `touched_files`（fix ∪ pins）当回退会把标注层硬塞进 fix 三路合并，与两层语义矛盾（ocr-212）。
        fix_rels = sorted(patch_rels(bundle, "fix.patch") - excluded)
        merged: Dict[str, str] = {}
        conflicts: List[str] = []
        missing: List[str] = []
        for rel in fix_rels:
            if need_pins_replay:
                # 中间树是"基线+修复"（钉已反向掉）：它里面缺 `rel` 说明反向钉删掉了该文件 ⇒
                # 回落含钉的 `code/` 会把钉当修复侧改动合进来（再正向 apply pins.patch ⇒ 同一枚钉写两遍，
                # ocr-050/ocr2-212）。记 missing，不静默降级。
                _theirs = mid_root / rel
                if not _theirs.is_file():
                    missing.append(rel)
                    continue
                theirs = _theirs
            else:
                theirs = mid_root / rel if (mid_root / rel).is_file() else theirs_root / rel
                if not theirs.is_file():
                    missing.append(rel)
                    continue
            # code-6（报告）：**base 存在而 ours 缺失** ⇒ 记 `missing` 并跳过（原实现把缺失侧写成空文件，
            # 三方皆空会合出 rc=0/text="" ⇒ 调用方以为"合并成功但内容为空"）。base 缺失而 ours 在（fix 新增
            # 文件）是正常情形，继续合。
            if (base_root / rel).is_file() and not (workspace / rel).is_file():
                missing.append(rel)
                continue
            res = _merge_file(workspace / rel, base_root / rel, theirs)
            if res.get("ok"):
                merged[rel] = str(res["text"])
            elif res.get("conflict"):
                conflicts.append(rel)
            else:
                return _fail(f"{rel}: {res.get('detail', '')}", merged=merged,
                             conflicts=conflicts, missing=missing, excluded=excluded)
        pins_rels = sorted(patch_rels(bundle, "pins.patch") - excluded)
        _why = []
        if conflicts:
            _why.append(f"冲突 {len(conflicts)} 个：{'、'.join(conflicts[:3])}")
        if missing:      # 落盘方只读 conflicts+detail ⇒ 旧写法"主干被删/找不到"一句消息都没有（400）
            _why.append(f"主干缺文件 {len(missing)} 个：{'、'.join(missing[:3])}")
        return {"ok": not conflicts and not missing, "merged": merged, "conflicts": conflicts,
                "missing": missing, "pins_rels": pins_rels, "excluded": sorted(excluded),
                "pins_patch": "pins.patch" if (bundle / "pins.patch").is_file() and "pins.patch" in order else "",
                "detail": "；".join(_why)}
    finally:
        shutil.rmtree(base_root, ignore_errors=True)
        if tmp_mid:
            shutil.rmtree(tmp_mid, ignore_errors=True)


def patch_rels(bundle: Path, name: str) -> Set[str]:
    """补丁声明的文件集合（`+++ b/<rel>`）——**公开单源**（value-4：送检面内曾有三份同规则实现）。

    `rel` 来自**外部交付包**，且被 `merge_into`/`union_pins`/落盘方拼进路径读写 ⇒ 绝对路径/`..`
    会逃出工作区（上游 `APPLY_PATH_ESCAPE` 只挡 `git apply`，挡不住这里的 mkdir+写，ocr-213）。
    """
    p = Path(bundle) / name
    if not p.is_file():
        return set()
    out: Set[str] = set()
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        rel = ""
        if line.startswith("+++ b/"):
            rel = line[6:].strip()
        elif line.startswith("--- a/"):
            # 删除型补丁的声明只在 `---` 侧（`+++` 是 /dev/null）：只认 `+++` 会把删除
            # 静默丢出触及集（ocr2-194/195）。
            rel = line[6:].strip()
        else:
            continue
        if (not rel or rel == "/dev/null" or rel.startswith("/")
                or ".." in Path(rel).parts or re.match(r"^[A-Za-z]:", rel)):
            continue
        out.add(rel)
    return out


#: 旧名（内部调用点过渡用）
# 旧名过渡别名 `_rels_of_patch` 已零引用（src/tests/docs 全走 `patch_rels`）⇒ 删除，
# 免得"公开单源"出现两个入口（ocr-401）。


def union_pins(workspace: Path, bundle: Path, rel: str) -> Dict[str, Any]:
    """钉的并集合并（两边都加了钉 ⇒ 两枚都留）：`merge-file --union`，不产生冲突标记。"""

    # code-5（报告）：base 必须是**纯基线**（`code/` 是"基线+fix+钉"，只反向钉会得"基线+fix"",
    # 与 ours（干线）/theirs（基线+fix+钉）不同基 ⇒ 并集会把 fix 当成钉侧的改动重复带入）。原实现还有
    # 一个恒真 `if True`（同 code-4 的味道）。
    base = _owned_replay(bundle)
    if not base.get("ok"):
        return {"ok": False, "text": "", "detail": base.get("detail") or "重放失败"}
    tmp = Path(tempfile.mkdtemp(prefix="k3dge-union-"))
    try:
        a, b, c = tmp / "ours", tmp / "base", tmp / "theirs"
        a.write_bytes((workspace / rel).read_bytes() if (workspace / rel).is_file() else b"")
        b.write_bytes((Path(base["root"]) / rel).read_bytes() if (Path(base["root"]) / rel).is_file() else b"")
        # 包的 code/ 里缺 `rel`（删除/半包）时裸 read_bytes 会抛 FileNotFoundError，跳出
        # `{ok, text, detail}` 契约（ocr2-213）⇒ fail-clear。
        _bundle_rel = Path(bundle) / "code" / rel
        if not _bundle_rel.is_file():
            return {"ok": False, "text": "",
                    "detail": f"{rel}: 包内 code/ 缺该文件（删除/半包），钉并集无法做，需人工处理"}
        c.write_bytes(_bundle_rel.read_bytes())
        # 钉是文本标注：任一输入非 UTF-8（二进制）时 `decode("replace")` 会把字节换成 U+FFFD，
        # 调用方再 `write_text(utf-8)` 写回 ⇒ 二进制文件被静默改写损坏（ocr2-046）。直接拒，不合二进制。
        for _p in (a, b, c):
            try:
                _p.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                return {"ok": False, "text": "",
                        "detail": f"{rel}: 非 UTF-8 文件不做钉并集（防二进制损坏），需人工处理"}
        rc = subprocess.run(["git", "merge-file", "--union", "-p", str(a), str(b), str(c)], capture_output=True)
        try:
            _text = rc.stdout.decode("utf-8")
        except UnicodeDecodeError:
            return {"ok": False, "text": "", "detail": f"{rel}: 合并输出非 UTF-8，不落盘"}
        return {"ok": rc.returncode == 0, "text": _text,
                "detail": (rc.stderr or b"").decode("utf-8", "replace")[:200]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(Path(base["root"]), ignore_errors=True)
