"""分发冒烟：驱动**真构建器**（scripts/build-pyz.sh），不再自写第二套打包路径。

ocr t-019..t-023 收口：旧测 inline `zipapp.create_archive(...)` 绕开 shebang/preflight/
敏感件守卫 ⇒ 构建器与产物分叉时测仍绿；`parents[3]` 不验根；`--help` 是唯一调用
（argparse 自行 SystemExit(0)，`main()` 返回值从不经过进程——`.pyz` 吞 rc 时冒烟照样绿，
基线 456dda9 实测 in-process rc=1 而 pyz rc=0，已立 INC-20261001-REG-zipapp-main-drops-exit-code）；
无 timeout、解码随 locale；`"check" in stdout` 被隐藏命令与 metavar 蒙过。
"""

import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
# t-019：parents[3] 在文件被移动/摊平复制（scan_in/unit__cli__test_pyz.py）时静默指错靶
# ⇒ 用前先验根（与 scripts/build-pyz.sh 的 preflight 同形状，别再"成功打包到别人目录"）。
assert (_ROOT / "pyproject.toml").is_file() and (_ROOT / "src" / "k3dge" / "cli" / "main.py").is_file(), \
    f"repo root mis-detected: {_ROOT}"

_IGNORE = shutil.ignore_patterns("__pycache__", ".DS_Store", "*.pyc")


def _stage(tmp_path: Path) -> Path:
    """构建器输入（src/ + scripts/ + pyproject.toml）收进临时根：

    产物落临时 `dist/`，不污染仓；真实 checkout 里的 Finder 垃圾也不绑架本测。
    构建代码路径与出货**同一份**（t-020）。
    """
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copytree(_ROOT / "src", root / "src", ignore=_IGNORE)
    shutil.copytree(_ROOT / "scripts", root / "scripts", ignore=_IGNORE)
    shutil.copy2(_ROOT / "pyproject.toml", root / "pyproject.toml")
    return root


def test_pyz_builder_and_runtime(tmp_path: Path) -> None:
    root = _stage(tmp_path)
    build = subprocess.run(["sh", str(root / "scripts" / "build-pyz.sh")],
                           cwd=str(root), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300,
                           env={**os.environ, "PYTHON": sys.executable})
    assert build.returncode == 0, f"builder failed:\n{build.stdout}\n{build.stderr}"
    out = root / "dist" / "k3dge.pyz"
    assert out.is_file() and out.stat().st_size > 0, "构建器没产出 dist/k3dge.pyz"

    names = zipfile.ZipFile(out).namelist()
    assert "__main__.py" in names, "入口必须是仓内 src/__main__.py（zipapp --main 模板不 sys.exit）"
    junk = [n for n in names if "__pycache__" in n or n.endswith((".pyc", ".DS_Store"))]
    assert junk == [], f"派生垃圾随单件外发：{junk[:5]}"

    ctx = f"pyz={out} cwd={tmp_path} exe={sys.executable}"
    r = subprocess.run([sys.executable, str(out), "--help"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       cwd=str(tmp_path), timeout=60)          # t-021：有界 + 钉死编码
    assert r.returncode == 0, ctx + "\n--- stdout ---\n" + r.stdout + "\n--- stderr ---\n" + r.stderr
    # t-023①逐行匹配：metavar `{check,…,check-msg,…}` 与隐藏命令的 `==SUPPRESS==` 都不算数。
    line = next((l for l in r.stdout.splitlines() if re.match(r"^\s+check(\s|$)", l)), None)
    assert line is not None, "help 里没有 `check` 条目行（命令被删/改名，冒烟失去意义）"
    assert "==SUPPRESS==" not in line and re.match(r"^\s+check\s{2,}\S", line), \
        f"check 条目形状不对（隐藏或无正文）：{line!r}"

    # t-023②非零返回必须到达进程——空目录 `check` 就是"闸红"的真实形状。
    empty = tmp_path / "empty"
    empty.mkdir()
    r2 = subprocess.run([sys.executable, str(out), "check"], capture_output=True,
                        text=True, encoding="utf-8", errors="replace",
                        cwd=str(empty), timeout=60)
    assert r2.returncode != 0, (ctx + "：空目录 check 竟退出 0——main() 返回码被吞，"
                                      "下游拿 .pyz 当闸会常绿")
