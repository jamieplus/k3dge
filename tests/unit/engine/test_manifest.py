import unittest

from k3dge.engine.manifest import Manifest, ManifestError


class TestManifest(unittest.TestCase):
    def test_ignore_must_be_list_of_strings(self) -> None:
        # 断**原因**不只断类型（t-136）：ManifestError 有十条来源，构造器在任何**别的**字段炸了
        # 本测也绿——必须钉是 ignore 这条规则。package_root 显式给出，不靠默认 "src"。
        with self.assertRaisesRegex(ManifestError, "ignore"):
            Manifest({"package_root": "src", "domains": {}, "ignore": "*.pyc"})
        # ocr2-475：`_parse_ignore` 的第二个条件（"of strings"）此前零覆盖——元素非串
        # 若被放行，坏模式会到 `is_ignored` 里 `.replace` 抛 AttributeError 炸闸。
        with self.assertRaisesRegex(ManifestError, "ignore"):
            Manifest({"package_root": "src", "domains": {}, "ignore": ["*.pyc", 1]})
        # `null` 归一为 []（合法，不抛）——边界也要钉住
        m = Manifest({"package_root": "src", "domains": {}, "ignore": None})
        self.assertEqual(m.ignore, [])

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
        # ocr2-476：四个路径字段共用 `_require_relative_path`；只喂 src 且不绑原因，
        # 会让 `package_root/spec/tests` 脱离该守卫、或改成只拦 `..` 都照样绿。
        cases = [
            ("package_root", "/abs/pkg"),
            ("src", "/tmp/core"),
            ("spec", "/etc/passwd"),
            ("tests", "/abs/tests"),
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
                with self.assertRaisesRegex(ManifestError, "must be relative"):
                    Manifest(payload)

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
        # ocr2-476：绑原因（都是 `must be relative`），且四个字段都走同一守卫。
        cases = [("package_root", r"C:\pkg"), ("src", r"C:\Windows"),
                 ("spec", r"D:\s.md"), ("tests", r"E:\t")]
        for field, bad in cases:
            with self.subTest(field=field):
                dom = {"core": {"src": "src/core", "spec": "docs/specs/core/spec.md",
                                "tests": "tests/unit/core"}}
                if field == "package_root":
                    payload = {"package_root": bad, "domains": dom}
                else:
                    dom["core"][field] = bad
                    payload = {"package_root": "src", "domains": dom}
                with self.assertRaisesRegex(ManifestError, "must be relative"):
                    Manifest(payload)

    def test_rejects_nul_in_path(self) -> None:
        # ocr2-476：NUL 分支的原因消息必须被绑住，且逐字段覆盖。
        cases = [("package_root", "src\x00x"), ("src", "src/co\x00re"),
                 ("spec", "docs/specs/co\x00re/spec.md"), ("tests", "tests/co\x00re")]
        for field, bad in cases:
            with self.subTest(field=field):
                dom = {"core": {"src": "src/core", "spec": "docs/specs/core/spec.md",
                                "tests": "tests/unit/core"}}
                if field == "package_root":
                    payload = {"package_root": bad, "domains": dom}
                else:
                    dom["core"][field] = bad
                    payload = {"package_root": "src", "domains": dom}
                with self.assertRaisesRegex(ManifestError, "NUL"):
                    Manifest(payload)

    def test_non_string_path_fields_rejected(self) -> None:
        """`False`/`0`/`{}` 等非字符串值不得绕过（t-138）：`_validate_domain` 特意"不看真假"
        也要走校验（ocr-080）——旧 `src: 1` 只喂了 int 一种，其余 falsy 值没覆盖。"""
        for bad in (False, 0, [], {}):
            with self.subTest(bad=repr(bad)), self.assertRaises(ManifestError):
                Manifest({"package_root": "src", "domains": {"core": {"src": bad,
                                                                        "spec": "s.md"}}})
        # ocr2-477：`None`/`""` 是**故意**走另一条路（归一成 ""，不抛）——旧测只喂了会
        # 抛的非串值，于是"把 None 误送进 _require_relative_path"或"存成 None"都测不到。
        for empty in (None, ""):
            with self.subTest(empty=repr(empty)):
                m = Manifest({"package_root": "src",
                              "domains": {"core": {"src": empty, "spec": "s.md", "tests": empty}}})
                self.assertEqual(m.domains["core"]["src"], "")
                self.assertEqual(m.domains["core"]["tests"], "")
        # 非串守卫对 spec/tests 同用（此前只探 src）
        for field in ("spec", "tests"):
            with self.subTest(field=field):
                with self.assertRaises(ManifestError):
                    Manifest({"package_root": "src",
                              "domains": {"core": {"src": "src/core", field: 5}}})

    def test_paths_are_normalized_on_return(self) -> None:
        """归一化（t-138）：`"./src//core"` 能过校验但原样存下来会让下游纯前缀比较静默失效。
        旧唯一正例喂的是已规范路径，从没经过这条支路。"""
        m = Manifest({"package_root": "src",
                      "domains": {"core": {"src": "./src//core", "spec": "docs/specs/./core/spec.md"}}})
        self.assertEqual(m.src_path("core"), "src/core")
        self.assertEqual(m.domains["core"]["spec"], "docs/specs/core/spec.md")
        # 归一后的 src 才谈得上 package_root 前缀比较
        self.assertTrue(m.under_package_root(m.src_path("core")))
        # ocr2-478：真回归是 **package_root 自身**未归一（"./src"）——上面手喂已归一的
        # "src" 让前缀断言恒真。这里显式喂未归一 package_root，并钉分量边界。
        m2 = Manifest({"package_root": "./src", "domains": {"core": {"src": "src/core"}}})
        self.assertEqual(m2.package_root, "src")
        self.assertTrue(m2.under_package_root("src/a.py"))
        self.assertFalse(m2.under_package_root("srcside/a.py"), "前缀比较必须认路径分量")

    def test_directory_ignore_pattern_matches_contents(self) -> None:
        """目录形模式（t-138 的 core/prefix 分支存在理由）：`"src/gen"` 必须盖住其下任意文件。"""
        m = Manifest({"package_root": "src", "ignore": ["src/gen"], "domains": {}})
        self.assertTrue(m.is_ignored("src/gen/x.py"), "目录模式失效＝被忽略的生成物会进闸")
        self.assertTrue(m.is_ignored("src/gen/sub/y.py"))
        self.assertFalse(m.is_ignored("src/keeper/z.py"))
        self.assertFalse(m.is_ignored("src/gentle/a.py"))   # 前缀判据要认路径分量，不做字符串前缀


if __name__ == "__main__":
    unittest.main()
