"""Full-consistency contract: manifest domains <-> docs/specs directories.

The evaluator only checks *touched* domains; this test asserts the FULL 1:1
mapping at CI time so drift (missing spec / orphan spec dir / missing tests
dir) is caught even when nothing in that domain was touched.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / ".agent" / "manifest.json"
SPECS_DIR = ROOT / "docs" / "specs"


def _is_relative(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


class TestManifestSpecsFullSync(unittest.TestCase):
    def setUp(self) -> None:
        # 存在性/可解析性在 setUp 里**出干净的红**（t-028）：旧写法 `json.loads(read_text)`
        # 裸抛——manifest 缺失时五个用例（含 `test_manifest_is_present` 自己）全数
        # FileNotFoundError traceback，那句为它准备的消息从没机会说话；ROOT 解错也伪装成
        # "manifest 没了"。先验根、再验件、坏 JSON 给专消息。
        self.assertTrue((ROOT / "pyproject.toml").is_file(),
                        f"仓根解析错误（parents[3] 漂了？）：{ROOT}")
        self.assertTrue(MANIFEST.is_file(), f".agent/manifest.json 缺失：{MANIFEST}")
        try:
            parsed = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self.fail(f".agent/manifest.json 解析失败：{exc}")
        self.assertIsInstance(parsed, dict, "manifest 顶层必须是对象")
        self.manifest = parsed
        # `domains` 缺失/被改名/被清空时旧写法静默回落 `{}` ⇒ 三条逐域断言全部空转仍报绿，
        # 而本文件的存在理由恰恰是抓"没人动的域漂了"（t-029）。空集必须是**红**。
        dom = self.manifest.get("domains")
        self.assertIsInstance(dom, dict, f"manifest.domains 不是对象：{type(dom).__name__}")
        self.assertTrue(dom, ".agent/manifest.json 的 domains 为空 ⇒ 本文件的 1:1 一致性核判空转")
        self.domains = dom

    def test_manifest_is_present(self) -> None:
        # 真正的存在性断言已上提进 setUp（t-028）；本用例保留为契约的**登记位**
        # （报告/审计引用过它），内容对账同一事实、措辞可检索。
        self.assertTrue(MANIFEST.is_file(), ".agent/manifest.json missing")

    def test_every_domain_has_all_registered_paths(self) -> None:
        for domain, cfg in self.domains.items():
            with self.subTest(domain=domain):
                self.assertIsInstance(cfg, dict,
                                      f"domain '{domain}' 注册的不是对象：{cfg!r}")
                for key in ("src", "spec", "tests"):
                    self.assertIn(key, cfg, f"domain '{domain}' missing '{key}'")
                    self.assertIsInstance(cfg[key], str,
                                          f"domain '{domain}' 的 {key} 不是字符串：{cfg[key]!r}")
                    path = ROOT / cfg[key]
                    self.assertTrue(path.exists(), f"domain '{domain}' {key} path missing: {cfg[key]}")

    def test_every_domain_has_spec_dir(self) -> None:
        # 本文件的职责是诊断**坏 manifest**，自己就不许先炸（t-030）：缺 spec 键此前
        # KeyError、cfg 非映射 TypeError——契约测试抛裸错＝CI 只见 traceback；
        # 且没有 subTest，第一个坏域中断整轮，后面的域从没被看。
        for domain, cfg in self.domains.items():
            with self.subTest(domain=domain):
                self.assertIsInstance(cfg, dict,
                                      f"domain '{domain}' 注册的不是对象：{cfg!r}")
                self.assertIn("spec", cfg, f"domain '{domain}' 缺 spec 键")
                self.assertIsInstance(cfg["spec"], str,
                                      f"domain '{domain}' 的 spec 不是字符串：{cfg['spec']!r}")
                spec_dir = (ROOT / cfg["spec"]).parent
                self.assertTrue(
                    spec_dir.is_dir(), f"domain '{domain}' spec dir missing: {spec_dir}"
                )

    def test_no_orphan_spec_dirs(self) -> None:
        # 旧写法在 `docs/specs` 缺失/被改名时抛裸 FileNotFoundError：契约测试"崩"而不是"红"，
        # CI 里只见 traceback，看不出是域路由漂了（t-031）。
        self.assertTrue(SPECS_DIR.is_dir(), f"spec 根目录不存在：{SPECS_DIR}")
        registered = set()
        for domain, cfg in self.domains.items():
            # ocr2-414：循环内无 subTest ⇒ 第一个坏域抛断言即中断整轮；
            # cfg 非映射时 `cfg.get` 抛 AttributeError 裸栈 ⇒ 必须先验映射再取键。
            with self.subTest(domain=domain):
                self.assertIsInstance(cfg, dict,
                                      f"domain '{domain}' 注册的不是对象：{cfg!r}")
                self.assertIn("spec", cfg, f"domain '{domain}' 缺 spec 键")
                spec = cfg["spec"]
                self.assertIsInstance(spec, str, f"domain '{domain}' 的 spec 不是字符串：{spec!r}")
                # ocr2-415：只取 `.parent.name` 会漏判/误判——嵌套路径登记内层名（假阳性），
                # 落在 specs 之外的改名/串位被同名目录顶名认领（假阴性），空值退化成无关名。
                # 先断言解析后确实落在 SPECS_DIR 之下，再用相对首段登记。
                resolved = (ROOT / spec).resolve()
                self.assertTrue(_is_relative(resolved, SPECS_DIR.resolve()),
                                f"domain '{domain}' 的 spec 落在 docs/specs 之外：{spec}")
                rel = resolved.relative_to(SPECS_DIR.resolve())
                registered.add(rel.parts[0])
        actual = {p.name for p in sorted(SPECS_DIR.iterdir())
                  if p.is_dir() and p.name != "_template"}
        orphans = actual - registered
        self.assertEqual(orphans, set(), f"spec dirs without manifest domain: {sorted(orphans)}")

    def test_spec_files_have_required_sections_and_hash(self) -> None:
        try:
            from k3dge.engine import spec_schema
        except ImportError as exc:
            # 直接跑本文件（`python -m unittest`/`__main__`）没有 pytest 的 pythonpath=src，
            # 旧写法 ImportError 崩栈看不出是"环境没配"还是"helper 没了"（t-032）。
            self.skipTest(f"k3dge 不可导入（需 pytest pythonpath=src）：{exc}")

        for domain, cfg in self.domains.items():
            with self.subTest(domain=domain):
                # ocr2-416：直接 `cfg["spec"]` 在坏 manifest 下抛裸 TypeError/KeyError
                # （error 而非 clean red），且本用例是唯一读正文的——先验形状再读盘。
                self.assertIsInstance(cfg, dict,
                                      f"domain '{domain}' 注册的不是对象：{cfg!r}")
                self.assertIn("spec", cfg, f"domain '{domain}' 缺 spec 键")
                self.assertIsInstance(cfg["spec"], str,
                                      f"domain '{domain}' 的 spec 不是字符串：{cfg['spec']!r}")
                spec_path = ROOT / cfg["spec"]
                self.assertTrue(spec_path.is_file(),
                                f"spec 文件缺失：{cfg['spec']}")   # 显式红，不是 read_text 的 FileNotFoundError
                content = spec_path.read_text(encoding="utf-8")
                self.assertEqual(
                    spec_schema.validate_structure(content),
                    [],
                    f"spec for '{domain}' missing required sections",
                )
                self.assertIsNotNone(
                    spec_schema.extract_contract_hash(content),
                    f"spec for '{domain}' has no contract hash (run 'k3dge sync')",
                )


if __name__ == "__main__":
    unittest.main()
