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
    # ocr2-409：`_stage` 已把 __pycache__/*.pyc/.DS_Store 滤掉 ⇒ 构建器侧 filter
    # 删了也照样绿。把派生垃圾种回 staged 树，唯一能挡住它的就是 builder 的 filter。
    (root / "src" / "k3dge" / "__pycache__").mkdir(parents=True, exist_ok=True)
    (root / "src" / "k3dge" / "__pycache__" / "planted.pyc").write_bytes(b"\x00" * 16)
    (root / "src" / "k3dge" / ".DS_Store").write_bytes(b"junk")
    return root


def _scrubbed_env() -> dict:
    """ocr2-410：运行时调用剥掉宿主泄漏——src 布局的 PYTHONPATH/可编辑安装会让
    坏包照样 rc==0（`from k3dge...` 回落到宿主副本）；K3DGE_* 会改变 check 行为。"""
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONPATH", "PYTHONHOME", "K3DGE_MCP_ROOT",
                        "K3DGE_ALLOW_EXTERNAL_WORKSPACE", "__PYVENV_LAUNCHER__")}
    env.pop("PYTHONSAFEPATH", None)
    return env


def test_pyz_builder_and_runtime(tmp_path: Path) -> None:
    root = _stage(tmp_path)
    build = subprocess.run(["sh", str(root / "scripts" / "build-pyz.sh")],
                           cwd=str(root), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300,
                           env={**os.environ, "PYTHON": sys.executable})
    assert build.returncode == 0, f"builder failed:\n{build.stdout}\n{build.stderr}"
    out = root / "dist" / "k3dge.pyz"
    assert out.is_file() and out.stat().st_size > 0, "构建器没产出 dist/k3dge.pyz"

    # ocr2-706①：ZipFile 不关＝fd 靠 refcount，Windows 上会卡 tmp_path 清理。用 with。
    # ocr2-706②：zipapp --main 模板同样产出同名 __main__.py——只验名字分不出"吞 rc 模板"。
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "__main__.py" in names, "入口必须是仓内 src/__main__.py（zipapp --main 模板不 sys.exit）"
        entry = zf.read("__main__.py").decode("utf-8")
    assert "sys.exit(main())" in entry, "入口不是仓内那份（吞 rc 模板无 sys.exit）"
    junk = [n for n in names if "__pycache__" in n or n.endswith((".pyc", ".DS_Store"))]
    assert junk == [], f"派生垃圾随单件外发：{junk[:5]}"
    planted = [n for n in names if "planted" in n]
    assert planted == [], f"种回的垃圾进了包＝builder filter 已死：{planted}"

    ctx = f"pyz={out} cwd={tmp_path} exe={sys.executable}"
    r = subprocess.run([sys.executable, str(out), "--help"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       cwd=str(tmp_path), timeout=60, env=_scrubbed_env())  # t-021 + ocr2-410
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
                        cwd=str(empty), timeout=60, env=_scrubbed_env())
    # ocr2-411：`!= 0` 太弱（ZipImportError/缺模块/SyntaxError/argparse exit 2 都非零）；
    # 基线（INC-20261001-REG-zipapp-main-drops-exit-code）是进程内 rc == 1，钉死它。
    assert r2.returncode == 1, (ctx + f"：空目录 check 退出 {r2.returncode} 而非 1——"
                               "main() 返回码没到达进程（崩溃形失败也会非零，不能当通过）\n" +
                               r2.stdout[-500:] + "\n" + r2.stderr[-500:])


def test_pyz_builder_rejects_unrunnable_shebang(tmp_path: Path) -> None:
    """ocr2-131：冒烟必须**经产物自己的 shebang** 起一次进程——否则 `PYZ_SHEBANG` 写成不存在的
    解释器/多参数也会"构建成功"，失败落在下游。"""
    root = _stage(tmp_path)
    build = subprocess.run(["sh", str(root / "scripts" / "build-pyz.sh")],
                           cwd=str(root), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300,
                           env={**os.environ, "PYTHON": sys.executable,
                                "PYZ_SHEBANG": "/nonexistent/interpreter-xyz"})
    assert build.returncode != 0, "坏 shebang 还构建成功＝shebang 冒烟已死"
    assert "shebang" in (build.stdout + build.stderr), build.stdout + build.stderr


def test_pyz_builder_rejects_sensitive_files(tmp_path: Path) -> None:
    """ocr2-409 后半：敏感件（.env/*.key）守卫的拒收路径——不种就永远不知道它还活着。"""
    root = _stage(tmp_path)
    (root / "src" / ".env").write_text("SECRET=x\n", encoding="utf-8")
    build = subprocess.run(["sh", str(root / "scripts" / "build-pyz.sh")],
                           cwd=str(root), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300,
                           env={**os.environ, "PYTHON": sys.executable})
    assert build.returncode != 0, "src/ 含 .env 还打出包＝敏感件守卫已死"
