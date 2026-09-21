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
