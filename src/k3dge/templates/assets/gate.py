#!/usr/bin/env python3
import pathlib
import shutil
import subprocess
import sys
import os

ROOT = pathlib.Path(__file__).resolve().parent.parent

args = sys.argv[1:] if len(sys.argv) > 1 else ["check"]

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
