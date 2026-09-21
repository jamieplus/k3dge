"""受管路径必须能验；缺行必须红。不开豁免。"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from k3dge.engine.attest import PREFIX, append_to_message, verify_commit


def _repo() -> Path:
    ws = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--allow-empty", "--no-verify", "-m", "chore: init"],
                   cwd=ws, check=True, capture_output=True)
    return ws


def test_appended_line_verifies():
    ws = _repo()
    (ws / "a.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True, capture_output=True)
    msg = append_to_message(ws, "feat: x", who="t")
    assert PREFIX in msg
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--no-verify", "-m", msg], cwd=ws, check=True, capture_output=True)
    h = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ws, capture_output=True, text=True).stdout.strip()
    ok, out = verify_commit(ws, h)
    assert ok, out


def test_missing_line_is_refused():
    ws = _repo()
    h = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ws, capture_output=True, text=True).stdout.strip()
    ok, out = verify_commit(ws, h)
    assert not ok
    assert "missing attestation line" in out
