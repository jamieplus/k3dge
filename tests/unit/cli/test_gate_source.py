"""K3DGE_SOURCE 统管：环境声明 vs 装时落盘不一致 ⇒ gate.* exit 2 拒跑。"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class TestGateSource(unittest.TestCase):
    def _set_receipt(self, value: str) -> None:
        """测试自备装时收据，不依赖本机 `.venv`（CI `pip install -e` 不会落这份文件）。"""
        venv = ROOT / ".venv"
        path = venv / "k3dge-source.txt"
        existed_venv = venv.is_dir()
        prev = path.read_text(encoding="utf-8") if path.is_file() else None
        venv.mkdir(parents=True, exist_ok=True)
        path.write_text(value + "\n", encoding="utf-8")

        def _restore() -> None:
            if prev is None:
                path.unlink(missing_ok=True)
                if not existed_venv:
                    try:
                        venv.rmdir()
                    except OSError:
                        pass
            else:
                path.write_text(prev, encoding="utf-8")

        self.addCleanup(_restore)

    def test_mismatch_exits_2(self):
        self._set_receipt("installed-from-here")
        env = dict(os.environ, K3DGE_SOURCE="git+https://example.invalid/x.git")
        r = subprocess.run(["bash", "scripts/gate.sh", "version"], cwd=ROOT,
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 2, r.stderr[-300:])
        self.assertIn("MISMATCH", r.stderr)

    def test_match_proceeds_no_mismatch(self):
        rec = "git+https://example.invalid/match.git"
        self._set_receipt(rec)
        env = dict(os.environ, K3DGE_SOURCE=rec)
        r = subprocess.run([sys.executable, "scripts/gate.py", "version", "show"], cwd=ROOT,
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        self.assertNotIn("MISMATCH", r.stdout + r.stderr)

    def test_gate_py_mismatch_exits_2(self):
        self._set_receipt("installed-from-here")
        env = dict(os.environ, K3DGE_SOURCE="git+https://example.invalid/x.git")
        r = subprocess.run([sys.executable, "scripts/gate.py", "version"], cwd=ROOT,
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 2, r.stderr[-300:])
        self.assertIn("MISMATCH", r.stderr)

class TestPyprojectOnlyPolicy(unittest.TestCase):
    """政策只写在 pyproject（env 未设）这条路——三轨都得判同一件事（ocr-347 的 (b)）。"""

    def _fixture(self, receipt: str) -> Path:
        import shutil
        import tempfile

        root = Path(tempfile.mkdtemp())
        (root / "scripts").mkdir()
        for f in ("gate.sh", "gate.py"):
            shutil.copy2(ROOT / "scripts" / f, root / "scripts" / f)
        (root / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1.0"\n\n[tool.k3dge]\nsource = "git+x"\n',
            encoding="utf-8")
        (root / ".venv").mkdir()
        (root / ".venv" / "k3dge-source.txt").write_text(receipt + "\n", encoding="utf-8")
        # 密封 fixture：放一个确定退出码的 venv 入口。不放的话，两轨会回落去 exec **全局**
        # k3dge（CI 里 `pip install -e` 就装着），而 `version` 缺 action 位置参数 ⇒ argparse
        # 退 2 —— 于是"匹配 ⇒ 政策未拦"这条路只能靠猜环境跑，断言成了环境的函数（t-024）。
        exe = root / ".venv" / "bin"
        exe.mkdir(exist_ok=True)
        stub = exe / "k3dge"
        stub.write_text("#!/bin/sh\nexit 41\n", encoding="utf-8")
        stub.chmod(0o755)
        self.addCleanup(shutil.rmtree, root, True)
        return root

    def _run(self, track, root):
        env = dict(os.environ)
        env.pop("K3DGE_SOURCE", None)
        cmd = (["bash", "scripts/gate.sh", "version"] if track == "sh"
               else [sys.executable, "scripts/gate.py", "version"])
        return subprocess.run(cmd, cwd=root, capture_output=True, text=True, env=env, timeout=60)

    def test_mismatch_from_pyproject_exits_2_both_tracks(self) -> None:
        for track in ("sh", "py"):
            r = self._run(track, self._fixture("git+y"))
            self.assertEqual(r.returncode, 2, f"{track}: {r.stderr[-300:]}")
            self.assertIn("MISMATCH", r.stderr, track)

    def test_matching_pyproject_policy_passes_the_gate(self) -> None:
        for track in ("sh", "py"):
            r = self._run(track, self._fixture("git+x"))
            self.assertNotIn("MISMATCH", r.stdout + r.stderr, track)
            # 政策放行才会去 exec 入口；41 来自 fixture 里的桩 ⇒ 证明"闸没拦、执行了"，
            # 而不是把断言押在下游 CLI 的退出码上（那会随装了哪个 k3dge 而变）。
            self.assertEqual(r.returncode, 41,
                             f"{track} 未走到执行入口（政策被误拦？）：{(r.stdout + r.stderr)[-200:]}")

    def test_missing_receipt_is_refused_both_tracks(self) -> None:
        for track in ("sh", "py"):
            root = self._fixture("git+x")
            (root / ".venv" / "k3dge-source.txt").unlink()
            r = self._run(track, root)
            self.assertEqual(r.returncode, 2, f"{track}: {r.stderr[-300:]}")
            self.assertIn("缺失", r.stderr, track)

    def test_ps1_shares_the_decision_markers(self) -> None:
        """`gate.ps1` 本机不可跑（无 pwsh），但判据文案与比较方式必须同轨（347/345/346）。"""
        ps1 = (ROOT / "scripts" / "gate.ps1").read_text(encoding="utf-8")
        for m in ("k3dge-source", "MISMATCH", "缺失", "Resolve-PhysPath"):
            self.assertIn(m, ps1, f"gate.ps1 缺判据标记：{m}")
        self.assertIn("-cne", ps1, "来源一致性是字面比较，不得用大小写不敏感的 -ne")
