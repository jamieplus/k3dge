#!/usr/bin/env python3
import pathlib
import shutil
import subprocess
import sys
import os

ROOT = pathlib.Path(__file__).resolve().parent.parent

args = sys.argv[1:] if len(sys.argv) > 1 else ["check"]

# K3DGE_SOURCE 统管校验：环境声明的源 vs 本 venv 的装时落盘，不一致即拦。
# 政策读取优先级与 gate.sh 同：K3DGE_SOURCE 环境（显式覆盖，最高）> 本仓 pyproject
# [tool.k3dge].source（入库政策）；都没有 = legacy（落盘收据即真相，老 venv）。
def _source_policy(pyproject):
    if not pyproject.is_file():
        return ""
    try:
        import tomllib  # py3.11+
    except ModuleNotFoundError:
        tomllib = None
    if tomllib is not None:
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            return str(data.get("tool", {}).get("k3dge", {}).get("source", "")).strip()
        except Exception:
            return ""
    # py3.10 fallback：无 tomllib，只扫 [tool.k3dge] 段的 `source = "..."`
    inside = False
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("["):
            inside = s == "[tool.k3dge]"
            continue
        if inside and s.startswith("source"):
            return s.partition("=")[2].strip().strip('"').strip("'")
    return ""


_src_file = ROOT / ".venv" / "k3dge-source.txt"
_want = (os.environ.get("K3DGE_SOURCE", "").strip()
         or _source_policy(ROOT / "pyproject.toml"))
if _want and _src_file.is_file():
    _txt = _src_file.read_text(encoding="utf-8")
    _rec = _txt.splitlines()[0].strip() if _txt.strip() else ""
    _w = os.path.realpath(_want) if os.path.isdir(_want) else _want
    _r = os.path.realpath(_rec) if os.path.isdir(_rec) else _rec
    if _w != _r:
        print(f"[k3dge-source] MISMATCH: want='{_w}' (env>pyproject) but installed from '{_r}'.", file=sys.stderr)
        print("  重装或改政策后再跑闸。", file=sys.stderr)
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
