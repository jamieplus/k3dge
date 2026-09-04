"""Audit Bundle builder — 送检包的**内容构成**（`docs/protocols/peer_contract.md` §3）.

规则 08 切分：本模块只管"送什么"（范围/排除/脱敏/签名骨架/manifest）；
"放哪、怎么取"归 `engine/store.py`（git 对象库）。哈希=tree OID ⇒ 同内容必同基线。
peer 永不遍历消费仓文件系统；它拿到的只是调用方决定送出的快照。
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import tarfile
from pathlib import Path
from typing import Dict, List, Optional

OUTBOX_REL = ".k3dge/outbox"
CONFIG_REL = ".agent/bundle.toml"
#: 噪音默认排除（可被 .agent/bundle.toml 覆盖/追加）
DEFAULT_IGNORE = (
    "__pycache__", ".DS_Store", ".git", ".venv", "node_modules",
    "logs", "docs/generated", ".k3dge", ".agent",
)
#: 超过该体积绝不内联进 JSON-RPC 请求体（契约 §3：超量走 cas:// offloading）
MAX_INLINE_BYTES = 512 * 1024
_EPOCH = 0  # 确定性打包：归一 mtime/uid/uname


def load_bundle_config(workspace: Path) -> dict:
    """`.agent/bundle.toml`（可选）覆盖默认值。键：ignore / max_bytes / scrub_keys / mode / format。"""
    cfg: Dict = {
        "ignore": list(DEFAULT_IGNORE),
        "max_bytes": 8 * 1024 * 1024,
        "scrub_keys": [],
        "mode": "tree",
        "format": "tar",
    }
    p = workspace / CONFIG_REL
    if not p.is_file():
        return cfg
    try:
        import tomllib  # py3.11+
    except ModuleNotFoundError:  # pragma: no cover
        try:
            import tomli as tomllib  # type: ignore
        except ModuleNotFoundError:
            return cfg
    try:
        user = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return cfg
    if isinstance(user.get("ignore"), list):
        cfg["ignore"] = [str(x) for x in user["ignore"]]
    if isinstance(user.get("max_bytes"), int):
        cfg["max_bytes"] = user["max_bytes"]
    if isinstance(user.get("scrub_keys"), list):
        cfg["scrub_keys"] = [str(x) for x in user["scrub_keys"]]
    if user.get("mode") in ("tree", "diff"):
        cfg["mode"] = user["mode"]
    return cfg


def extract_signatures(source: str) -> str:
    """轻量 AST 头文件：只留类/函数签名与类型注解，去掉函数体（消除跨文件符号幻觉，契约 §3）。

    解析失败（非合法 Python）⇒ 返回空串，调用方退回全文。
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""
    src_lines = source.splitlines()
    out: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases) if node.bases else ""
            out.append(f"class {node.name}({bases}):" if bases else f"class {node.name}:")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else "def "
            try:
                args = ast.unparse(node.args)
            except Exception:  # pragma: no cover - defensive
                args = "..."
            ret = ""
            if node.returns is not None:
                try:
                    ret = f" -> {ast.unparse(node.returns)}"
                except Exception:  # pragma: no cover
                    ret = ""
            out.append(f"{prefix}{node.name}({args}){ret}: ...")
        elif isinstance(node, ast.AnnAssign) and isinstance(getattr(node, "target", None), ast.Name):
            try:
                out.append(f"{node.target.id}: {ast.unparse(node.annotation)}")
            except Exception:  # pragma: no cover
                pass
    return "\n".join(out) + ("\n" if out else "")


def _scrub(text: str, keys: List[str]) -> str:
    """出门前脱敏：命中 key 模式的字符串值替换为 <redacted>（契约 §3：不靠对方承诺不看）。"""
    for k in keys or []:
        text = re.sub(
            rf"(?im)^(\s*{re.escape(k)}\s*[:=]\s*).+$",
            r"\1<redacted>",
            text,
        )
    return text


def _is_ignored(rel: str, ignore: List[str]) -> bool:
    parts = Path(rel).parts
    return any(seg in ignore or seg.startswith(".") and seg not in (".") for seg in parts[:-1]) or \
        Path(rel).name in ignore


def pack_provenance(workspace: Path, cfg: dict) -> dict:
    """可复现性元数据：让两轮基线差异可归因（config 变了/ git 版本变了 ⇒ 说得清）。"""
    import subprocess
    cfgp = workspace / CONFIG_REL
    cfg_hash = hashlib.sha256((cfgp.read_bytes() if cfgp.is_file() else b"<defaults>")).hexdigest()[:12]
    try:
        gv = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip().split("\n")[0]
    except OSError:
        gv = "unknown"
    return {"config_digest": cfg_hash, "mode": cfg["mode"], "git": gv,
            "ignore": sorted(cfg["ignore"]), "scrub_keys": sorted(cfg["scrub_keys"])}


def build_bundle(workspace: Path, targets: List[str], milestone_id: Optional[str] = None,
                 prev_commit: Optional[str] = None) -> dict:
    """打一个确定性送检包，返回契约 §3 的引用结构。

    `targets` 是相对仓库根的路径（文件或目录）。签名骨架覆盖包内 `.py` 的本地依赖。
    """
    cfg = load_bundle_config(workspace)
    ignore = cfg["ignore"]

    files: Dict[str, bytes] = {}
    for t in targets:
        root = workspace / t
        if root.is_file():
            cand = [root]
        elif root.is_dir():
            cand = [p for p in sorted(root.rglob("*")) if p.is_file()]
        else:
            continue
        for p in cand:
            rel = p.relative_to(workspace).as_posix()
            if _is_ignored(rel, ignore):
                continue
            data = p.read_bytes()
            if len(data) > cfg["max_bytes"]:
                continue  # 单文件超限不入包（宁可缺，不可塞爆）
            if p.suffix in (".py", ".md", ".toml", ".json", ".txt", ".cfg", ".ini", ".yml", ".yaml"):
                try:
                    data = _scrub(data.decode("utf-8"), cfg["scrub_keys"]).encode("utf-8")
                except UnicodeDecodeError:
                    pass
            files[f"target/{rel}"] = data

    # 签名骨架：包内 .py 的本地 import 依赖（启发式：相对导入或仓库内可解析的顶层包）
    sigs: Dict[str, str] = {}
    for arc, data in list(files.items()):
        if not arc.endswith(".py"):
            continue
        try:
            tree = ast.parse(data.decode("utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        mods: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
            elif isinstance(node, ast.Import):
                mods.extend(a.name for a in node.names)
        for mod in mods:
            dotted = mod.replace(".", "/")
            cands = [workspace / "src" / (dotted + ".py"), workspace / (dotted + ".py"),
                     workspace / "src" / dotted / "__init__.py"]
            for cand in cands:
                if not cand.is_file():
                    continue
                rel = cand.relative_to(workspace).as_posix()
                if f"target/{rel}" not in files and rel not in sigs:
                    sigs[rel] = extract_signatures(cand.read_text(encoding="utf-8"))
                break

    manifest_files = [
        {"path": arc, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        for arc, data in sorted(files.items())
    ]
    manifest = {
        "bundle_version": 3,  # v3 = epoch commit 链 + bundle 文件（ADR-0026 §2.2/§2.3）
        "mode": cfg["mode"],
        "milestone_id": milestone_id or "",
        "pack_provenance": pack_provenance(workspace, cfg),
        "files": manifest_files,
        "signatures": sorted(sigs),
    }
    tree: Dict[str, bytes] = {"MANIFEST.json": (json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")}
    tree.update(files)
    for rel, text in sigs.items():
        tree[f"signatures/{rel}.sig"] = text.encode("utf-8")

    from k3dge.engine import store as _store

    st = _store.GitStore(workspace)
    if st.supports_sha256:
        snap = st.commit_snapshot(tree, job=milestone_id or "adhoc", prev_commit=prev_commit)
        oid = snap["tree"]
        digest = f"sha256:{oid}"
        bpath = workspace / ".k3dge" / "bundles" / f"{oid[:16]}.bundle"
        try:
            st.bundle_create(snap["commit"], bpath, has=None if prev_commit is None else prev_commit)
        except _store.StoreError:
            st.bundle_create(snap["commit"], bpath)  # 前置不可满足 ⇒ 回退全量包（形状不变，参数降级）
        bundle_file = bpath.relative_to(workspace).as_posix()
        size = sum(len(v) for v in tree.values())
        ref = f"cas://{digest}"
        path = None  # 权威对象在 store.git；bundle_file＝可搬运的封闭袋（ADR-0026 §2.2）
    else:  # 老 git 环境回退：确定性 tar（v1 路），ref/哈希格式不变
        import io as _io

        buf = _io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
            def _add(arc: str, data: bytes) -> None:
                info = tarfile.TarInfo(name=arc)
                info.size = len(data)
                info.mtime = _EPOCH
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mode = 0o644
                tar.addfile(info, _io.BytesIO(data))

            for arc, data in sorted(tree.items()):
                _add(arc, data)
        blob = buf.getvalue()
        digest = "sha256:" + hashlib.sha256(blob).hexdigest()
        size = len(blob)
        ref = f"cas://{digest}"
        outbox = workspace / OUTBOX_REL
        outbox.mkdir(parents=True, exist_ok=True)
        out = outbox / f"{digest.split(':')[1]}.tar"
        if not out.exists():
            out.write_bytes(blob)
        path = out.relative_to(workspace).as_posix()

    return {
        "ref": ref,
        "hash": digest,
        "commit": None if path else snap["commit"],
        "bundle_file": None if path else bundle_file,
        "mode": cfg["mode"],
        "format": "git-bundle" if path is None else "tar",
        "path": path,
        "size": size,
        "inline_ok": size <= MAX_INLINE_BYTES,
        "manifest": manifest,
    }
