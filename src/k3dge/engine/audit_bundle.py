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


def _run(argv: List[str], cwd: Path, timeout: int) -> Tuple[int, str]:
    try:
        proc = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
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


def run_path_audit(workspace: Path, out: Path, *, mode: str = "full", timeout: int = 3600,
                   k3dit: Optional[List[str]] = None) -> dict:
    """跑 k3dit 路径入口（cli 传输的实体）。返回 {ok, rc, out, payload, detail}。"""
    argv0 = k3dit or find_k3dit(workspace)
    if not argv0:
        return {"ok": False, "rc": 127, "detail": f"找不到 k3dit（设 {K3DIT_ENV} 或装到 PATH/兄弟仓）"}
    argv = [*argv0, "audit", "--path", str(workspace), "--out", str(out),
            "--mode", mode, "--format", "json"]
    rc, text = _run(argv, workspace, timeout)
    payload = _last_json(text)
    if rc not in (0, 3):
        return {"ok": False, "rc": rc, "out": str(out), "detail": text.strip()[-400:],
                "payload": payload or {}}
    return {"ok": bool(payload), "rc": rc, "out": str(out), "payload": payload or {},
            "detail": text.strip()[-400:]}


def verify_bundle(bundle: Path, *, k3dit: Optional[List[str]] = None,
                  timeout: int = 600) -> dict:
    """`k3dit audit --verify <bundle>`：包自证（反向重放 + 12 列 + findings↔报告）。"""
    argv0 = k3dit or find_k3dit(bundle)
    if not argv0:
        return {"ok": False, "detail": f"找不到 k3dit（设 {K3DIT_ENV}）"}
    rc, text = _run([*argv0, "audit", "--verify", str(bundle), "--format", "json"], bundle, timeout)
    payload = _last_json(text) or {}
    ok = bool(payload.get("ok")) and not payload.get("errors")
    return {"ok": ok, "rc": rc, "errors": payload.get("errors") or [],
            "baseline_tree_hash": payload.get("baseline_tree_hash") or "",
            "detail": "" if ok else text.strip()[-300:]}


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
                 allow_dirty: bool = False) -> dict:
    """按 `apply_order` 用**标准 `git apply`** 落补丁：先 worktree 试跑（原子化），再就地应用。"""
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
    pre = _dry_run_via_worktree(workspace, bundle, order)
    if not pre.get("ok"):
        return {"ok": False, "error": pre.get("error"), "detail": pre.get("detail", ""),
                "phase": "dry-run", "applied": pre.get("applied") or []}
    if dry_run:
        return {"ok": True, "applied": order, "files": pre.get("files") or [], "dry_run": True}
    res = _apply_sequential(workspace, bundle, order)
    if not res.get("ok"):
        # worktree 试跑已过 ⇒ 走到这里多为外部并发改动；如实报错并给出**已落清单**，不静默半途状态
        return {"ok": False, "error": res.get("error"), "detail": res.get("detail", ""),
                "phase": "apply", "applied": res.get("applied") or []}
    return {"ok": True, "applied": order, "files": res.get("files") or [], "dry_run": False}


def commit_applied(workspace: Path, message: str, files: List[str]) -> str:
    """提交**已落的这些文件**（不用 `add -A`：别把工作区其它改动卷进审计提交）。返回 sha 或 ""。

    不写 `Audit-*` trailer——那些由封版相位 3 一次写清（判据只认 git 事实，ADR-0004 §2.1.10）。
    """
    files = [f for f in (files or []) if f]
    if not files:
        return ""
    rc, _ = _git(workspace, "add", "--", *files)
    if rc != 0:
        return ""
    rc, _ = _git(workspace, "-c", "user.email=k3dge@local", "-c", "user.name=k3dge",
                 "commit", "-q", "-m", message)
    if rc != 0:
        return ""
    rc, out = _git(workspace, "rev-parse", "HEAD")
    return out.strip() if rc == 0 else ""


def consume(workspace: Path, bundle: Path, *, dry_run: bool = False,
            k3dit: Optional[List[str]] = None, expect_input: Optional[str] = None) -> dict:
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
    if str(facts.get("status") or "") != "closed":
        return {"ok": False, "error": "NOT_CLOSED", "facts": facts,
                "detail": f"status={facts.get('status')!r}（unclosed={facts.get('unclosed')}）"
                          f"——未闭环的包不得当已审"}
    argv0 = k3dit or find_k3dit(workspace)
    verified = verify_bundle(bundle, k3dit=argv0)
    if not verified.get("ok"):
        return {"ok": False, "error": "VERIFY_FAILED", "facts": facts, "verify": verified,
                "detail": "包自证未通过：" + "; ".join(verified.get("errors") or [])[:300]}
    applied = apply_bundle(workspace, bundle, dry_run=dry_run)
    if not applied.get("ok"):
        return {"ok": False, "error": applied.get("error"), "facts": facts, "verify": verified,
                "apply": applied, "detail": applied.get("detail", "")}
    return {"ok": True, "facts": facts, "verify": verified, "apply": applied,
            "digest": bundle_digest(bundle), "dry_run": dry_run}
