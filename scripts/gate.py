#!/usr/bin/env python3
import pathlib
import shutil
import subprocess
import sys
import os

ROOT = pathlib.Path(__file__).resolve().parent.parent

args = sys.argv[1:] if len(sys.argv) > 1 else ["check"]

# K3DGE_SOURCE 统管校验：环境声明的源 vs 本 venv 的装时落盘，不一致即拦。
_src_file = ROOT / ".venv" / "k3dge-source.txt"
_want = os.environ.get("K3DGE_SOURCE", "").strip()
if _want and _src_file.is_file():
    _rec = _src_file.read_text(encoding="utf-8").splitlines()[0].strip() if _src_file.read_text(encoding="utf-8").strip() else ""
    _w = os.path.realpath(_want) if os.path.isdir(_want) else _want
    _r = os.path.realpath(_rec) if os.path.isdir(_rec) else _rec
    if _w != _r:
        print(f"[k3dge-source] MISMATCH: K3DGE_SOURCE='{_w}' but this venv was installed from '{_r}'.", file=sys.stderr)
        print("  用 K3DGE_SOURCE 重装一次（或 unset 回 legacy），再跑闸。", file=sys.stderr)
        sys.exit(2)

# Prefer project venv
venv_k3dge = ROOT / ".venv" / ("Scripts/k3dge.exe" if os.name == "nt" else "bin/k3dge")
if venv_k3dge.exists():
    sys.exit(subprocess.call([str(venv_k3dge)] + args))

# Fall back to globally installed k3dge
k3dge = shutil.which("k3dge")
if k3dge:
    sys.exit(subprocess.call([k3dge] + args))

print("k3dge not found. Run ./k3dge-init.sh or ./k3dge-init.ps1", file=sys.stderr)
print("See README.md for details.", file=sys.stderr)
sys.exit(1)
