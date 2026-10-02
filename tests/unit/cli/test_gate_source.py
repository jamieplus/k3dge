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
    (root / ".agent").mkdir()          # gate.py 的验根标记（ocr2-349）
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
    # ocr2-396：gate.py 在 nt 下读 `.venv/Scripts/k3dge.exe`（gate.py:84），只铺 bin
    # 在 Windows 上桩永远找不到 ⇒ rc 断言随机器而变；按平台补齐另一轨的桩。
    scripts_dir = root / ".venv" / "Scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    win_stub = scripts_dir / "k3dge.exe"
    win_stub.write_text("#!/bin/sh\nexit 41\n", encoding="utf-8")
    try:
        win_stub.chmod(0o755)
    except OSError:
        pass
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

class TestGateShLayoutAndPolicyShape(unittest.TestCase):
    """gate.sh 的验根与政策读取失败面（ocr2-353/356）。sh 轨需要 bash。"""

    @unittest.skipUnless(shutil.which("bash"), "gate.sh 轨需要 bash")
    def test_missing_agent_marker_refuses(self) -> None:
        root = _sealed_root(self, None)
        shutil.rmtree(root / ".agent")
        env = dict(os.environ)
        env.pop("K3DGE_SOURCE", None)
        r = subprocess.run(["bash", "scripts/gate.sh", "version"], cwd=root,
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 1, r.stderr[-300:])
        self.assertIn(".agent", r.stderr)

    @unittest.skipUnless(shutil.which("bash"), "gate.sh 轨需要 bash")
    def test_refuses_source_line_that_yields_no_value(self) -> None:
        # 强制走无 tomllib 的文本回退：段里有 `source =` 却解析不出值 ⇒ exit 2，不静默当 legacy（ocr2-356）。
        root = _sealed_root(self, None)
        (root / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1.0"\n\n[tool.k3dge]\nsource = x\n', encoding="utf-8")
        fake = root / "fakelib"
        fake.mkdir()
        (fake / "tomllib.py").write_text("raise ModuleNotFoundError('forced')\n", encoding="utf-8")
        env = dict(os.environ)
        env.pop("K3DGE_SOURCE", None)
        env["PYTHONPATH"] = str(fake)
        r = subprocess.run(["bash", "scripts/gate.sh", "version"], cwd=root,
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 2, r.stderr[-300:])
        self.assertIn("source", r.stderr)


    @unittest.skipUnless(shutil.which("bash"), "gate.sh 轨需要 bash")
    def test_declared_policy_refuses_unverified_global_fallback(self) -> None:
        # 政策已声明、收据一致，但 .venv 判定核缺失 ⇒ 默认拒跑，不静默用来源未校验的全局 k3dge（ocr2-357）。
        root = _sealed_root(self, "git+x", policy_source="git+x")
        (root / ".venv" / "bin" / "k3dge").unlink()
        win = root / ".venv" / "Scripts" / "k3dge.exe"
        if win.exists():
            win.unlink()
        shim = root / "globalshim"
        shim.mkdir()
        g = shim / "k3dge"
        g.write_text("#!/bin/sh\nexit 41\n", encoding="utf-8")
        g.chmod(0o755)
        env = dict(os.environ)
        env.pop("K3DGE_SOURCE", None)
        env["PATH"] = f"{shim}{os.pathsep}{env.get('PATH', '')}"
        r = subprocess.run(["bash", "scripts/gate.sh", "version"], cwd=root,
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 2, r.stderr[-300:])

    @unittest.skipUnless(shutil.which("bash"), "gate.sh 轨需要 bash")
    def test_text_fallback_parses_valid_quoted_source(self) -> None:
        """无 tomllib 时，合法 `source = "git+x"`（无行尾注释）也必须解析出来、走到了入口桩。

        回归 ocr2-145：旧实现用 GNU BRE 的 `\\?` 可选组（BSD/macOS sed 不认 ⇒ 匹配失败）并以
        `head -1` 收尾（`set -o pipefail` 下 SIGPIPE=141 会静默中止 bootstrap）。
        """
        root = _sealed_root(self, "git+x", policy_source="git+x")
        fake = root / "fakelib"
        fake.mkdir()
        (fake / "tomllib.py").write_text("raise ModuleNotFoundError('forced')\n", encoding="utf-8")
        env = dict(os.environ)
        env.pop("K3DGE_SOURCE", None)
        env["PYTHONPATH"] = str(fake)
        r = subprocess.run(["bash", "scripts/gate.sh", "version"], cwd=root,
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 41,
                         f"合法 source 被当'读不懂'拒跑/漏解析：{(r.stdout + r.stderr)[-300:]}")


class TestPyprojectOnlyPolicy(unittest.TestCase):
    """政策只写在 pyproject（env 未设）这条路——三轨都得判同一件事（ocr-347 的 (b)）。"""

    def _fixture(self, receipt: str) -> Path:
        # 与 TestGateSource 同一密封形状（t-024 的桩、t-026 的临时根）——两份近似
        # 拷贝迟早各修各的；政策写在 pyproject（env 不出现在调用方）。
        return _sealed_root(self, receipt, policy_source="git+x")

    def _run(self, track, root):
        # ocr2-397：缺 bash 时返回 None 而不是抛 SkipTest——抛会中止整个方法，
        # py 轨（只需要 sys.executable）将永远跑不到；调用方逐轨 subTest + continue。
        if track == "sh" and not shutil.which("bash"):
            return None
        env = dict(os.environ)
        env.pop("K3DGE_SOURCE", None)
        cmd = (["bash", "scripts/gate.sh", "version"] if track == "sh"
               else [sys.executable, "scripts/gate.py", "version"])
        return subprocess.run(cmd, cwd=root, capture_output=True, text=True, env=env, timeout=60)

    def test_mismatch_from_pyproject_exits_2_both_tracks(self) -> None:
        skipped = []
        for track in ("sh", "py"):
            # ocr2-397：每轨独立 subTest——sh 缺 bash 时 skip 不得吞掉 py 轨；
            # 任一轨失败也不得中断另一轨。
            with self.subTest(track=track):
                r = self._run(track, self._fixture("git+y"))
                if r is None:
                    skipped.append(track)
                    continue
                self.assertEqual(r.returncode, 2, f"{track}: {r.stderr[-300:]}")
                self.assertIn("MISMATCH", r.stderr, track)
        if skipped:
            self.skipTest(f"无 bash，{skipped} 轨未跑；其余轨已断言")

    def test_matching_pyproject_policy_passes_the_gate(self) -> None:
        skipped = []
        for track in ("sh", "py"):
            with self.subTest(track=track):
                r = self._run(track, self._fixture("git+x"))
                if r is None:
                    skipped.append(track)
                    continue
                self.assertNotIn("MISMATCH", r.stdout + r.stderr, track)
                # 政策放行才会去 exec 入口；41 来自 fixture 里的桩 ⇒ 证明"闸没拦、执行了"，
                # 而不是把断言押在下游 CLI 的退出码上（那会随装了哪个 k3dge 而变）。
                # ocr2-396：fixture 同时铺 bin/k3dge 与 Scripts/k3dge.exe，
                # gate.py 按平台解析的那一侧恒有桩，41 与平台无关。
                self.assertEqual(r.returncode, 41,
                                 f"{track} 未走到执行入口（政策被误拦？）：{(r.stdout + r.stderr)[-200:]}")

    def test_missing_receipt_is_refused_both_tracks(self) -> None:
        skipped = []
        for track in ("sh", "py"):
            with self.subTest(track=track):
                root = self._fixture("git+x")
                (root / ".venv" / "k3dge-source.txt").unlink()
                r = self._run(track, root)
                if r is None:
                    skipped.append(track)
                    continue
                self.assertEqual(r.returncode, 2, f"{track}: {r.stderr[-300:]}")
                self.assertIn("缺失", r.stderr, track)
        if skipped:
            self.skipTest(f"无 bash，{skipped} 轨未跑；其余轨已断言")

    def test_empty_receipt_is_refused_both_tracks(self) -> None:
        """ocr2-398：空/纯空白收据＝无证据，必须拒（exit 2），不能当"没声明"放行。"""
        skipped = []
        for receipt in ("", " \n"):
            for track in ("sh", "py"):
                with self.subTest(receipt=repr(receipt), track=track):
                    root = self._fixture("git+x")
                    (root / ".venv" / "k3dge-source.txt").write_text(receipt, encoding="utf-8")
                    r = self._run(track, root)
                    if r is None:
                        skipped.append(track)
                        continue
                    self.assertEqual(r.returncode, 2,
                                     f"{track} receipt={receipt!r}: {(r.stdout + r.stderr)[-300:]}")
        if skipped:
            self.skipTest(f"无 bash，{sorted(set(skipped))} 轨未跑；其余轨已断言")

    def test_ps1_shares_the_decision_markers(self) -> None:
        """`gate.ps1` 本机不可跑（无 pwsh），但判据文案与比较方式必须同轨（347/345/346）。"""
        ps1 = (ROOT / "scripts" / "gate.ps1").read_text(encoding="utf-8")
        for m in ("k3dge-source", "MISMATCH", "缺失", "Resolve-PhysPath"):
            self.assertIn(m, ps1, f"gate.ps1 缺判据标记：{m}")
        # ocr2-399：`-cne` 也出现在注释里，子串断言抓不住比较符退化；
        # 钉真表达式，并确认代码行里没有大小写不敏感的 `-ne` 比较。
        self.assertIn("$w -cne $r", ps1, "gate.ps1 真比较必须是大小写敏感的 -cne")
        code_lines = [ln for ln in ps1.splitlines() if not ln.lstrip().startswith("#")]
        code = "\n".join(code_lines)
        import re as _re
        self.assertIsNone(_re.search(r"(?<![a-z])-ne\b", code),
                          "gate.ps1 代码行出现大小写不敏感 -ne 比较")


class TestGatePyLayoutAndPolicyShape(unittest.TestCase):
    """gate.py 的验根、政策形状与路径归一（ocr2-349/350/352）。py 轨恒可跑。"""

    def _run_py(self, root: Path, extra_env: dict | None = None):
        env = dict(os.environ)
        env.pop("K3DGE_SOURCE", None)
        if extra_env:
            env.update(extra_env)
        return subprocess.run([sys.executable, "scripts/gate.py", "version"],
                              cwd=root, capture_output=True, text=True, env=env, timeout=60)

    def test_missing_agent_marker_refuses(self) -> None:
        # 复制到没有 .agent/ 的树里 ⇒ ROOT 假设不成立，拒跑而不是静默当"没政策"放行（ocr2-349）。
        root = _sealed_root(self, None)
        shutil.rmtree(root / ".agent")
        r = self._run_py(root)
        self.assertEqual(r.returncode, 1, r.stderr[-300:])
        self.assertIn(".agent", r.stderr)

    def test_non_table_policy_shapes_refuse(self) -> None:
        # [tool] / [tool.k3dge] 形状异常或 source 非串 ⇒ 出声 exit 1，不静默关掉政策校验（ocr2-350）。
        bodies = ('[tool]\nk3dge = "x"\n', "[tool]\nk3dge = 5\n", "[tool.k3dge]\nsource = 5\n")
        for body in bodies:
            with self.subTest(body=body):
                root = _sealed_root(self, None)
                (root / "pyproject.toml").write_text(
                    '[project]\nname = "x"\nversion = "0.1.0"\n\n' + body, encoding="utf-8")
                r = self._run_py(root)
                self.assertEqual(r.returncode, 1, r.stderr[-300:])

    def test_path_dotdot_normalized_for_nonexistent(self) -> None:
        # 尚不存在的路径也要 realpath 归一：`a/b/../b` 与 `a/b` 是同一源，不得假 MISMATCH（ocr2-352）。
        root = _sealed_root(self, None)
        ghost = root / "ghost"
        (root / ".venv" / "k3dge-source.txt").write_text(str(ghost) + "\n", encoding="utf-8")
        r = self._run_py(root, {"K3DGE_SOURCE": str(ghost / ".." / "ghost")})
        self.assertEqual(r.returncode, 41, (r.stdout + r.stderr)[-300:])
        self.assertNotIn("MISMATCH", r.stdout + r.stderr)

    def _force_text_fallback(self, root: Path) -> dict:
        fake = root / "fakelib"
        fake.mkdir()
        (fake / "tomllib.py").write_text("raise ModuleNotFoundError('forced')\n", encoding="utf-8")
        return {"PYTHONPATH": str(fake)}

    def test_text_fallback_parses_header_comment_and_spacing(self) -> None:
        # 无 tomllib 时，`[ tool.k3dge ] # 注释` 与带行尾注释的 source 也要取到值（ocr2-351）。
        root = _sealed_root(self, "git+x")
        (root / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1.0"\n\n[ tool.k3dge ] # policy\nsource = "git+x"  # checkout\n',
            encoding="utf-8")
        r = self._run_py(root, self._force_text_fallback(root))
        self.assertEqual(r.returncode, 41, (r.stdout + r.stderr)[-300:])

    def test_text_fallback_refuses_section_without_source(self) -> None:
        # 段存在但取不到值 ⇒ 出声 exit 1，不静默当 legacy（ocr2-351，与 ocr-148 同口径）。
        root = _sealed_root(self, None)
        (root / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1.0"\n\n[tool.k3dge]\nother = 1\n', encoding="utf-8")
        r = self._run_py(root, self._force_text_fallback(root))
        self.assertEqual(r.returncode, 1, (r.stdout + r.stderr)[-300:])

    def test_declared_policy_refuses_unverified_global_fallback(self) -> None:
        # 政策已声明、收据一致，但 .venv 判定核缺失 ⇒ 默认拒跑，不静默用来源未校验的全局 k3dge
        #（ocr2-143，与 gate.sh 的 ocr2-357 同口径）。
        root = _sealed_root(self, "git+x", policy_source="git+x")
        (root / ".venv" / "bin" / "k3dge").unlink()
        win = root / ".venv" / "Scripts" / "k3dge.exe"
        if win.exists():
            win.unlink()
        shim = root / "globalshim"
        shim.mkdir()
        g = shim / "k3dge"
        g.write_text("#!/bin/sh\nexit 41\n", encoding="utf-8")
        g.chmod(0o755)
        env = dict(os.environ)
        env.pop("K3DGE_SOURCE", None)
        env["PATH"] = f"{shim}{os.pathsep}{env.get('PATH', '')}"
        r = subprocess.run([sys.executable, "scripts/gate.py", "version"], cwd=root,
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 2, r.stderr[-300:])
