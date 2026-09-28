"""k3dit 交付包**消费侧**（k3dit 仓 0028 的消费方实现）。

形状（与 k3dit 仓 0028 对齐）::

    冻结提交（基线 B） → k3dit 路径入口产包（`k3dit audit --path . --out <bundle> --mode full`）
      → 验包（`k3dit audit --verify <bundle>`：反向重放逐字节 + 12 列 + findings↔报告）
      → 读包内**机器可读判定**（`bundle_version` / `status` / `unclosed` / `apply_order`）
      → 按 `apply_order` 用**标准 `git apply`** 把 `fix.patch` + `pins.patch` 落到工作树
      → 由调用方决定提交/封板（本模块**不**改历史）

为什么 k3dge 要自己 apply 而不是让 k3dit 写：k3dit 仓 0028 §2.9「k3dit 不接管送审方的版本、封板与分发」。
k3dit 出意图与证据，落树与落账归消费方——契约＝内容哈希，实现＝各自的 git。

纪律（全部 fail-clear，不猜）：
- 包结构版本不认 ⇒ 拒（旧/异版包不得按本版布局解释）；
- `status != closed` ⇒ 拒（`incomplete`/`partial` 不得当"已审"）；
- 工作树不干净 ⇒ 拒（别把别人的在途改动卷进审计产物）；
- 只应用 `manifest.apply_order` 里**实际存在**的补丁（k3dit 仓 0028 §2.5 第 4 条）。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

#: k3dit 交付包**结构**版本白名单（认不出即 fail-clear；见 k3dit 仓 0028 §2.5 第 7 条）。
SUPPORTED_BUNDLE_VERSIONS = (1,)

#: 环境变量：显式指定 k3dit 可执行（argv 列表中的第一段）。
K3DIT_ENV = "K3DIT_BIN"


def find_k3dit(workspace: Path) -> Optional[List[str]]:
    """定位 k3dit：`K3DIT_BIN` > PATH > 兄弟仓 `.venv` > 兄弟仓 zipapp。找不到 → None。"""
    env = (os.environ.get(K3DIT_ENV) or "").strip()
    if env and Path(env).is_file():
        return [env]
    found = shutil.which("k3dit")
    if found:
        return [found]
    for cand in (workspace.parent / "k3dit" / ".venv" / "bin" / "k3dit",
                 workspace / ".venv" / "bin" / "k3dit",
                 workspace.parent / "k3dit" / "dist" / "k3dit.pyz"):
        if cand.is_file():
            return [str(cand)]
    return None


def _run(argv: List[str], cwd: Path, timeout: int, env: Optional[Dict[str, str]] = None) -> Tuple[int, str]:
    try:
        proc = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 124, f"{exc}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _last_json(text: str) -> Optional[dict]:
    """k3dit 的 json 载荷在最后一行（前面可能有过程日志/诊断）。"""
    for line in reversed((text or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if isinstance(data, dict):
                return data
    return None


def run_path_audit(workspace: Path, out: Path, *, mode: str = "full", pins: str = "inplace",
                   scope: str = "", timeout: int = 3600, k3dit: Optional[List[str]] = None) -> dict:
    """跑 k3dit 路径入口（工具调用）。`mode`＝工具运行模式（full / audit-only）；
    `pins`＝钉的落地形态（inplace＝钉留树 / artifact＝钉只随包）；
    `scope`＝送审范围（**逗号分隔**；空串＝不传，用 k3dit 自己的缺省）。返回 {ok, rc, out, payload, detail}。"""
    argv0 = k3dit or find_k3dit(workspace)
    if not argv0:
        return {"ok": False, "rc": 127, "detail": f"找不到 k3dit（设 {K3DIT_ENV} 或装到 PATH/兄弟仓）"}
    argv = [*argv0, "audit", "--path", str(workspace), "--out", str(out),
            "--mode", mode, "--pins", pins, "--format", "json"]
    if scope:
        argv += ["--scope", str(scope)]
    rc, text = _run(argv, workspace, timeout, env=_tool_env(workspace, argv0))
    payload = _last_json(text)
    if rc not in (0, 3):
        return {"ok": False, "rc": rc, "out": str(out), "detail": text.strip()[-400:],
                "payload": payload or {}}
    return {"ok": bool(payload), "rc": rc, "out": str(out), "payload": payload or {},
            "detail": text.strip()[-400:]}


def _tool_env(workspace: Path, argv0: List[str]) -> Dict[str, str]:
    """工具子进程的环境：**工具状态（hall root / ledger）不得落到外部被审仓**。

    真跑实测（2026-09-27）：在 k3dge 仓里跑 k3dge 自己的审计时，k3dit 把 `.k3dit/`（工作目录/席日志）与
    `ledger/jobs.json` 建到了**被审仓**里 ⇒ 工作区变脏 ⇒ 消费相位被自家 `DIRTY_TREE` 拒（而且这些是工具
    状态，不是审计产物）。规则：**外部被审仓 ⇒ 状态落缓存**（确定性路径 ⇒ 跨轮续用，`prior.json` 的旧债
    抑制仍然有效）；**工具自己家**（被审仓＝工具所在仓）⇒ 不动，保持仓库内状态的连续性。
    """
    import hashlib
    import tempfile

    env = {**os.environ}
    try:
        repo = Path(argv0[0]).resolve()
        for _ in range(3):      # <repo>/.venv/bin/k3dit → <repo>
            if (repo / "pyproject.toml").is_file() or (repo / ".git").exists():
                break
            repo = repo.parent
        if repo.resolve() == Path(workspace).resolve():
            return env          # 工具审自己：保持仓库内状态（连续性优先）
    except OSError:             # pragma: no cover
        pass
    cache = Path(os.environ.get("K3GE_AUDIT_CACHE") or (Path(tempfile.gettempdir()) / "k3ge-audit"))
    key = hashlib.sha1(str(Path(workspace).resolve()).encode("utf-8")).hexdigest()[:12]
    root = cache / f"k3dit-state-{key}"
    env["K3DIT_HALL_ROOT"] = str(root / "hall")
    env["K3DIT_LEDGER"] = str(root / "ledger" / "jobs.json")
    return env


def salvage_bundle(workspace: Path, out: Path, *, k3dit: Optional[List[str]] = None,
                   timeout: int = 300) -> dict:
    """工具失败/被墙钟掐断后**抢救**：`k3dit hall export --latest --out <out>`。

    用户裁定："超时也要出报告，不能让流程停在中间"。工具被杀时不会自己 `write_bundle`，但它账本里状态
    是全的（`report_markdown` 每步都写）⇒ 抢救出一只**自带「未完成导出」横幅 + `salvage:true`** 的包，
    消费侧据此走"部分落地 + 升级"。返回 {ok, rc, out, detail}。
    """
    argv0 = k3dit or find_k3dit(workspace)
    if not argv0:
        return {"ok": False, "rc": 127, "out": str(out), "detail": "找不到 k3dit（抢救不了）"}
    rc, text = _run([*argv0, "hall", "export", "--latest", "--out", str(out)],
                    Path(workspace), timeout, env=_tool_env(Path(workspace), argv0))
    ok = rc == 0 and (Path(out) / "manifest.json").is_file()
    return {"ok": ok, "rc": rc, "out": str(out),
            "detail": "" if ok else (text or "").strip()[-300:]}


def write_run_digest(out: Path, **facts: object) -> str:
    """**运行摘要**（用户裁定 ok）：`<out>/run-digest.json` —— "这轮怎么跑的 / 为什么停"。

    为什么随产物留：席日志与账本在**工具状态目录**里（可能被清理/换机），摘要随包留存 ⇒ 事后仍能看出
    问题出在哪（轮次/打回/封顶/未关/用量/抢救是否发生/工具状态目录）。
    """
    import datetime
    import json as _json

    data = {"written_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), **facts}
    try:
        Path(out).mkdir(parents=True, exist_ok=True)
        dst = Path(out) / "run-digest.json"
        dst.write_text(_json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        return str(dst)
    except OSError:      # pragma: no cover - 摘要写不出不该挡住主流程
        return ""


def verify_bundle(bundle: Path, *, expect_input: str = "", require_closed: bool = False,
                  accept_baseline_drift: str = "") -> dict:
    """**消费侧独立验收**（不调产出方）：报告完备性 + 本地闭环 + 内容哈希链。

    实现见 `k3dge.engine.audit_verify`。**不由产出方自证**：`k3dit audit --verify` 是产出方的自查，
    拿去当闸等于"自己批自己"（ADR-0012：产物 + **消费者** + 到达）。
    """
    from k3dge.engine import audit_verify

    res = audit_verify.verify_bundle_local(bundle, expect_input=expect_input, require_closed=require_closed,
                                           accept_baseline_drift=accept_baseline_drift)
    return {"ok": bool(res.get("ok")), "errors": list(res.get("errors") or []),
            "baseline_tree_hash": str((res.get("facts") or {}).get("baseline") or ""),
            "detail": "" if res.get("ok") else "; ".join(res.get("errors") or [])[:400],
            "local": res}


def bundle_facts(bundle: Path) -> dict:
    """读包内**机器可读契约面**（缺/坏 ⇒ 空值，由调用方 fail-clear）。"""
    man_p = Path(bundle) / "manifest.json"
    if not man_p.is_file():
        return {}
    try:
        man = json.loads(man_p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return {}
    if not isinstance(man, dict):
        return {}
    return {"bundle_version": man.get("bundle_version"), "status": man.get("status"),
            "unclosed": man.get("unclosed"), "apply_order": list(man.get("apply_order") or []),
            "patches": list(man.get("patches") or []), "pins": man.get("pins") or {},
            "flow": man.get("flow") or {}, "coverage": man.get("coverage") or {},
            "input": man.get("input"), "mode": man.get("mode"), "job_id": man.get("job_id"),
            "git_head": man.get("git_head") or ""}


def bundle_digest(bundle: Path) -> str:
    """包的**内容摘要**（排序后的 rel:sha256）——封版提交里记它，可核"审的是哪只包"。"""
    bundle = Path(bundle)
    rows: List[str] = []
    for p in sorted(bundle.rglob("*")):
        if p.is_file():
            rows.append(f"{p.relative_to(bundle).as_posix()}:{hashlib.sha256(p.read_bytes()).hexdigest()}")
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def _git(workspace: Path, *argv: str) -> Tuple[int, str]:
    return _run(["git", "-C", str(workspace), *argv], workspace, 120)


def _apply_sequential(target: Path, bundle: Path, order: List[str]) -> dict:
    """在 `target` 上按序 `git apply`（每条先 `--check`）。

    顺序是**契约的一部分**：`pins.patch`（标注层）的上下文建立在 `fix.patch`（语义层）之后，
    所以**不能**先对所有补丁各做一次 `--check`（那是在原树上验第二条，必然失败）；
    必须"check→apply→check→apply"。
    """
    done: List[str] = []
    for name in order:
        patch = Path(bundle) / name
        if not patch.is_file():
            return {"ok": False, "error": f"PATCH_MISSING:{name}", "applied": done}
        rc, out = _git(target, "apply", "--check", str(patch))
        if rc != 0:
            return {"ok": False, "error": f"APPLY_CHECK_FAILED:{name}", "detail": out.strip()[-300:],
                    "applied": done}
        rc, out = _git(target, "apply", str(patch))
        if rc != 0:
            return {"ok": False, "error": f"APPLY_FAILED:{name}", "detail": out.strip()[-300:],
                    "applied": done}
        done.append(name)
    rc, names = _git(target, "status", "--porcelain")
    files = sorted(ln[3:].strip() for ln in names.splitlines() if ln.strip()) if rc == 0 else []
    return {"ok": True, "files": files, "applied": done}


def _dry_run_via_worktree(workspace: Path, bundle: Path, order: List[str]) -> dict:
    """在**临时 worktree** 上顺序打一遍（不动工作树、不动索引、不动历史）。

    为什么用 worktree 而不是 `--check`：见 `_apply_sequential` 的顺序理由；worktree 是 git 原生
    的"零副作用副本"，比拷树便宜也比"先真打再回滚"安全（失败时工作树仍无改动）。
    """
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="k3dge-apply-dry-"))
    wt = tmp / "wt"
    rc, out = _git(workspace, "worktree", "add", "--detach", "-q", str(wt), "HEAD")
    if rc != 0:
        return {"ok": False, "error": "WORKTREE_UNAVAILABLE", "detail": out.strip()[-200:]}
    try:
        res = _apply_sequential(wt, bundle, order)
        if res["ok"]:
            res["files"] = res.get("files") or []
        return res
    finally:
        _git(workspace, "worktree", "remove", "--force", str(wt))
        shutil.rmtree(tmp, ignore_errors=True)


def apply_bundle(workspace: Path, bundle: Path, *, dry_run: bool = False,
                 allow_dirty: bool = False, exclude: Optional[List[str]] = None,
                 exclude_hunks: Optional[Dict[str, List[int]]] = None) -> dict:
    """落补丁：先 `git apply`（精确）；打不上则**三路合并**（主干已前进时的正道）。

    两条策略的差别只在"怎么把补丁贴到当前树上"：结果都要过同一道消费侧验收与同一套提交。
    `exclude`＝显式排除某些文件（例如"这条修复与当前测试期望冲突，需人工重做"）——不做猜测。
    """
    facts = bundle_facts(bundle)
    order = facts.get("apply_order") or []
    if not order:
        return {"ok": True, "applied": [], "files": [], "dry_run": dry_run,
                "detail": "apply_order 为空（无补丁要打）"}
    rc, _ = _git(workspace, "rev-parse", "--git-dir")
    if rc != 0:
        return {"ok": False, "error": "NOT_A_REPO", "detail": f"{workspace} 不是 git 仓库"}
    rc, dirty = _git(workspace, "status", "--porcelain")
    if rc == 0 and dirty.strip() and not allow_dirty:
        return {"ok": False, "error": "DIRTY_TREE",
                "detail": "工作树不干净，先提交或 stash（审计产物不得与在途改动混在一起）",
                "dirty": dirty.strip().splitlines()[:10]}
    # **有 hunk 级剔除要求时不许走"精确 git apply"快路**：那条路会把未关项所在 hunk 一起落进去
    #（真跑/测试实测：`git apply` 成功 ⇒ 过滤从未发生 ⇒ 未验证的改动进了主干）。一律走合并路径。
    pre = {"ok": False, "detail": "（有 hunk 级剔除要求 ⇒ 强制走合并路径）"} if exclude_hunks else \
        _dry_run_via_worktree(workspace, bundle, order)
    if pre.get("ok"):
        if dry_run:
            return {"ok": True, "applied": order, "files": pre.get("files") or [], "dry_run": True,
                    "strategy": "git-apply", "excluded": sorted({str(x) for x in (exclude or [])})}
        res = _apply_sequential(workspace, bundle, order)
        if res.get("ok"):
            return {"ok": True, "applied": order, "files": res.get("files") or [], "dry_run": False,
                    "strategy": "git-apply", "excluded": sorted({str(x) for x in (exclude or [])})}
    # `git apply` 打不上**不等于修复不可用**：补丁是对审计当时的基线生成的，而主干可能已经往前走
    #（落钉、别的修复、重构）。两侧信息都全 ⇒ 退到**三路合并**（base＝包的可重放基线）。
    # **结构性**失败（补丁缺/不是仓/脏树/无 worktree）不该退合并——那不是"打不上"，是输入不对。
    if str(pre.get("error") or "").split(":")[0] in {"PATCH_MISSING", "NOT_A_REPO", "DIRTY_TREE",
                                                     "WORKTREE_UNAVAILABLE"}:
        return {"ok": False, "error": pre.get("error"), "detail": pre.get("detail", ""),
                "phase": "dry-run", "applied": pre.get("applied") or []}
    got = _apply_sequential_merged(workspace, bundle, exclude=exclude, dry_run=dry_run,
                                   exclude_hunks=exclude_hunks)
    if got.get("ok"):
        return {"ok": True, "applied": order, "files": got.get("files") or [], "dry_run": dry_run,
                "strategy": "three-way-merge", "excluded": got.get("excluded") or [],
                "dropped_hunks": got.get("dropped_hunks") or {},
                "post_apply_check": got.get("post_apply_check") or {},
                "detail": f"`git apply` 打不上（{(pre.get('detail') or '')[:100]}）⇒ 三路合并"
                          f"{'（试跑，未落）' if dry_run else '成功'}"}
    return {"ok": False, "error": got.get("error") or pre.get("error") or "MERGE_FAILED",
            "detail": got.get("detail") or pre.get("detail", ""),
            "phase": "merge", "applied": [], "conflicts": got.get("conflicts") or []}


def _apply_sequential_merged(workspace: Path, bundle: Path, *, exclude=None, dry_run: bool = False,
                             exclude_hunks: Optional[Dict[str, List[int]]] = None) -> dict:
    """三路合并落补丁（在**临时 worktree** 里先做一遍并跑声明的落库后校验，再就地写）。

    返回 {ok, files, excluded, conflicts, detail}。校验失败/有冲突 ⇒ 不写工作区（fail-clear）。
    """
    import tempfile

    from k3dge.engine import audit_merge

    tmp = Path(tempfile.mkdtemp(prefix="k3dge-merge-dry-"))
    wt = tmp / "wt"
    rc, out = _git(workspace, "worktree", "add", "--detach", "-q", str(wt), "HEAD")
    if rc != 0:
        return {"ok": False, "error": "WORKTREE_UNAVAILABLE", "detail": out.strip()[-200:]}
    try:
        res = audit_merge.merge_into(wt, bundle, exclude=exclude or ())
        if not res.get("ok"):
            label = "合并冲突" if res.get("conflicts") else "合并失败"
            return {"ok": False, "error": "MERGE_FAILED", "conflicts": res.get("conflicts") or [],
                    "detail": f"{label}：{', '.join((res.get('conflicts') or [])[:6])} {res.get('detail', '')}".strip()}
        files = []
        for rel, text in (res.get("merged") or {}).items():
            p = wt / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            files.append(rel)
        # **hunk 级剔除未关项那几段**（用户裁定："已修的为什么不能落，不是 git 管理吗？"）：git 本是按 hunk 的
        # ⇒ 只把与未关项位置重叠的 hunk 反向应用掉，同文件里的其它修复**照落**（文件级排除会把它们一起挡掉）。
        dropped: Dict[str, list] = {}
        if exclude_hunks:
            from k3dge.engine.audit_merge import hunks_overlapping

            for rel, lines in sorted(exclude_hunks.items()):
                if rel not in files:
                    continue
                src = Path(bundle) / "fix.patch"
                if not src.is_file():
                    continue
                sel = hunks_overlapping(src.read_text(encoding="utf-8"), rel, list(lines))
                if not sel.get("patch"):
                    continue
                tmpf = wt / ".k3dge-drop.patch"
                tmpf.write_text(str(sel["patch"]), encoding="utf-8")
                rc, out = _git(wt, "apply", "-R", "-p1", str(tmpf))
                tmpf.unlink(missing_ok=True)
                if rc != 0:
                    return {"ok": False, "error": "HUNK_EXCLUDE_FAILED", "conflicts": [rel],
                            "detail": f"{rel}: 未关项所在 hunk 剔不出去（{out.strip()[:160]}）⇒ 不落地（fail-close）"}
                dropped[rel] = sel.get("dropped") or []
        # 钉（标注层，纯增量）：正向应用；打不上就对**该文件**并集合并（"两边都加钉"的正解＝两枚都留）
        pins = str(res.get("pins_patch") or "")
        if pins:
            rc, out = _git(wt, "apply", "-p1", str(Path(bundle) / pins))
            if rc != 0:
                from k3dge.engine import audit_merge

                for rel in sorted(audit_merge._rels_of_patch(Path(bundle), pins)):
                    u = audit_merge.union_pins(wt, Path(bundle), rel)
                    if not u.get("ok"):
                        return {"ok": False, "error": "PINS_MERGE_FAILED", "conflicts": [rel],
                                "detail": f"{rel}: 钉并集失败 {u.get('detail', '')}"}
                    (wt / rel).parent.mkdir(parents=True, exist_ok=True)
                    (wt / rel).write_text(str(u["text"]), encoding="utf-8")
                    if rel not in files:
                        files.append(rel)
        if dry_run:
            return {"ok": True, "files": files, "excluded": res.get("excluded") or [],
                    "conflicts": [], "post_apply_check": {"cmd": "", "ok": True,
                                                          "detail": "dry-run：不跑落库后校验"}}
        # 就地写（含钉那一步的结果）⇒ 落库后校验**在工作区**跑（venv/钩子都在那；临时 worktree 里没有）
        # ⇒ 不过就把刚写的这几个文件**回滚**（树本来是干净的：`DIRTY_TREE` 已挡）并 fail-clear。
        for rel in files:
            p = workspace / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(wt / rel, p)
        check = _post_apply_check(workspace, workspace)
        if check.get("cmd") and not check.get("ok"):
            # 回滚：合并写进去的文件 **＋ 投影**（声明的校验可能跑了 `k3dge sync/index` 之类的投影刷新；
            # 合并被回滚后那些投影也不再成立 ⇒ 一起退，别留半套状态）
            if files:
                _git(workspace, "checkout", "--", *files)
            if (workspace / "docs" / "generated").is_dir():
                _git(workspace, "checkout", "--", "docs/generated")
            return {"ok": False, "error": "POST_APPLY_CHECK_FAILED", "conflicts": [],
                    "detail": f"落库后校验未过（已回滚 {len(files)} 个文件）：{check.get('cmd')} ⇒ "
                              f"{check.get('detail')}", "files": []}
        return {"ok": True, "files": files, "excluded": res.get("excluded") or [],
                "conflicts": [], "post_apply_check": check, "dropped_hunks": dropped}
    finally:
        _git(workspace, "worktree", "remove", "--force", str(wt))
        shutil.rmtree(tmp, ignore_errors=True)


def _post_apply_check(root: Path, workspace: Path) -> dict:
    """跑**声明面**的落库后校验（`[roles.audit] post_apply_check`）：把"修复落进主干必须过消费仓自己的
    测试"从"靠人记得跑"变成流程的一步。未声明 ⇒ 跳过（如实报 `cmd=''`）。"""
    cmd = ""
    try:
        import tomllib

        data = tomllib.loads((Path(workspace) / ".agent" / "pipeline.toml").read_text(encoding="utf-8"))
        cmd = str(((data.get("roles") or {}).get("audit") or {}).get("post_apply_check") or "")
    except Exception:
        cmd = ""
    if not cmd:
        return {"cmd": "", "ok": True, "detail": "未声明 post_apply_check（跳过）"}
    rc = subprocess.run(["/bin/sh", "-c", cmd], cwd=root, capture_output=True)
    tail = ((rc.stdout or b"") + (rc.stderr or b"")).decode("utf-8", "replace").strip()[-400:]
    return {"cmd": cmd, "ok": rc.returncode == 0, "rc": rc.returncode, "detail": tail}


#: 升级标记（写在报告**验证**列；k3ge 自己写、自己读 ⇒ 单源）：
#:   `UNCLOSED`＝未闭环（转人工，封板判据须为空）；`NOTLANDED`＝声称已修但本次没落（--exclude）。
ESCALATION_UNCLOSED = "待验：未闭环（转人工）"
ESCALATION_NOTLANDED = "升级：本次未落"
ESCALATION_MARKERS = (ESCALATION_UNCLOSED, ESCALATION_NOTLANDED)


def reconcile_report_rows(body: str, excluded: Optional[List[str]] = None,
                          escalated: Optional[List[str]] = None) -> Dict[str, object]:
    """报告行 ↔ **实际落了什么/未关什么**的机械对账（写在**验证**列，**不动状态列**）。

    用户裁定（2026-09-27）：未关项**不要**改成"待修"，而是在**验证**列分配状态；升级由 **k3dge 的审后闸**
    报出来（k3dit 里没人看得到升级）。所以：
      - 位置列指向**被排除文件**的行（`--exclude`／未关项所在文件 ⇒ 本次没落）⇒ 验证列加
        `升级：本次未落（--exclude）待人工`；
      - 未关 finding（`escalated`）⇒ 验证列加 `待验：未闭环（转人工）`。
    状态列保持产出方原样（判定面要的是"它在报告里怎么说的"＋我们的升级注记）。
    返回 {body, changed, ids}。表头异常 ⇒ 原样返回（不冒险改坏报告）。
    """
    excluded = [str(x) for x in (excluded or []) if str(x).strip()]
    esc = {str(x) for x in (escalated or []) if str(x).strip()}
    if (not excluded and not esc) or not (body or "").strip():
        return {"body": body, "changed": 0, "ids": []}
    from k3dge.engine.report_table import parse_rows

    lines = body.splitlines()
    header, rows = parse_rows(body)
    if not header or "验证" not in header or "位置" not in header:
        return {"body": body, "changed": 0, "ids": []}
    try:
        i_ver = header.index("验证") + 1
        i_id = header.index("ID") + 1
        i_pos = header.index("位置") + 1
    except ValueError:
        return {"body": body, "changed": 0, "ids": []}
    changed: List[str] = []
    for idx, row in rows:
        rid = str(row.get("ID") or "").strip()
        f = str(row.get("位置") or "").split(":")[0].strip()
        mark = ""
        if rid and rid in esc:
            mark = ESCALATION_UNCLOSED
        elif f and f in excluded and str(row.get("状态") or "").strip() == "已修":
            # 只标"声称已修却没落"的行（"有意留"本无东西可落 ⇒ 标它等于误导）
            mark = ESCALATION_NOTLANDED + "（`--exclude`）待人工"
        if not mark:
            continue
        parts = lines[idx].split("|")
        if len(parts) <= max(i_ver, i_id, i_pos):
            continue
        if mark not in parts[i_ver]:
            parts[i_ver] = (parts[i_ver].rstrip() + ("；" if parts[i_ver].strip() else " ") + mark + " ")
        lines[idx] = "|".join(parts)
        changed.append(rid or str(row.get("ID") or ""))
    return {"body": "\n".join(lines) + "\n", "changed": len(changed), "ids": changed}


def land_report(workspace: Path, milestone_id: str, out: Path, *,
                extra_files: Optional[List[str]] = None, why: str = "", note: str = "",
                excluded: Optional[List[str]] = None,
                escalated: Optional[List[str]] = None) -> dict:
    """**唯一的"落报告"入口**：包内 `report.md` → `docs/reviews/` + 重生 docs 投影 + **一次提交**。

    为什么合并（2026-09-27 流程体检）：这条三步序列此前写在**两处**（腿的正常路 + 腿的拒绝路
    `_land_report_even_on_refusal`），而**手动入口 `k3dge audit bundle` 两处都没有** ⇒ 同一动作三种形态，
    其中"手动入口"那种**没有效果**（报告不落盘、不提交 ⇒ 判定面看不到）。三个入口现在共用本函数。
    `extra_files`＝同一次提交里并入的已落文件（落补丁时用：报告与补丁同一次提交，封版相位再写 trailer）。
    返回 {ok, report, commit, error}。**失败不抛**：调用方按 `error` 决定拒绝还是继续。
    """
    report_src = Path(out) / "report.md"
    if not report_src.is_file():
        return {"ok": False, "error": "REPORT_MISSING", "detail": f"包内缺 report.md（{out}）", "report": "", "commit": ""}
    try:
        from k3dge.engine.milestone_audit import persist_external_audit_report

        body = report_src.read_text(encoding="utf-8")
        # **先对账再落盘**：被排除文件的 `已修` 行改 `待修` ⇒ 判定面（封板判据读报告 `待修`）不会被虚报糊弄。
        rec = reconcile_report_rows(body, excluded, escalated)
        body, _rec_changed = str(rec["body"]), int(rec["changed"])
        if _rec_changed:
            note = (f"| 对账 | 报告有 {_rec_changed} 行在**验证**列被标升级/未验（未关或未落）："
                    f"{', '.join(rec['ids'][:8])} |\n| --- | --- |\n" + (note or ""))
        if note:      # 诚实说明（例如"本批修复经三路合并落树；排除 X（其修复与主干/现测试冲突，需人工重做）"）
            body = body.rstrip("\n") + "\n\n" + note.strip() + "\n"
        report_dst = persist_external_audit_report(workspace, milestone_id, body,
                                                   scope="k3dit-bundle", kind="audit")
    except Exception as exc:      # pragma: no cover - 落地器异常不该吞
        return {"ok": False, "error": "REPORT_PERSIST_FAILED", "detail": str(exc), "report": "", "commit": ""}
    rel = report_dst.relative_to(workspace).as_posix()
    # **重生全部确定性投影**（不是只修一处）：落报告与落钉都会让投影过期 —— `docs-index`（文档面）
    # 与 `symbol-index`（`k3dge where` 的判据面）。真跑实测两次踩：先只重生 docs-index ⇒ 提交被
    # `DOC_INDEX_STALE` 拦；补上后又撞 `SYMBOL_INDEX_STALE`。所以这里跑与 `k3dge sync` + `k3dge index`
    # **同一对写入器**，再按 `docs/generated/` 的 git 差异把变更文件并入同一次提交（不扫全仓，避免卷进别人的改动）。
    import contextlib
    import io

    log = io.StringIO()
    try:
        # 两个写入器**都属于 engine 域**（`doc_catalog` / `search`）⇒ 不 import `sync`（域方向：sync→engine，
        # 反向会被 `DOMAIN_IMPORT_VIOLATION` 拦，且那确实是耦合方向错了）。落报告/落钉会过期的投影就是这两个：
        # `docs-index`（文档面）、`symbol-index`（`k3dge where` 判据面）；契约面（specs）不受注释级改动影响。
        from k3dge.engine.doc_catalog import write_docs_index
        from k3dge.engine.search import write_symbol_index

        with contextlib.redirect_stdout(log):          # 投影器会打日志 ⇒ 收起来，别污染调用方的 stdout（JSON）
            write_docs_index(workspace)
            write_symbol_index(workspace)
    except Exception as exc:
        return {"ok": False, "error": "PROJECTION_FAILED",
                "detail": f"重生投影失败：{exc}", "report": rel, "commit": "",
                "projection_log": log.getvalue()[-400:]}
    proj: List[str] = []
    # 收集面＝**整个 `docs/`**：落报告会动 `docs/reviews/`，落代码会动 `docs/generated/`（投影）
    # 与 `docs/specs/`（契约哈希 ⇒ `k3dge sync` 回写，真跑实测漏在提交外 ⇒ 钩子按"哈希不一致"拦下）。
    # 树在本步之前是干净的（`DIRTY_TREE` 已挡）⇒ `docs/` 下的改动必是本轮产物。
    rc, out = _git(workspace, "status", "--porcelain", "-uall", "--", "docs")
    if rc == 0:
        proj = [line[3:].strip() for line in out.splitlines() if line.strip()]
    files = [*([f for f in (extra_files or []) if f]), rel, *proj]
    # 里程碑 id **原样用**（`M0` 就写 `M0`）：别再前置 `M`——真跑实测把 `M0` 写成了 `MM0`。
    msg = (f"docs(audit): {milestone_id} 审计报告落盘（{why[:80]}）" if why
           else f"fix(audit): k3dit 交付包落树（{why or 'k3dit-bundle'}）")
    sha, cerr = commit_applied(workspace, msg, files)
    return {"ok": not cerr, "error": "COMMIT_FAILED" if cerr else "", "detail": cerr,
            "report": rel, "commit": sha, "files": files,
            "reconciled_rows": _rec_changed,
            "projection": proj, "projection_log": log.getvalue()[-400:]}


def commit_applied(workspace: Path, message: str, files: List[str]) -> Tuple[str, str]:
    """提交**已落的这些文件**（不用 `add -A`：别把工作区其它改动卷进审计提交）。返回 `(sha, 错误)`。

    不写 `Audit-*` trailer——那些由封版相位 3 一次写清（判据只认 git 事实，ADR-0004 §2.1.10）。

    ⚠️ 报错**必须带出来**（2026-09-27 真跑）：此前失败只 `return ""` ⇒ 腿只表现为"没提提交"，
    真实原因（本地钩子 `DOC_INDEX_STALE` 拦下）被吞掉，树还被留在 staged 态（下一次跑又被 `DIRTY_TREE` 挡）。
    """
    files = [f for f in (files or []) if f]
    if not files:
        return "", ""
    rc, out = _git(workspace, "add", "--", *files)
    if rc != 0:
        return "", f"git add 失败：{out.strip()[-300:]}"
    if _git(workspace, "diff", "--cached", "--quiet")[0] == 0:
        return "", ""      # 没有可提交的内容（报告内容未变/投影已同步）⇒ no-op，**不是失败**
    rc, out = _git(workspace, "-c", "user.email=k3dge@local", "-c", "user.name=k3dge",
                   "commit", "-q", "-m", message)
    if rc != 0:
        return "", f"git commit 失败：{out.strip()[-400:]}"
    rc, out = _git(workspace, "rev-parse", "HEAD")
    return (out.strip() if rc == 0 else ""), ""


def consume(workspace: Path, bundle: Path, *, dry_run: bool = False,
            k3dit: Optional[List[str]] = None, expect_input: Optional[str] = None,
            require_closed: bool = True, accept_baseline_drift: str = "",
            exclude: Optional[List[str]] = None, landing: str = "partial") -> dict:
    """**消费一只包**：验契约 → 输入身份 → 自证 → 落补丁。

    `expect_input` 非空时校验 `manifest.input` 与它同指一处（realpath 比较）——包的输入身份是
    k3dit 仓 0028 §2.10 的"同一版"判据，拿错包（为别的目录做的）多半意味着补丁要打到别的树上。
    返回 {ok, facts, verify, apply, digest, error?}。"""
    bundle = Path(bundle)
    bundle = Path(bundle)
    facts = bundle_facts(bundle)
    if not facts:
        return {"ok": False, "error": "NO_MANIFEST", "detail": f"{bundle}/manifest.json 缺失或不可解析"}
    ver = facts.get("bundle_version")
    if ver not in SUPPORTED_BUNDLE_VERSIONS:
        return {"ok": False, "error": "BUNDLE_VERSION_UNSUPPORTED", "facts": facts,
                "detail": f"bundle_version={ver!r} 不在白名单 {SUPPORTED_BUNDLE_VERSIONS}"}
    if expect_input:
        try:
            got = Path(str(facts.get("input") or "")).resolve()
            want = Path(str(expect_input)).resolve()
            if got != want:
                return {"ok": False, "error": "INPUT_MISMATCH", "facts": facts,
                        "detail": f"包是为 {got} 做的，而当前目标是 {want}（用 --into 指定目标目录）"}
        except OSError:      # pragma: no cover - 路径解析异常不该拦住消费
            pass
    # **闭环由 k3dge 自己从 findings 算**（`require_closed=False` 只给纯审计：它的 `status=partial` 是设计，
    # 钉留树＝待修队列）。产出方自报的 `status` **不作判据**，只作交叉核（不一致会被验收报出来）。
    # 未闭环**不再整包拒**（用户裁定 乙：部分落地）⇒ 验收先按"不要求闭环"跑，未关项改成"排除其所在文件"
    # 并在结果里**记升级**（由 k3dge 的审后闸报出，k3dit 里没人看得到升级）。
    verified = verify_bundle(bundle, expect_input=str(expect_input or ""), require_closed=False,
                             accept_baseline_drift=accept_baseline_drift)
    if not verified.get("ok"):
        return {"ok": False, "error": "VERIFY_FAILED", "facts": facts, "verify": verified,
                "detail": "消费侧验收未通过：" + "; ".join(verified.get("errors") or [])[:400]}
    local = (verified.get("local") or {})
    unclosed = [str(x) for x in (local.get("unclosed") or [])]
    unclosed_files: List[str] = []
    unclosed_hunks: Dict[str, List[int]] = {}
    if unclosed:
        try:
            items = json.loads((Path(bundle) / "findings.json").read_text(encoding="utf-8"))
            rows = items.get("items") if isinstance(items, dict) else items
            for it in (rows or []):
                if str((it or {}).get("id") or "") in unclosed:
                    loc = str((it or {}).get("location") or "")
                    f, _sep, ln = loc.partition(":")
                    f = f.strip()
                    if f:
                        unclosed_files.append(f)
                        if ln.strip().isdigit():
                            unclosed_hunks.setdefault(f, []).append(int(ln.strip()))
        except Exception:      # pragma: no cover - 读不出就 fail-close（宁可不落也不乱落）
            unclosed_files, unclosed_hunks = [], {}
    _landing = str(landing or "partial")
    if _landing not in ("closed-only", "partial", "all"):
        return {"ok": False, "error": "BAD_LANDING", "facts": facts,
                "detail": f"landing={landing!r} 不合法（closed-only / partial / all）"}
    if unclosed and _landing == "closed-only":
        # **调用方选了最严策略**：未关项 ⇒ 不落（这等价于旧行为；策略归声明面/CLI，k3ge 只执行）
        return {"ok": False, "error": "VERIFY_FAILED", "facts": facts, "verify": verified,
                "detail": f"未闭环（消费侧算）：{unclosed[:5]}（`landing=closed-only` ⇒ 不落）"}
    if unclosed and _landing == "all":
        unclosed_hunks = {}      # 全落：连未关项那几段也落（但下面仍按行标升级 ⇒ 封板被挡）
    if unclosed and not unclosed_hunks and _landing == "partial":
        # **解不出未关项所在文件 ⇒ 不许部分落地**（否则会把未关项的修复一起落进去＝虚报）。fail-close。
        return {"ok": False, "error": "UNRESOLVED_UNCLOSED", "facts": facts, "verify": verified,
                "detail": f"未关 {len(unclosed)} 项但 findings 里取不到 `location` ⇒ 无法安全排除其文件，"
                          f"不做部分落地（{', '.join(unclosed[:5])}）"}
    ex_all = sorted({str(x) for x in (exclude or [])})      # 未关项走 **hunk 级**（不再整文件排除）
    applied = apply_bundle(workspace, bundle, dry_run=dry_run, exclude=ex_all,
                           exclude_hunks=unclosed_hunks or None)
    if not applied.get("ok"):
        return {"ok": False, "error": applied.get("error"), "facts": facts, "verify": verified,
                "apply": applied, "detail": applied.get("detail", "")}
    return {"ok": True, "facts": facts, "verify": verified, "apply": applied,
            "digest": bundle_digest(bundle), "dry_run": dry_run,
            "partial": bool(unclosed), "escalated": unclosed, "unclosed_files": sorted(set(unclosed_files)),
            "unclosed_hunks": unclosed_hunks, "landing": _landing}
