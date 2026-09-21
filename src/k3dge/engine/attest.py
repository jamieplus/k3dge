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


def secret() -> str:
    return os.environ.get("K3DGE_ATTEST_SECRET") or DEFAULT_SECRET


def tree_hash(workspace: Path) -> str:
    return subprocess.run(
        ["git", "write-tree"], cwd=str(workspace), capture_output=True, text=True
    ).stdout.strip()


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
        return when_iso[:16]
    return dt.strftime("%Y-%m-%dT%H:%M")


def windows(when_iso: str) -> List[str]:
    from datetime import timedelta

    dt = utc_minute(when_iso)
    if dt is None:
        return [when_iso[:16]]
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
    """正文还没有 trailer 就补一行。进程提交与 `k3dge commit` 共用。"""
    if PREFIX in (msg or ""):
        return msg
    return f"{(msg or '').rstrip()}\n\n{line(workspace, who=who)}\n"


def verify_commit(workspace: Path, h: str) -> Tuple[bool, str]:
    tree = subprocess.run(
        ["git", "rev-parse", f"{h}^{{tree}}"], cwd=str(workspace),
        capture_output=True, text=True,
    ).stdout.strip()
    when_iso = subprocess.run(
        ["git", "show", "-s", "--format=%cI", h], cwd=str(workspace),
        capture_output=True, text=True,
    ).stdout.strip()
    body = subprocess.run(
        ["git", "log", "-1", "--format=%B", h], cwd=str(workspace),
        capture_output=True, text=True,
    ).stdout
    m: Optional[re.Match] = None
    for ln in body.splitlines():
        m = LINE_RE.match(ln.strip())
        if m:
            break
    if not m:
        return False, f"[ATTEST] commit {h} missing attestation line"
    who, when, tok = m.group(1), m.group(2), m.group(3)
    expected = [
        WORDLIST[int(hashlib.sha256(f"{secret()}|{w}|{tree}".encode()).hexdigest(), 16) % len(WORDLIST)]
        for w in windows(when)
    ]
    if tok not in expected:
        return False, (
            f"[ATTEST] commit {h} token mismatch (got '{tok}', expected '{expected[0]}') "
            "-- attestation was not produced by the governed path"
        )
    return True, f"[ATTEST] commit {h} OK ({who} @ {when})"
