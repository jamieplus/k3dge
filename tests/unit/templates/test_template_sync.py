import pathlib
import unittest

from k3dge.engine.pairs import PAIRS

def _find_repo_root() -> pathlib.Path:
    """仓根用**标记反查**（t-330）：`parents[3]` 把文件深度焊死——测试挪一层、或从
    安装/打包副本里跑，ROOT 静默指错，失败伪装成子测试里的 FileNotFoundError。
    稳定标记＝`pyproject.toml` ∧ `src/k3dge/` ∧ `docs/specs/`。找不到就大声炸。"""
    here = pathlib.Path(__file__).resolve()
    for cand in here.parents:
        if ((cand / "pyproject.toml").is_file() and (cand / "src" / "k3dge").is_dir()
                and (cand / "docs" / "specs").is_dir()):
            return cand
    raise AssertionError(f"从 {here} 向上找不到 k3dge 仓根——别把本文件搬出 tests/**/")


ROOT = _find_repo_root()
ASSETS = ROOT / "src/k3dge/templates/assets"


class TestTemplateSync(unittest.TestCase):
    """Assets in src/k3dge/templates/assets must stay identical to the repo's own scripts."""

    def test_templates_match_repo_scripts(self) -> None:
        # 登记表自身不许空转（t-327）：PAIRS 被搬空/缩水时循环体一行不跑也"通过"——
        # 同类前科见 INC-20260827（漏一条 PAIRS ⇒ TEMPLATE_DRIFT 恒绿）。给下限。
        self.assertGreaterEqual(len(PAIRS), 60,
                                f"PAIRS 只剩 {len(PAIRS)} 条——守卫失去保护面，先问谁被删了")
        for asset, rel in PAIRS:
            with self.subTest(asset=asset):
                # 两侧存在性**先点名**（t-328）：删了一侧时 read_text 的 FileNotFoundError
                # 以"测试崩溃"面目出现，说不清哪侧没了——而那正是 TEMPLATE_DRIFT 闸要
                # 当违例报的形状。断言给出资产侧/主仓侧的归属。
                a, b = ASSETS / asset, ROOT / rel
                self.assertTrue(a.is_file(), f"资产侧缺失：{a}")
                self.assertTrue(b.is_file(), f"主仓侧缺失：{b}（PAIRS 指向已删/改名的文件？）")
                # 字节锁的比较必须比**字节**：`read_text()` 无 encoding ⇒ 按 locale 解码，
                # 跨平台/CI locale 不同时同一对文件会被判"漂移"或掩盖真漂移（t-326）
                tpl = a.read_text(encoding="utf-8").rstrip("\n")
                act = b.read_text(encoding="utf-8").rstrip("\n")
                self.assertEqual(tpl, act, f"{asset} drifted from {rel}")

    # 渲染型模板：无主仓对件（占位由 scaffold 填写后下发）——新资产必须进 PAIRS 或这张表，
    # 手着"四件套"里登记一步（INC-20260827-AST-template-sync-protocols 的病根就是漏登记静默）。
    _RENDER_ONLY = {
        "adr-readme.md.template",
        "architecture.md.template",
        "gitignore.template",
        "mcp-bridge.md.template",
        "reviews-summary.md.template",
        "reviews/LEFTOVERS.md",
    }

    def test_asset_inventory_is_fully_registered(self) -> None:
        """清单从**目录反查**（t-329）：旧测的手抄名单 43 项已过时（rules/08、11、12、
        gate.*/init.*/pre-commit/commit-msg 等十几件全缺），而且它只验"名单里的存在"——
        **新增**资产不登记照样绿。现在：盘上每个文件必须可归位，登记表也不许多指。"""
        on_disk = {p.relative_to(ASSETS).as_posix() for p in ASSETS.rglob("*") if p.is_file()}
        registered = {a for a, _rel in PAIRS} | self._RENDER_ONLY
        self.assertEqual(sorted(on_disk - registered), [],
                         "assets 出现未登记文件——进 PAIRS 或 _RENDER_ONLY，否则下发面静默漏项")
        self.assertEqual(sorted(registered - on_disk), [], "登记表指向不存在的资产")
        self.assertGreaterEqual(len(on_disk), 60, f"assets 面缩水到 {len(on_disk)}？")
        for _asset, rel in PAIRS:
            self.assertTrue((ROOT / rel).is_file(), f"PAIRS 主仓侧缺件：{rel}")


if __name__ == "__main__":
    unittest.main()
