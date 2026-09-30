"""提交 attestation：受管路径（`k3dge commit` / 进程 round work / 封版提交）写同一行，CI 全量验。

token = word(hash(secret + UTC 分钟窗 + tree))。有 `K3DGE_ATTEST_SECRET` 才是证明；
缺省常量只是威慑。不给任何提交类别开豁免——进程提交也必须带这一行。
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

PREFIX = "k3dge-commit: "
DEFAULT_SECRET = "k3dge-local-attest-v1"
WORDLIST = [
    "aura", "brick", "cedar", "delta", "ember", "flux", "glyph", "haven",
    "iris", "jolt", "kiwi", "lumen", "moss", "nexus", "onyx", "prism",
    "quill", "rune", "sage", "tide", "umber", "vault", "wisp", "xenon",
    "yarn", "zephyr",
]
LINE_RE = re.compile(r"^k3dge-commit: (.+?) @ (.+?) #([a-z]+)$")


_SECRET_WARNED = False


def secret() -> str:
    s = (os.environ.get("K3DGE_ATTEST_SECRET") or "").strip()
    if s:
        return s
    global _SECRET_WARNED
    if not _SECRET_WARNED:
        import sys

        _SECRET_WARNED = True
        # 回退常量写在源码里 ⇒ 谁都能算出期望词；CI 若配了真 secret，本地提交会**全量红**。
        # 两种情形必须在日志里可区分（"威慑-only" 不是 "证明"，ocr-198）。
        print("[ATTEST] WARN: K3DGE_ATTEST_SECRET 未设 ⇒ 本行是威慑（公开常量），不是证明。", file=sys.stderr)
    return DEFAULT_SECRET


def tree_hash(workspace: Path) -> str:
    r = subprocess.run(
        ["git", "write-tree"], cwd=str(workspace), capture_output=True, text=True
    )
    if r.returncode != 0:
        # git 失败必须出声：空 tree 混进 token ⇒ 生成的行永远验不过，报错还指向"非受管路径"（ocr-038）。
        raise RuntimeError(f"git write-tree failed in {workspace}: {(r.stderr or '').strip()}")
    return r.stdout.strip()


def utc_minute(when_iso: str):
    from datetime import datetime, timezone

    ts = (when_iso or "").strip()
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def window(when_iso: str) -> str:
    dt = utc_minute(when_iso)
    if dt is None:
        # `utc_minute` 明确容忍 None，这里也必须容忍：`None[:16]` 抛 TypeError，且畸形时间戳被
        # 静默当成一个"窗口"继续算 token ⇒ 报错文案指向"非受管路径"，掩盖真实故障（ocr-199）。
        return str(when_iso or "")[:16]
    return dt.strftime("%Y-%m-%dT%H:%M")


def windows(when_iso: str) -> List[str]:
    from datetime import timedelta

    dt = utc_minute(when_iso)
    if dt is None:
        return [str(when_iso or "")[:16]]
    base = dt.replace(second=0, microsecond=0)
    return [base.strftime("%Y-%m-%dT%H:%M"), (base - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")]


def token(workspace: Path, when_iso: str) -> str:
    digest = hashlib.sha256(f"{secret()}|{window(when_iso)}|{tree_hash(workspace)}".encode()).hexdigest()
    return WORDLIST[int(digest, 16) % len(WORDLIST)]


def line(workspace: Path, who: str = "") -> str:
    import getpass
    from datetime import datetime, timezone

    if not who:
        try:
            who = subprocess.run(
                ["git", "config", "user.name"], cwd=str(workspace),
                capture_output=True, text=True,
            ).stdout.strip()
        except OSError:
            who = ""
        if not who:
            who = getpass.getuser()
    when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"{PREFIX}{who} @ {when} #{token(workspace, when)}"


def append_to_message(workspace: Path, msg: str, who: str = "") -> str:
    """正文没有**合法** trailer 就补一行；有前缀但形状不对（伪造/过期）⇒ 去掉重写。

    旧实现 `if PREFIX in msg: return msg` 是子串判断：正文里引用一句 `k3dge-commit: ...`
    就足以让受管路径放弃署名；`--amend` 复用旧行时 tree 已变也不会重算 ⇒ CI 误红（ocr-200）。
    """
    body = msg or ""
    if any(LINE_RE.match(ln.strip()) for ln in body.splitlines()):
        return body
    kept = [ln for ln in body.splitlines() if not ln.strip().startswith(PREFIX)]
    trailer = line(workspace, who=who)
    cleaned = "\n".join(kept).rstrip()
    if not cleaned:
        return f"{trailer}\n"
    # 末段若已是 trailer 块（每行都 `Token: value`），署名**并进同一段**：另起一段会把别人的
    # 四键挤成倒数第二段 ⇒ `%(trailers)` 只读回署名，封版记录整体读不回（ocr-308）。
    last_para = [ln for ln in cleaned.split("\n\n")[-1].strip().splitlines() if ln.strip()]
    _TRAILER_SHAPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*: .*$")
    if last_para and all(_TRAILER_SHAPE.match(ln.strip()) for ln in last_para):
        return f"{cleaned}\n{trailer}\n"
    return f"{cleaned}\n\n{trailer}\n"


def verify_commit(workspace: Path, h: str) -> Tuple[bool, str]:
    # `h` 来自 CI 参数：不校验就拼进 argv ⇒ 以 `-` 开头的取值被 git 当**选项**解析（参数注入面），
    # 坏值还会让三条 git 命令各报一次难懂的错（393）。
    sha = str(h or "").strip()
    # 闭集形状判不了（调用方也传 `HEAD`/tag/`main^`），但**必须**挡掉：空值、以 `-` 开头
    # （被 git 当选项）、含空白（多参数注入）。剩下的交给 `--verify` 报错。
    if not sha or sha.startswith("-") or any(c.isspace() for c in sha):
        return False, ("[ATTEST] 提交标识不合法（{!r}）：要 hex 或 ref 名，"
                       "非空、不以 - 开头、不含空白".format(h))

    def _git(*argv: str) -> str:
        r = subprocess.run(["git", *argv], cwd=str(workspace), capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or "").strip() or f"git {' '.join(argv)} failed")
        return r.stdout

    # git 调用失败（坏仓库 / 空提交区间 / 不在 PATH）与"attestation 不合法"是两种 verdict：分开报，
    # 否则 `tree=""`/`body=""` 会被误判成 missing line / token mismatch（ocr-038）。
    try:
        # rev 不放 `--` 之后（那会被当路径）；注入面由上面"不以 - 开头/不含空白"的判据挡
        tree = _git("rev-parse", "--verify", f"{sha}^{{tree}}").strip()
        when_iso = _git("show", "-s", "--format=%aI", sha).strip()
        body = _git("log", "-1", "--format=%B", sha)
    except RuntimeError as exc:
        return False, f"[ATTEST] git 调用失败（{h}）：{exc}"
    m: Optional[re.Match] = None
    for ln in body.splitlines():
        m = LINE_RE.match(ln.strip())
        if m:
            break
    if not m:
        return False, f"[ATTEST] commit {h} missing attestation line"
    who, when, tok = m.group(1), m.group(2), m.group(3)
    # 时间绑定：行必须与本提交的**作者时间**同窗（±1 分钟），否则把一条合法行原样搬到另一提交
    # （同树）即可复用（ocr-005）。用作者时间而非提交者时间：rebase/amend 会改提交者时间但保留
    # 作者时间 ⇒ 不误杀正常历史重写；攻击者复用须显式改作者时间（留痕）。
    if window(when_iso) not in windows(when):
        return False, (f"[ATTEST] commit {h} timestamp mismatch "
                       "-- attestation line not bound to this commit's author date")
    expected = [
        WORDLIST[int(hashlib.sha256(f"{secret()}|{w}|{tree}".encode()).hexdigest(), 16) % len(WORDLIST)]
        for w in windows(when)
    ]
    if tok not in expected:
        return False, (
            f"[ATTEST] commit {h} token mismatch "
            "-- attestation was not produced by the governed path"
        )
    return True, f"[ATTEST] commit {h} OK ({who} @ {when})"
