"""分发冒烟：stdlib zipapp 单件可构建、可从任意目录运行（无需 venv/第三方）。"""
from __future__ import annotations

import subprocess
import sys
import zipapp
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]


def test_pyz_builds_and_runs(tmp_path: Path) -> None:
    out = tmp_path / "k3dge.pyz"
    zipapp.create_archive(str(_ROOT / "src"), target=str(out), main="k3dge.cli.main:main")
    assert out.is_file() and out.stat().st_size > 0
    r = subprocess.run([sys.executable, str(out), "--help"], capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert "check" in r.stdout and "status" in r.stdout
