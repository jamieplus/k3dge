#!/usr/bin/env python3
import pathlib
import re
import shutil
import subprocess
import sys
import os

ROOT = pathlib.Path(__file__).resolve().parent.parent
# 布局假设校验：ROOT 由"本脚本在 <root>/scripts/ 下"推出，被复制/软链到别的深度会指错根，
# 于是政策/收据/venv 全在错根上算，且以"没声明政策"收场静默放行（ocr2-349）。与 gate.sh
# 的验根同口径（`.agent/` 是 k3dge 治理仓的固定标记）。
if not (ROOT / ".agent").is_dir():
    print(f"[k3dge] gate.py: 推断的仓根 '{ROOT}' 里没有 .agent/ ⇒ 布局假设不成立，拒跑", file=sys.stderr)
    sys.exit(1)

args = sys.argv[1:] if len(sys.argv) > 1 else ["check"]


# K3DGE_SOURCE 统管校验：环境声明的源 vs 本 venv 的装时落盘，不一致即拦。
# 政策优先级与 gate.sh / gate.ps1 同：环境（最高）> 本仓 pyproject [tool.k3dge].source；都没有 = legacy。
def _source_policy(pyproject: pathlib.Path) -> str:
    if not pyproject.is_file():
        return ""
    try:
        text = pyproject.read_text(encoding="utf-8-sig")   # 容忍 BOM（init.ps1 旧版会写带 BOM 的文件）
    except (OSError, UnicodeDecodeError) as exc:
        print(f"[k3dge-source] 读 pyproject 失败：{exc}——拒绝静默放行", file=sys.stderr)
        sys.exit(1)
    try:
        import tomllib  # py3.11+
    except ModuleNotFoundError:
        tomllib = None
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except Exception as exc:
            # 语法错 ≠ 没有政策：静默 return "" 会让该生效的政策悄悄关掉（ocr-148）。
            print(f"[k3dge-source] pyproject.toml 解析失败（{exc}）——拒绝静默放行", file=sys.stderr)
            sys.exit(1)
        tool = data.get("tool", {})
        if not isinstance(tool, dict):
            print("[k3dge-source] pyproject 的 [tool] 不是表 ⇒ 拒绝静默放行", file=sys.stderr)
            sys.exit(1)
        if "k3dge" not in tool:
            return ""
        sec = tool["k3dge"]
        if not isinstance(sec, dict):
            print("[k3dge-source] pyproject 的 [tool.k3dge] 不是表 ⇒ 拒绝静默放行", file=sys.stderr)
            sys.exit(1)
        src = sec.get("source", "")
        if not isinstance(src, str):
            print(f"[k3dge-source] pyproject 的 source 不是字符串（{type(src).__name__}）⇒ 拒绝静默放行",
                  file=sys.stderr)
            sys.exit(1)
        return src.strip()
    return _source_policy_fallback(text)


def _source_policy_fallback(text: str) -> str:
    """py3.10 文本回退：锚定 `source = "..."`（两种引号 + 缩进 + 行尾注释），别用
    `startswith("source")`（会先命中 sources=/source-dir= 等相邻键，ocr-149）。表头也先
    剥注释/空白再比较（`[tool.k3dge] # x` / `[ tool.k3dge ]` 以前被判成"无政策"静默放行，
    ocr2-351）；段存在却取不到值 ⇒ 拒跑，不静默当 legacy。"""
    inside = False
    saw_section = False
    for raw in text.splitlines():
        s = raw.strip()
        if re.match(r"^\[\s*tool\.k3dge\s*\]\s*(#.*)?$", s):
            inside = True
            saw_section = True
            continue
        if s.startswith("["):
            inside = False
            continue
        if inside:
            m = re.match(r"""^source\s*=\s*["']([^"']*)["']\s*(#.*)?$""", s)
            if m:
                return m.group(1)
    if saw_section:
        print("[k3dge-source] pyproject 有 [tool.k3dge] 段但没解析出 source ⇒ 拒跑；请检查该行写法",
              file=sys.stderr)
        sys.exit(1)
    return ""


def _norm_path(p: str) -> str:
    """与 gate.sh 的 `cd "$ROOT"` 同口径：相对路径按**仓根**解析（不是调用者 cwd），无条件
    realpath（文件/尚不存在路径上的 `..`/符号链接父目录也要归一，ocr2-352）。"""
    pp = pathlib.Path(p)
    if not pp.is_absolute():
        pp = ROOT / pp
    return os.path.realpath(str(pp))


_src_file = ROOT / ".venv" / "k3dge-source.txt"
_want = (os.environ.get("K3DGE_SOURCE", "").strip()
         or _source_policy(ROOT / "pyproject.toml"))
if _want:
    if not _src_file.is_file():
        # 政策存在而收据缺失 ⇒ 无法证明本 venv 来源与政策一致（删收据 / 手建 venv 都会溜过，ocr-150）。
        print("[k3dge-source] 政策已声明但 .venv/k3dge-source.txt 缺失：无法证明来源一致 ⇒ 拒跑",
              file=sys.stderr)
        print("  重跑 ./k3dge-init.sh（或 .ps1）落盘，或 unset K3DGE_SOURCE/改 pyproject 政策。", file=sys.stderr)
        sys.exit(2)
    try:
        _txt = _src_file.read_text(encoding="utf-8-sig")   # BOM 会让 `!=` 恒真 ⇒ 假 MISMATCH（ocr-151）
    except (OSError, UnicodeDecodeError) as exc:
        print(f"[k3dge-source] 读收据失败：{exc}", file=sys.stderr)
        sys.exit(1)
    _rec = _txt.splitlines()[0].strip() if _txt.strip() else ""
    if not _rec:
        # 空/仅空白/BOM-only 收据 ⇒ 无证据：与"收据缺失"同等拒跑，不能跳过比较静默放行（ocr2-015/096）。
        print("[k3dge-source] 政策已声明但 .venv/k3dge-source.txt 为空/仅空白：无证据 ⇒ 拒跑",
              file=sys.stderr)
        sys.exit(2)
    if _norm_path(_want) != _norm_path(_rec):
        print(f"[k3dge-source] MISMATCH: want='{_want}' (env>pyproject) but installed from '{_rec}'.",
              file=sys.stderr)
        print("  重装或改政策后再跑闸。", file=sys.stderr)
        sys.exit(2)

# Prefer project venv：与 gate.sh 的 `[ -x ]` 同口径（只看存在会 exec 一个坏解释器崩闸，ocr-153）。
venv_k3dge = ROOT / ".venv" / ("Scripts/k3dge.exe" if os.name == "nt" else "bin/k3dge")
if venv_k3dge.is_file() and os.access(str(venv_k3dge), os.X_OK):
    try:            # 丢 +x 已被上面的 X_OK 挡住；shebang 指向已删解释器仍会 OSError ⇒ 不得裸抛（351）
        sys.exit(subprocess.call([str(venv_k3dge)] + args))
    except OSError as exc:
        print(f"[k3dge] 无法执行 {venv_k3dge}：{exc} ⇒ 闸中止（不静默放行）", file=sys.stderr)
        sys.exit(127)

# Fall back to globally installed k3dge
k3dge = shutil.which("k3dge")
if k3dge:
    # 收据只覆盖 `.venv`；政策已声明而 .venv 判定核缺失时，全局那份来源未经收据校验。删/丢 venv 二进制
    # 比伪造收据更省事 ⇒ 默认拒跑（与相邻 fail-closed 分支及 gate.sh 同口径，ocr2-143）；
    # K3DGE_ALLOW_GLOBAL=1 保留便利回落。诊断按**平台实际探测的** venv 路径点名。
    if _want:
        if os.environ.get("K3DGE_ALLOW_GLOBAL") != "1":
            print(f"[k3dge-source] 政策已声明但 {venv_k3dge} 缺失：全局 k3dge 来源未经校验 ⇒ 拒跑"
                  "（K3DGE_ALLOW_GLOBAL=1 可强制回落）", file=sys.stderr)
            sys.exit(2)
        print(f"[k3dge-source] WARN: 政策已声明但 {venv_k3dge} 缺失 ⇒ 回落全局 k3dge（其来源未经收据校验）：{k3dge}",
              file=sys.stderr)
    try:
        sys.exit(subprocess.call([k3dge] + args))
    except OSError as exc:
        print(f"[k3dge] 无法执行 {k3dge}：{exc} ⇒ 闸中止（不静默放行）", file=sys.stderr)
        sys.exit(127)

print("k3dge not found. Run ./k3dge-init.sh or ./k3dge-init.ps1", file=sys.stderr)
print("See README.md for details.", file=sys.stderr)
sys.exit(1)
