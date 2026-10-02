import json
import tempfile
import unittest
from pathlib import Path

from k3dge.engine import version
import shutil


def _write_pyproject(ws: Path, ver: str) -> None:
    ws.joinpath("pyproject.toml").write_text(f'[project]\nname="test"\nversion = "{ver}"\n', encoding="utf-8")


def _write_manifest(ws: Path, ver: str | None) -> None:
    data: dict = {"package_root": "src", "domains": {}}
    if ver is not None:
        data["version"] = ver
    (ws / ".agent").mkdir(exist_ok=True)
    (ws / ".agent" / "manifest.json").write_text(json.dumps(data), encoding="utf-8")


def _write_init(ws: Path, ver: str | None) -> None:
    p = ws / "src" / "k3dge" / "__init__.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    if ver is None:
        p.write_text("", encoding="utf-8")
    else:
        p.write_text(f'__version__ = "{ver}"\n', encoding="utf-8")


class TestVersion(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_parse_and_format(self) -> None:
        self.assertEqual(version.parse_version("1.2.3"), (1, 2, 3))
        self.assertEqual(version.format_version(1, 2, 3), "1.2.3")
        with self.assertRaises(ValueError):
            version.parse_version("1.-2.3")

    def test_get_version_prefers_pyproject(self) -> None:
        _write_pyproject(self.ws, "1.2.3")
        _write_manifest(self.ws, "9.9.9")
        self.assertEqual(version.get_version(self.ws), "1.2.3")

    def test_get_version_fallback_to_manifest(self) -> None:
        _write_manifest(self.ws, "0.2.0")
        self.assertEqual(version.get_version(self.ws), "0.2.0")
        _write_manifest(self.ws, "0.1.0")
        self.assertEqual(version.get_version(self.ws), "0.1.0")

    def test_validate_mismatch_pyproject_vs_manifest(self) -> None:
        _write_pyproject(self.ws, "0.1.0")
        _write_manifest(self.ws, "0.1.1")
        _write_init(self.ws, "0.1.0")
        violations = version.validate_versions(self.ws)
        self.assertTrue(any(v.rule_id == "VERSION_MISMATCH" for v in violations))

    def test_validate_missing_manifest_field_is_drift(self) -> None:
        _write_pyproject(self.ws, "0.1.0")
        _write_manifest(self.ws, None)  # no version key
        _write_init(self.ws, "0.1.0")
        violations = version.validate_versions(self.ws)
        # manifest version None != pyproject 0.1.0 → drift
        self.assertTrue(any(v.rule_id == "VERSION_MISMATCH" for v in violations))

    def test_downstream_layout_bump_and_validate_use_manifest_branch(self) -> None:
        """下游布局把 `_init_path` 的 manifest 支路**走满闭环**（t-291）。

        本文件其余用例都把 `__version__` 写进 `src/k3dge/__init__.py`——只经过
        fallback 那半条解析路。下游脚手架（name=myproj，包在 `src/myproj/`）若
        解析错位，`bump_version` 会"成功"却不动真文件、`validate_versions` 靠
        同一处错位继续绿 ⇒ 三处一致的 promise 当场失效，没有测会红。
        """
        ws = self.ws
        pkg = ws / "src" / "myproj"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")
        (ws / ".agent").mkdir(exist_ok=True)
        (ws / ".agent" / "manifest.json").write_text(json.dumps(
            {"name": "myproj", "package_root": "src", "domains": {}, "version": "0.1.0"}),
            encoding="utf-8")
        _write_pyproject(ws, "0.1.0")
        self.assertEqual(version.validate_versions(ws), [])
        self.assertEqual(version.bump_version(ws, "patch"), "0.1.1")
        self.assertIn("0.1.1", (pkg / "__init__.py").read_text(encoding="utf-8"))
        # fallback 支路不许在下游布局里凭空造 `src/k3dge/`——造了＝解析根本没走 manifest
        self.assertFalse((ws / "src" / "k3dge").exists())
        self.assertEqual(version.validate_versions(ws), [])

    def test_bump_patch_updates_all(self) -> None:
        _write_pyproject(self.ws, "0.1.0")
        _write_manifest(self.ws, "0.1.0")
        _write_init(self.ws, "0.1.0")
        new_v = version.bump_version(self.ws, part="patch")
        self.assertEqual(new_v, "0.1.1")
        self.assertEqual(version.get_pyproject_version(self.ws), "0.1.1")
        self.assertEqual(version.get_manifest_version(self.ws), "0.1.1")
        self.assertEqual(version.get_init_version(self.ws), "0.1.1")

    def test_bump_is_atomic_on_failure(self) -> None:
        _write_pyproject(self.ws, "0.1.0")
        _write_manifest(self.ws, "0.1.0")
        _write_init(self.ws, "0.1.0")
        import unittest.mock as mock

        # 失效点打在写原语上（而非 `Path.write_text`：`_atomic_write` 走 fdopen，
        # 桩错层就会把"注入失败"变成"把目标写成空文件"的假象）。
        # ocr2-536：按**路径**注入（manifest）而不是按调用序号——序号版在写序
        # 变化/新增版本文件时会把故障悄悄挪到别的文件，测试仍绿。
        real = version._atomic_write
        seen: list = []

        def flaky(path, text):
            seen.append(str(path))
            if str(path).endswith("manifest.json"):
                raise OSError("disk full")      # 第二件＝manifest ⇒ 真失败
            real(Path(path), text)              # 首写与回滚都落真盘

        with mock.patch.object(version, "_atomic_write", side_effect=flaky):
            with self.assertRaises(OSError):
                version.bump_version(self.ws, part="patch")
        self.assertTrue(any(x.endswith("manifest.json") for x in seen), seen)
        self.assertTrue([x for x in seen if x.endswith("pyproject.toml")], seen)
        # ocr2-537：三个镜像文件在盘上都必须是旧版（任一停在半新半旧都红）
        self.assertEqual(version.get_pyproject_version(self.ws), "0.1.0")
        self.assertEqual(version.get_manifest_version(self.ws), "0.1.0")
        self.assertEqual(version.get_init_version(self.ws), "0.1.0")

    def test_bump_rolls_back_earlier_files_when_last_write_fails(self) -> None:
        """ocr2-537：把失效点挪到**最后一件**（__init__.py）——pyproject/manifest 已写盘，
        回滚循环若在第一件收手/漏掉尾件就会留下新值，此测必红。"""
        _write_pyproject(self.ws, "0.1.0")
        _write_manifest(self.ws, "0.1.0")
        _write_init(self.ws, "0.1.0")
        import unittest.mock as mock

        real = version._atomic_write

        def flaky(path, text):
            if str(path).endswith("__init__.py"):
                raise OSError("disk full")
            real(Path(path), text)

        with mock.patch.object(version, "_atomic_write", side_effect=flaky):
            with self.assertRaises(OSError):
                version.bump_version(self.ws, part="patch")
        self.assertEqual(version.get_pyproject_version(self.ws), "0.1.0")
        self.assertEqual(version.get_manifest_version(self.ws), "0.1.0")
        self.assertEqual(version.get_init_version(self.ws), "0.1.0")

    def test_append_changelog(self) -> None:
        _write_pyproject(self.ws, "0.1.0")
        p = version.append_changelog(self.ws, "0.1.1", notes="feat: test")
        self.assertTrue(p.exists())
        text = p.read_text(encoding="utf-8")
        self.assertIn("## [0.1.1]", text)
        self.assertIn("feat: test", text)

    def test_init_path_uses_manifest(self) -> None:
        # downstream with package_root src and name myproj
        (self.ws / ".agent").mkdir(exist_ok=True)
        (self.ws / ".agent" / "manifest.json").write_text(
            json.dumps({"name": "myproj", "package_root": "src", "domains": {}, "version": "0.1.0"}), encoding="utf-8"
        )
        (self.ws / "src" / "myproj").mkdir(parents=True)
        (self.ws / "src" / "myproj" / "__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")
        # _init_path should resolve to src/myproj/__init__.py via manifest
        init_p = version._init_path(self.ws)
        self.assertEqual(init_p, self.ws / "src" / "myproj" / "__init__.py")




class TestVersionParsing(unittest.TestCase):
    """合法 TOML 写法都要认；坏 manifest 不得静默放行版本闸（ocr-335/337/338）。"""

    def _ws(self, pyproject: str, manifest: str | None = "{\"version\": \"0.1.0\"}") -> Path:
        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        (ws / "pyproject.toml").write_text(pyproject, encoding="utf-8")
        if manifest is not None:
            (ws / ".agent").mkdir()
            (ws / ".agent" / "manifest.json").write_text(manifest, encoding="utf-8")
        return ws

    def test_single_quote_and_indent_and_inline_table(self) -> None:
        for body in ('[project]\nversion = \'0.1.0\'\n',
                     '[project]\n  version = "0.1.0"\n',
                     'project = { name = "x", version = "0.1.0" }\n'):
            ws = self._ws(body)
            self.assertEqual(version.get_pyproject_version(ws), "0.1.0", body)

    def test_bump_roundtrips_every_accepted_toml_form(self) -> None:
        """ocr2-538：读侧认的合法 TOML，写侧必须能 round-trip（旧版行内表直接
        RuntimeError，缩进版静默拍平）。"""
        import re as _re

        cases = {
            "single_quote": ('[project]\nversion = \'0.1.0\'\n',
                             lambda t: '0.1.1' in t),
            "indented": ('[project]\n  version = "0.1.0"\n',
                         lambda t: '  version = "0.1.1"' in t),      # 缩进保留
            "inline_table": ('project = { name = "x", version = "0.1.0" }\n',
                             lambda t: 'version = "0.1.1"' in t),
        }
        for name, (body, ok) in cases.items():
            with self.subTest(form=name):
                ws = self._ws(body)
                self.assertEqual(version.bump_version(ws, part="patch"), "0.1.1")
                text = (ws / "pyproject.toml").read_text(encoding="utf-8")
                self.assertTrue(ok(text), text)
                self.assertEqual(version.get_pyproject_version(ws), "0.1.1", text)
                # 无关内容不得丢（行内表的 name 仍在）
                if name == "inline_table":
                    self.assertIn('name = "x"', text)
                # 缩进版的行首空白不得被拍平
                if name == "indented":
                    self.assertIsNotNone(_re.search(r"^  version = ", text, _re.M), text)

    def test_dynamic_version_reads_as_absent_not_error(self) -> None:
        ws = self._ws('[project]\nname = "x"\ndynamic = ["version"]\n')
        self.assertIsNone(version.get_pyproject_version(ws))
        self.assertEqual(version.validate_versions(ws), [])   # 与 get_version 同口径：不判违规
        no_canon = self._ws('[project]\nname = "x"\ndynamic = ["version"]\n', manifest=None)
        with self.assertRaises(FileNotFoundError):            # 真没 canonical ⇒ 明确报错
            version.bump_version(no_canon, part="patch")

    def test_manifest_init_drift_without_pyproject_is_a_violation(self) -> None:
        """ocr2-539：`validate_versions` 的 `py_v is None and mf_v != init_v` 分支
        （manifest↔`__init__` 半边，下游 `dynamic = ["version"]` 脚手架依赖它）此前无测。"""
        ws = self._ws('[project]\nname = "x"\ndynamic = ["version"]\n', '{"version": "0.1.0"}')
        _write_init(ws, "0.2.0")
        vs = version.validate_versions(ws)
        self.assertEqual([v.rule_id for v in vs], ["VERSION_MISMATCH"], vs)
        self.assertIn("manifest.json=0.1.0", vs[0].message)
        # 一致时不得报（该分支不是"永远红"）
        ws2 = self._ws('[project]\nname = "x"\ndynamic = ["version"]\n', '{"version": "0.1.0"}')
        _write_init(ws2, "0.1.0")
        self.assertEqual(version.validate_versions(ws2), [])

    def test_bump_skips_pyproject_without_version_key(self) -> None:
        ws = self._ws('[project]\nname = "x"\ndynamic = ["version"]\n')
        self.assertEqual(version.get_manifest_version(ws), "0.1.0")
        version.bump_version(ws, part="patch")
        self.assertEqual(version.get_manifest_version(ws), "0.1.1")

    def test_corrupt_manifest_is_a_violation_not_silence(self) -> None:
        ws = self._ws('[project]\nname = "x"\nversion = "0.1.0"\n', "{ not json")
        vs = version.validate_versions(ws)
        self.assertTrue(vs, "坏 JSON 的 manifest 让版本闸直接 return []")
        self.assertEqual(vs[0].rule_id, "VERSION_MISMATCH")
        # 必须走 `manifest_read_error` 支路，不能靠 `get_manifest_version` 回 None 兜底（ocr2-125）。
        # 删掉前者也照样红 ⇒ 测不出回归。直接断言成因函数。
        self.assertTrue(version.manifest_read_error(ws), "坏 JSON 必须被 manifest_read_error 指认")

    def test_non_table_project_does_not_crash(self) -> None:
        # `project` 是标量/数组（合法 TOML）时不得抛 AttributeError（ocr2-085）。
        self.assertIsNone(version._pyproject_version('project = "x"\n'))
        self.assertIsNone(version._pyproject_version('project = [1, 2]\n'))

    def test_non_object_manifest_returns_none(self) -> None:
        # `[]`/`"x"`/`1`/`null` 都是合法 JSON 但无 `.get`（ocr2-086）。
        ws = self._ws('[project]\nname = "x"\nversion = "0.1.0"\n', "[]")
        self.assertIsNone(version.get_manifest_version(ws))

    def test_bump_writes_project_section_only(self) -> None:
        # `[tool.x]` 的 version 在前时，不得改错地方（ocr2-087）。
        ws = self._ws('[tool.x]\nversion = "9.9.9"\n[project]\nname = "x"\nversion = "0.1.0"\n',
                      '{"version": "0.1.0"}')
        version.bump_version(ws, part="patch")
        text = (ws / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "0.1.1"', text)
        self.assertIn('[tool.x]\nversion = "9.9.9"', text)

    def test_relaxed_fallback_pairs_project_table(self) -> None:
        """无 tomllib 的 3.10 回退：`[[array]]`/行尾注释不得让段对错位（ocr2-327）。"""
        self.assertEqual(
            version._pyproject_version_relaxed(
                '[tool.pytest.ini_options]\naddopts = "-q"\n\n'
                '[project]\nname = "x"\nversion = "1.2.3"\n'),
            "1.2.3")
        self.assertEqual(
            version._pyproject_version_relaxed(
                '[[tool.pytest.ini_options]]\nfoo = 1\n\n[project]\nversion = "9.9.9"\n'),
            "9.9.9")

    def test_non_utf8_pyproject_is_a_violation_not_traceback(self) -> None:
        """非 UTF-8 的 pyproject 不得让版本闸裸抛（ocr2-328）。"""
        ws = self._ws('[project]\nname = "x"\nversion = "0.1.0"\n')
        (ws / "pyproject.toml").write_bytes(b"\xff\xfe[project]\nversion = \"0.1.0\"\n")
        vs = version.validate_versions(ws)
        self.assertTrue(vs)
        self.assertEqual(vs[0].rule_id, "VERSION_MISMATCH")

    def test_non_utf8_manifest_bump_raises_loudly(self) -> None:
        """非 UTF-8 manifest 提版要带明确 ValueError，而非 TypeError/半途（ocr2-329）。"""
        ws = self._ws('[project]\nname = "x"\nversion = "0.1.0"\n')
        (ws / ".agent" / "manifest.json").write_bytes(b"\xff\xfe{}")
        with self.assertRaises(ValueError):
            version.bump_version(ws, part="patch")


if __name__ == "__main__":
    unittest.main()
