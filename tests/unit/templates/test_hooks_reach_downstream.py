"""**到达环**：`k3dge init` 之后，git hooks 与各 docs 类型的治理件必须在仓里，且 hook 真会跑闸。

背景（实测 2026-09-21，D1/D2）：`scripts/pre-commit` / `commit-msg` 此前**不在资产里** ⇒
下游按 AGENTS.md 激活 `core.hooksPath scripts` 后，git 找不到 hook 就**静默跳过**（`git commit` rc=0，
doc-gate/schema/引用/排查闸全不生效）；同时 `docs/{specs,guides,protocols,architecture,generated}`
两份治理件缺失 ⇒ 即便钩子在，下游第一次提交 spec 也会红（门禁与资产互斥）。

本测试把这条"到达"钉成机检：init → hook 可执行 → 真跑三层闸 → 缺治理件时必须红。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from k3dge.templates.scaffold import scaffold

K3DGE_SRC = Path(__file__).resolve().parents[3] / "src"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


class TestHooksReachDownstream(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "r"
        self.repo.mkdir()
        scaffold(self.repo, name="r")
        _git(self.repo, "init", "-b", "main")
        _git(self.repo, "config", "user.email", "t@example.com")
        _git(self.repo, "config", "user.name", "tester")
        # 下游出生后先 sync（契约哈希/派生件落盘）——`docs/guides/downstream.md` 的既定流程
        self._k3dge("sync")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _k3dge_shim(self) -> Path:
        """伪造"已安装的 k3dge"（下游真实场景是仓内 .venv）：PATH 上放一个 `k3dge` 可执行，
        让 hook 的一致层（`scripts/gate.py`）能解析到它。"""
        shim_dir = Path(self._tmp.name) / "bin"
        shim_dir.mkdir(exist_ok=True)
        shim = shim_dir / "k3dge"
        import shlex

        # 旧写法把解释器与仓路径直接插进 `-c '...'` 的单引号里：路径含 `"`/`'`/空格
        # （venv 建在带引号的目录下并不罕见）就把脚本结构改了，等于测试自己在示范注入面（t-319）。
        # ⇒ 值走 shlex.quote 成 shell 词，路径改由**环境变量**传给被 exec 的程序。
        prog = ('import os, sys; sys.path.insert(0, os.environ["K3DGE_SRC"]); '
                "from k3dge.cli.main import main; sys.exit(main())")
        shim.write_text(
            "#!/bin/sh\n"
            "K3DGE_SRC=" + shlex.quote(str(K3DGE_SRC)) + "; export K3DGE_SRC\n"
            "exec " + shlex.quote(sys.executable) + " -c " + shlex.quote(prog) + ' "$@"\n',
            encoding="utf-8",
        )
        shim.chmod(0o755)
        return shim_dir

    def _k3dge(self, *args: str) -> subprocess.CompletedProcess:
        """在临时仓里跑 k3dge（同 `_run_hook` 的环境：PATH shim + PYTHONPATH）。"""
        env = dict(
            os.environ,
            PYTHONPATH=str(K3DGE_SRC),
            PATH=f"{self._k3dge_shim()}{os.pathsep}{os.environ.get('PATH', '')}",
        )
        return subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0, {str(K3DGE_SRC)!r}); "
             "from k3dge.cli.main import main; sys.exit(main())", *args],
            cwd=self.repo, capture_output=True, text=True, env=env,
        )

    def _run_hook(self, *args: str) -> subprocess.CompletedProcess:
        """用系统 python 起 hook（模拟 git 的 `#!/usr/bin/env python3`），PYTHONPATH 指向 k3dge 源码。

        下游真实场景是 k3dge 装在仓内 `.venv`（hook 会自己 re-exec 进去）；这里用 PYTHONPATH +
        PATH 上的 `k3dge` shim 等价地提供"已安装的 k3dge"，避免测试里装 venv。
        """
        env = dict(
            os.environ,
            PYTHONPATH=str(K3DGE_SRC),
            K3DGE_HOOK_REEXEC="1",
            PATH=f"{self._k3dge_shim()}{os.pathsep}{os.environ.get('PATH', '')}",
        )
        return subprocess.run(
            [sys.executable, str(self.repo / "scripts" / "pre-commit"), *args],
            cwd=self.repo, capture_output=True, text=True, env=env,
        )

    def test_hook_scripts_are_shipped_and_executable(self):
        for name in ("pre-commit", "commit-msg"):
            p = self.repo / "scripts" / name
            self.assertTrue(p.is_file(), f"{name} 未随 init 下发（D1）")
            self.assertTrue(os.access(p, os.X_OK), f"{name} 不可执行（git 会静默跳过）")

    def test_governance_files_exist_for_every_docs_type(self):
        for typ in ("specs", "guides", "protocols", "architecture", "generated"):
            for name in ("README.md", "AUTHORING.md"):
                self.assertTrue(
                    (self.repo / "docs" / typ / name).is_file(), f"docs/{typ}/{name} 缺失（D2）"
                )

    def test_scan_passes_on_fresh_repo(self):
        r = self._run_hook("--scan")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[k3dge doc-gate] PASS", r.stdout)

    def test_staged_spec_passes_when_governance_present(self):
        (self.repo / "docs" / "specs" / "core").mkdir(parents=True)
        (self.repo / "docs" / "specs" / "core" / "spec.md").write_text("# spec\n", encoding="utf-8")
        self._k3dge("sync")   # 文档变了先 sync（派生件 docs-index 等），再提交——既定流程
        _git(self.repo, "add", "-A")
        r = self._run_hook()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[k3dge doc-gate] PASS", r.stdout)

    def test_missing_authoring_blocks_the_commit(self):
        (self.repo / "docs" / "specs" / "AUTHORING.md").unlink()
        (self.repo / "docs" / "specs" / "core").mkdir(parents=True)
        (self.repo / "docs" / "specs" / "core" / "spec.md").write_text("# spec\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        r = self._run_hook()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("AUTHORING.md", r.stdout)




ASSETS = K3DGE_SRC / "k3dge" / "templates" / "assets"


class TestInitEntrypoints(unittest.TestCase):
    """init 入口三件：包装壳校验目标、参数契约、argv 显式化（ocr-363..367）。"""

    def _wrapper(self, root: Path) -> Path:
        w = root / "k3dge-init.sh"
        w.write_text((ASSETS / "k3dge-init-wrapper.sh").read_text(encoding="utf-8"), encoding="utf-8")
        w.chmod(0o755)
        return w

    def test_wrapper_refuses_missing_init(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            w = self._wrapper(root)
            r = subprocess.run([str(w)], capture_output=True, text=True, cwd=root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("找不到", r.stderr)

    def test_wrapper_refuses_foreign_init_sh(self) -> None:
        (root := Path(tempfile.mkdtemp()))
        (root / "scripts").mkdir()
        (root / "scripts" / "init.sh").write_text("#!/usr/bin/env bash\necho 外来脚本\n", encoding="utf-8")
        w = self._wrapper(root)
        r = subprocess.run([str(w)], capture_output=True, text=True, cwd=root)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("不是 k3dge 下发", r.stderr)
        self.assertNotIn("外来脚本", r.stdout)

    def test_wrapper_rejects_positional_args_with_the_right_hint(self) -> None:
        root = Path(tempfile.mkdtemp())
        (root / "scripts").mkdir()
        (root / "scripts" / "init.sh").write_text(
            "#!/usr/bin/env bash\n# k3dge init\ntrue\n", encoding="utf-8")
        w = self._wrapper(root)
        r = subprocess.run([str(w), "/some/other/repo"], capture_output=True, text=True, cwd=root)
        self.assertIn("K3DGE_SOURCE", r.stderr)      # 365：不接受位置参数，别再给"生效"假象

    def test_doc_gate_scan_takes_explicit_argv(self) -> None:
        """`--scan` 由调用方传参，不再靠引擎偷读 sys.argv（366）。"""
        import io
        from contextlib import redirect_stdout
        from unittest import mock

        from k3dge.engine import doc_gate

        with tempfile.TemporaryDirectory() as d:
            doc_gate.set_workspace(Path(d))
            buf = io.StringIO()
            with mock.patch.object(sys, "argv", ["prog"]), redirect_stdout(buf):
                rc = doc_gate.main(["--scan"])
            self.assertEqual(rc, 0)
            self.assertIn("无 docs/ 目录", buf.getvalue())

    def test_load_doc_gate_prefers_installed_k3dge(self) -> None:
        """自举兜底不得遮蔽已装那份（367）。"""
        import importlib.machinery     # 不能靠 importlib.util 顺带把 machinery 挂上（CPython 实现细节，t-324）
        import importlib.util

        ws = Path(tempfile.mkdtemp())
        (ws / "src" / "k3dge" / "engine").mkdir(parents=True)
        (ws / "src" / "k3dge" / "engine" / "__init__.py").write_text("", encoding="utf-8")
        spec = importlib.util.spec_from_loader(
            "pc_mod", importlib.machinery.SourceFileLoader("pc_mod", str(K3DGE_SRC.parent / "scripts" / "pre-commit")))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        before = list(sys.path)
        dg = mod._load_doc_gate(ws)
        self.assertTrue(str(Path(dg.__file__)).startswith(str(K3DGE_SRC / "k3dge")))
        self.assertNotIn(str(ws / "src"), sys.path, "已能 import 时不得再塞仓内路径")

    def test_ps1_init_gates_are_declared(self) -> None:
        """`init.ps1` 在本机（无 pwsh）不可跑，但四条判据必须在文本里成对存在（358/359/360/361/362）。"""
        ps1 = (ASSETS / "init.ps1").read_text(encoding="utf-8")
        for marker in ("sys.version_info >= (3, 10)", "rev-parse --show-toplevel",
                       "找不到 k3dge 入口", "找不到 pre-commit 入口", "if ($Src -notmatch"):
            self.assertIn(marker, ps1, f"init.ps1 缺判据：{marker}")
        wrapper = (ASSETS / "k3dge-init-wrapper.ps1").read_text(encoding="utf-8")
        self.assertIn("$PSScriptRoot", wrapper)
        self.assertIn("无法定位本脚本所在目录", wrapper)      # 363


class TestTrackHygiene(unittest.TestCase):
    """三轨脚本的进程级副作用与定位假设（ocr-373/375/376/377/378/379）。"""

    def test_build_pyz_resolves_through_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bindir = root / "bin"
            bindir.mkdir()
            link = bindir / "build-pyz.sh"
            link.symlink_to(K3DGE_SRC.parent / "scripts" / "build-pyz.sh")
            r = subprocess.run(["bash", str(link)], capture_output=True, text=True,
                               env={"PATH": "/usr/bin:/bin", "PYTHON": "definitely-not-a-python"},
                               cwd=root)
            self.assertTrue(("PYTHON" in r.stderr) or ("不像 k3dge 仓" in r.stderr),
                            r.stdout + r.stderr)     # 走到 preflight/验根，而不是在错根造 dist
            self.assertFalse((root / "dist").exists(), "错根上被 mkdir -p dist 造了垃圾")

    def test_gate_ps1_feeds_absolute_path_to_child(self) -> None:
        ps1 = (ASSETS / "gate.ps1").read_text(encoding="utf-8")
        self.assertIn("K3DGE_PYPROJECT", ps1)
        self.assertNotIn('open("pyproject.toml","rb")', ps1, "相对路径依赖子进程 CWD（375）")

    def test_generate_docs_ps1_restores_location_and_names_itself(self) -> None:
        ps1 = (ASSETS / "generate-docs.ps1").read_text(encoding="utf-8")
        self.assertIn("Push-Location $Root", ps1)
        self.assertIn("trap { Pop-Location } EXIT", ps1)             # 376
        self.assertIn("Auto-generated stub by ``./scripts/generate-docs.ps1``", ps1)  # 377
        self.assertNotIn("Auto-generated stub by ``./scripts/generate-docs.sh``", ps1)

    def test_init_ps1_guards_script_root_and_exit_codes(self) -> None:
        ps1 = (ASSETS / "init.ps1").read_text(encoding="utf-8")
        self.assertIn("} elseif ($PSCommandPath) {", ps1)             # 378：$PSScriptRoot 空不再算错根
        self.assertIn('$ScriptRoot -and (Test-Path', ps1)
        self.assertNotIn("\n  Write-Error", ps1,                      # 379：Stop 下 Write-Error 吞掉 exit 码
                         "该用 [Console]::Error.WriteLine + exit")

    def test_commit_msg_delegates_attestation_to_library(self) -> None:
        hook = (K3DGE_SRC.parent / "scripts" / "commit-msg").read_text(encoding="utf-8")
        self.assertIn("commit-attest --rewrite-file", hook)
        self.assertNotIn("$1.k3dge-tmp", hook, "hook 自己 grep+mv 的实现已退休（374）")


if __name__ == "__main__":
    unittest.main()
