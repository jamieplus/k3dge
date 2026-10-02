"""K3DGE_SOURCE 统管：环境声明 vs 装时落盘不一致 ⇒ gate.* exit 2 拒跑。"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _sealed_root(test: unittest.TestCase, receipt: "str | None", *,
                 policy_source: "str | None" = None) -> Path:
    """密封 fixture（t-026）：**绝不碰开发者的真 `.venv`**。

    旧 `_set_receipt` 改的是 `ROOT/.venv/k3dge-source.txt`——生产闸真读的装时收据：
    ①还原只靠 addCleanup，SIGINT/crash 后**回不去原值**（原值只活在死进程内存里），
    留下的假收据＋任何来源声明会让此后每一次 `gate.*` exit 2＝把作者的 pre-commit
    静默变砖；②两个用例写同一个路径＝共享可变状态，并行/乱序即互相污染。
    这里把两轨脚本、收据、pyproject 与一个**确定退出码（41）的 venv 入口桩**收进
    临时根——"政策放行走到了执行"也有可断言的必然信号（t-025：rc==0 从此不再
    取决于这台机器装没装 k3dge）。
    """
    root = Path(tempfile.mkdtemp())
    test.addCleanup(shutil.rmtree, root, True)
    (root / "scripts").mkdir()
    for f in ("gate.sh", "gate.py"):
        shutil.copy2(ROOT / "scripts" / f, root / "scripts" / f)
    py = '[project]\nname = "x"\nversion = "0.1.0"\n'
    if policy_source:
        py += f"\n[tool.k3dge]\nsource = \"{policy_source}\"\n"
    (root / "pyproject.toml").write_text(py, encoding="utf-8")
    (root / ".venv" / "bin").mkdir(parents=True)
    if receipt is not None:
        (root / ".venv" / "k3dge-source.txt").write_text(receipt + "\n", encoding="utf-8")
    stub = root / ".venv" / "bin" / "k3dge"
    stub.write_text("#!/bin/sh\nexit 41\n", encoding="utf-8")
    stub.chmod(0o755)
    return root


def _run_gate(track: str, root: Path, env: dict):
    cmd = (["bash", "scripts/gate.sh", "version"] if track == "sh"
           else [sys.executable, "scripts/gate.py", "version"])
    return subprocess.run(cmd, cwd=root, capture_output=True, text=True, env=env, timeout=60)


class TestGateSource(unittest.TestCase):
    """env 声明（K3DGE_SOURCE）vs 装时收据：不一致 ⇒ 拒跑；一致 ⇒ 放行进入口。"""

    @unittest.skipUnless(shutil.which("bash"), "gate.sh 轨需要 bash（Windows 走 ps1 轨，见下）")
    def test_mismatch_exits_2(self):
        root = _sealed_root(self, "installed-from-here")
        env = dict(os.environ, K3DGE_SOURCE="git+https://example.invalid/x.git")
        r = _run_gate("sh", root, env)
        self.assertEqual(r.returncode, 2, r.stderr[-300:])
        self.assertIn("MISMATCH", r.stderr)

    def test_match_proceeds_no_mismatch(self):   # py 轨：python3 恒在（sys.executable）
        rec = "git+https://example.invalid/match.git"
        root = _sealed_root(self, rec)
        env = dict(os.environ, K3DGE_SOURCE=rec)
        r = _run_gate("py", root, env)
        self.assertNotIn("MISMATCH", r.stdout + r.stderr)
        # 政策放行才会 exec 入口桩：41 是**必然信号**——不再拿"全局 k3dge 恰好能跑且
        # 退 0"当判据（旧形状在没 init 的检出上 exit 1，与政策无关地红；t-025）。
        self.assertEqual(r.returncode, 41,
                         f"未走到执行入口（政策被误拦？）：{(r.stdout + r.stderr)[-200:]}")

    def test_gate_py_mismatch_exits_2(self):
        root = _sealed_root(self, "installed-from-here")
        env = dict(os.environ, K3DGE_SOURCE="git+https://example.invalid/x.git")
        r = _run_gate("py", root, env)
        self.assertEqual(r.returncode, 2, r.stderr[-300:])
        self.assertIn("MISMATCH", r.stderr)

class TestPyprojectOnlyPolicy(unittest.TestCase):
    """政策只写在 pyproject（env 未设）这条路——三轨都得判同一件事（ocr-347 的 (b)）。"""

    def _fixture(self, receipt: str) -> Path:
        # 与 TestGateSource 同一密封形状（t-024 的桩、t-026 的临时根）——两份近似
        # 拷贝迟早各修各的；政策写在 pyproject（env 不出现在调用方）。
        return _sealed_root(self, receipt, policy_source="git+x")

    def _run(self, track, root):
        if track == "sh" and not shutil.which("bash"):
            self.skipTest("gate.sh 轨需要 bash（sh track）")
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
