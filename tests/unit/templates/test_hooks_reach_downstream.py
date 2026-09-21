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
        shim.write_text(
            "#!/bin/sh\n"
            f'exec "{sys.executable}" -c \'import sys; sys.path.insert(0, "{K3DGE_SRC}")\n'
            "from k3dge.cli.main import main; sys.exit(main())\' \"$@\"\n",
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


if __name__ == "__main__":
    unittest.main()
