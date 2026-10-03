"""架构文档新鲜度（seal 收摊时算的事实）：`M<last>` 边界 .. HEAD 区间内 src/spec 变过而 overview 未动 ⇒ 报。"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from k3dge.engine.seal_flow import _architecture_staleness, _boundary_tag_before


def _git_available() -> bool:
    """环境前提**先问再跑**（t-052）：缺 git 或老 runner 不认 `init -b`（<2.28）时，
    旧夹具直接炸栈——读起来像产品回归。这里探测后由类级 skipUnless 显式跳过。"""
    if not shutil.which("git"):
        return False
    with tempfile.TemporaryDirectory() as d:        # 探针目录随用随清（裸 mkdtemp＝泄漏）
        # ocr2-423：探针也必须带隔离 env，否则宿主 GIT_DIR/坏系统配置让探针失败 ⇒
        # 整类 skip，t-048…t-051 全变 no-op 还绿。探针与执行同环境才同结论。
        r = subprocess.run(["git", "init", "-q", "-b", "branch-probe", d],
                           capture_output=True, text=True, env=_env(), timeout=60)
    return r.returncode == 0


def _env() -> dict:
    """宿主环境出局：globalconfig（commit.gpgsign/hooksPath/commit.template/autocrlf）
    与导出的 GIT_DIR/GIT_WORK_TREE 都会让 init/commit/diff 为无关原因红（t-052）。"""
    e = {k: v for k, v in os.environ.items()
         if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG")}
    e["GIT_CONFIG_GLOBAL"] = os.devnull
    e["GIT_CONFIG_NOSYSTEM"] = "1"
    return e


def _git(repo: Path, *args: str) -> None:
    """前置失败要**带 git 的抱怨**出声（t-051）。

    `check=True` 的 `CalledProcessError` 只含命令与 rc，stderr 被 `capture_output`
    吞掉——CI 上"缺 git / init -b 不支持 / commit 被 gpgsign 拦"全都读成产品 bug。
    """
    proc = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, env=_env())
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{(proc.stderr or proc.stdout).strip()}")


def _init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "tester")
    (repo / "docs" / "architecture").mkdir(parents=True)
    (repo / "docs" / "architecture" / "overview.md").write_text("# Arch\n", encoding="utf-8")
    # `_architecture_staleness` 盯**两**份文档，两份都在区间内动过才回 ✅；fixture 少了
    # encyclopedia.md 就永远落在"部分未更新"支路，而那条文案同样含"已更新"（t-048）
    (repo / "docs" / "architecture" / "encyclopedia.md").write_text("# Enc\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "chore: init")
    _git(repo, "tag", "-a", "M9", "-m", "boundary M9")


@unittest.skipUnless(_git_available(), "需要 git（`init -b` 要求 ≥2.28）")
class TestArchitectureFreshness(unittest.TestCase):
    def setUp(self) -> None:
        # ocr2-424/425：隔离只做到夹具 `_git` 不够——被测的 `seal._git` 继承 ambient
        # env（`git -C ws …` 无 env=）。hook/CI 导出的 GIT_DIR 会把断言读到真仓，
        # 首个里程碑用例空转绿。全轮测试共享同一份净化 env（patcher 在此，不在 _git 内）。
        self._old_env = dict(os.environ)
        for _k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG"):
            os.environ.pop(_k, None)
        os.environ["GIT_CONFIG_GLOBAL"] = os.devnull
        os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
        self.addCleanup(self._restore_env)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        _init(self.repo)

    def _restore_env(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_env)

    # ocr2-716：此前 `tearDown` 又调一次已 `addCleanup` 注册的 cleanup——双重清理
    # （第二次靠 TemporaryDirectory 弱引用终结才 no-op，且 setUp 中途失败时 tearDown
    # 不跑而 addCleanup 跑）。只留 addCleanup，不再复写 tearDown。

    def test_boundary_tag_before_skips_current_milestone(self) -> None:
        self.assertEqual(_boundary_tag_before(self.repo, "M10"), "M9")
        self.assertEqual(_boundary_tag_before(self.repo, "M9"), "")  # 自己是唯一 tag ⇒ 无

    def _commit_src(self, msg: str = "feat: change") -> None:
        (self.repo / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", msg)

    def test_src_changed_without_overview_warns(self) -> None:
        self._commit_src()
        line = _architecture_staleness(self.repo, "M10")
        # 两条 ⚠️ 支路（"两件都没动" vs "部分已更新"）**共享**子串"未更新"——旧断言分不出
        # 走了哪条；按支路形状钉死（t-049）。
        self.assertTrue(line.startswith("⚠️"), line)
        self.assertIn("两件都没动", line)
        self.assertIn("M9", line)

    def test_specs_only_change_triggers_the_gate(self) -> None:
        """`docs/specs/` 是一等触发面前缀，此前从没被走——把它从 code 过滤里摘掉，
        旧测全绿（t-049）。spec 单独变过而两份架构文档都没动 ⇒ ⚠️。"""
        (self.repo / "docs" / "specs" / "engine").mkdir(parents=True)
        (self.repo / "docs" / "specs" / "engine" / "spec.md").write_text("# spec v2\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "docs(specs): touch spec")
        line = _architecture_staleness(self.repo, "M10")
        self.assertTrue(line.startswith("⚠️"), f"docs/specs/ 不再被当触发面：{line}")
        self.assertIn("两件都没动", line)

    def test_partial_update_reports_the_missing_doc(self) -> None:
        """"部分已更新"支路显式覆盖（t-049）：只动 overview ⇒ encyclopedia 被点名。"""
        self._commit_src()
        (self.repo / "docs" / "architecture" / "overview.md").write_text("# Arch v2\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "docs: overview only")
        line = _architecture_staleness(self.repo, "M10")
        self.assertTrue(line.startswith("⚠️"), line)
        self.assertIn("encyclopedia.md", line)
        self.assertIn("overview.md` 已更新", line)

    def test_overview_touched_in_range_is_ok(self) -> None:
        (self.repo / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
        (self.repo / "docs" / "architecture" / "overview.md").write_text("# Arch v2\n", encoding="utf-8")
        (self.repo / "docs" / "architecture" / "encyclopedia.md").write_text("# Enc v2\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "docs: arch + code")
        line = _architecture_staleness(self.repo, "M10")
        self.assertTrue(line.startswith("✅"), line)          # 只认 ✅ 支路，不再被子串"已更新"蒙过
        self.assertIn("都已更新", line)

    def test_no_code_change_since_boundary_is_ok(self) -> None:
        (self.repo / "docs" / "memo").mkdir(parents=True)
        (self.repo / "docs" / "memo" / "x.md").write_text("# x\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "docs: memo only")
        # ocr2-717：本文件唯独这条不断支路形状——裸 `assertIn("无改动")` 会被其它分支
        # 漏进来的同一子串喂饱。与兄弟测同口径，按前缀钉死无改动短路支路。
        line = _architecture_staleness(self.repo, "M10")
        self.assertTrue(line.startswith("✅"), line)
        self.assertIn("无改动", line)

    def test_first_milestone_without_boundary_is_ok(self) -> None:
        line = _architecture_staleness(self.repo, "M9")
        self.assertIn("首个里程碑", line)

    def test_boundary_is_numeric_not_lexicographic_with_multiple_tags(self) -> None:
        """fixture 以前**恰好一个 tag**，"最近一个别人的边界"这条规则从没被走（t-050）：
        `M9`+`M10` 都在、milestone 是 M11 时答案必须是 M10——字典序会把 "M9" 选出来
        （"M10" < "M9"），区间选错则 diff 与 CHANGELOG 全漂。自己已有 tag 时也排自己。"""
        _git(self.repo, "commit", "-q", "--allow-empty", "-m", "second")
        _git(self.repo, "tag", "-a", "M10", "-m", "boundary M10")
        self.assertEqual(_boundary_tag_before(self.repo, "M11"), "M10")
        self.assertEqual(_boundary_tag_before(self.repo, "M10"), "M9")   # 排自己
        self._commit_src()                                              # 只有 M10..HEAD 内含这次改动
        line = _architecture_staleness(self.repo, "M11")
        self.assertIn("M10", line)

    def test_diff_failure_is_stated_not_silenced(self) -> None:
        """`git diff` 失败支路（读不出≠没问题）此前零覆盖（t-050）：如实出声。"""
        from k3dge.engine import seal as seal_mod
        real = seal_mod._git

        def fake(workspace, *args):
            if args and args[0] == "diff":
                return 1, ""
            return real(workspace, *args)

        with mock.patch.object(seal_mod, "_git", fake):
            line = _architecture_staleness(self.repo, "M10")
        self.assertIn("未能对账", line)
        self.assertIn("M9", line)


if __name__ == "__main__":
    unittest.main()
