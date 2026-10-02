import unittest

from k3dge.engine.manifest import Manifest, ManifestError


class TestManifest(unittest.TestCase):
    def test_ignore_must_be_list_of_strings(self) -> None:
        # 断**原因**不只断类型（t-136）：ManifestError 有十条来源，构造器在任何**别的**字段炸了
        # 本测也绿——必须钉是 ignore 这条规则。package_root 显式给出，不靠默认 "src"。
        with self.assertRaisesRegex(ManifestError, "ignore"):
            Manifest({"package_root": "src", "domains": {}, "ignore": "*.pyc"})

    def test_rejects_parent_relative_paths(self) -> None:
        """`..` 必须在**每一个**路径字段上被拒（t-137），且错误要说得出是哪个值。

        `_require_relative_path` 守着 src/spec/tests/package_root 四个口；旧测只喂 spec——
        重构若让某个字段不再走这道守卫（尤其 src/package_root 这些参与前缀比较的），
        旧测照样绿。逐字段参数化＋assertRaisesRegex 绑定危险值。
        """
        cases = [
            ("package_root", "../pkg"),
            ("src", "../outside/src"),
            ("spec", "../secret.md"),
            ("tests", "../tests/x"),
        ]
        for field, bad in cases:
            with self.subTest(field=field):
                dom = {"core": {"src": "src/core", "spec": "docs/specs/core/spec.md",
                                "tests": "tests/unit/core"}}
                if field == "package_root":
                    payload = {"package_root": bad, "domains": dom}
                else:
                    dom["core"][field] = bad
                    payload = {"package_root": "src", "domains": dom}
                with self.assertRaisesRegex(ManifestError, r"\.\."):
                    Manifest(payload)

    def test_rejects_absolute_paths(self) -> None:
        with self.assertRaises(ManifestError):
            Manifest(
                {
                    "package_root": "src",
                    "domains": {"core": {"src": "/tmp/core"}},
                }
            )

    def test_rejects_non_string_src(self) -> None:
        with self.assertRaisesRegex(ManifestError, r"src.*string"):
            Manifest({"package_root": "src", "domains": {"core": {"src": 1}}})

    def test_valid_relative_paths(self) -> None:
        m = Manifest(
            {
                "package_root": "src",
                "ignore": ["*.pyc"],
                "domains": {
                    "core": {
                        "src": "src/core",
                        "spec": "docs/specs/core/spec.md",
                        "tests": "tests/unit/core",
                    }
                },
            }
        )
        self.assertEqual(m.src_path("core"), "src/core")
        self.assertFalse(m.is_ignored("foo.py"))
        self.assertTrue(m.is_ignored("x.pyc"))

    def test_empty_ignore_pattern_does_not_crash(self) -> None:
        m = Manifest({"package_root": "src", "ignore": [""], "domains": {}})
        self.assertFalse(m.is_ignored("foo.py"))

    def test_rejects_windows_drive_path(self) -> None:
        with self.assertRaises(ManifestError):
            Manifest({"package_root": "src", "domains": {"core": {"src": r"C:\Windows"}}})

    def test_rejects_nul_in_path(self) -> None:
        with self.assertRaises(ManifestError):
            Manifest({"package_root": "src", "domains": {"core": {"src": "src/co\x00re"}}})

    def test_non_string_path_fields_rejected(self) -> None:
        """`False`/`0`/`{}` 等非字符串值不得绕过（t-138）：`_validate_domain` 特意"不看真假"
        也要走校验（ocr-080）——旧 `src: 1` 只喂了 int 一种，其余 falsy 值没覆盖。"""
        for bad in (False, 0, [], {}):
            with self.subTest(bad=repr(bad)), self.assertRaises(ManifestError):
                Manifest({"package_root": "src", "domains": {"core": {"src": bad,
                                                                        "spec": "s.md"}}})

    def test_paths_are_normalized_on_return(self) -> None:
        """归一化（t-138）：`"./src//core"` 能过校验但原样存下来会让下游纯前缀比较静默失效。
        旧唯一正例喂的是已规范路径，从没经过这条支路。"""
        m = Manifest({"package_root": "src",
                      "domains": {"core": {"src": "./src//core", "spec": "docs/specs/./core/spec.md"}}})
        self.assertEqual(m.src_path("core"), "src/core")
        self.assertEqual(m.domains["core"]["spec"], "docs/specs/core/spec.md")
        # 归一后的 src 才谈得上 package_root 前缀比较
        self.assertTrue(m.under_package_root(m.src_path("core")))

    def test_directory_ignore_pattern_matches_contents(self) -> None:
        """目录形模式（t-138 的 core/prefix 分支存在理由）：`"src/gen"` 必须盖住其下任意文件。"""
        m = Manifest({"package_root": "src", "ignore": ["src/gen"], "domains": {}})
        self.assertTrue(m.is_ignored("src/gen/x.py"), "目录模式失效＝被忽略的生成物会进闸")
        self.assertTrue(m.is_ignored("src/gen/sub/y.py"))
        self.assertFalse(m.is_ignored("src/keeper/z.py"))
        self.assertFalse(m.is_ignored("src/gentle/a.py"))   # 前缀判据要认路径分量，不做字符串前缀


if __name__ == "__main__":
    unittest.main()
