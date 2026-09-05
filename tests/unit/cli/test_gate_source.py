"""K3DGE_SOURCE 统管：环境声明 vs 装时落盘不一致 ⇒ gate.* exit 2 拒跑。"""
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class TestGateSource(unittest.TestCase):
    def test_mismatch_exits_2(self):
        env = dict(os.environ, K3DGE_SOURCE="git+https://example.invalid/x.git")
        r = subprocess.run(["bash", "scripts/gate.sh", "version"], cwd=ROOT,
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 2, r.stderr[-300:])
        self.assertIn("MISMATCH", r.stderr)

    def test_gate_py_mismatch_exits_2(self):
        import sys

        env = dict(os.environ, K3DGE_SOURCE="git+https://example.invalid/x.git")
        r = subprocess.run([sys.executable, "scripts/gate.py", "version"], cwd=ROOT,
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 2, r.stderr[-300:])
