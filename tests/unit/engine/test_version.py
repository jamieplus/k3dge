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
        # 顺序＝[pyproject 成功, manifest 失败] ⇒ 回滚重写 pyproject。
        # 关键：**其余调用走真实写盘**。整桩会把盘上也什么都不写，"回滚成 0.1.0"就成了
        # 恒真（回滚写错内容、写成新值、干脆不滚都测不出来，t-289）。
        real = version._atomic_write
        seen: list = []

        def flaky(path, text):
            seen.append(str(path))
            if len(seen) == 2:                      # 第二件＝manifest ⇒ 真失败
                raise OSError("disk full")
            real(Path(path), text)                  # 首写与回滚都落真盘

        with mock.patch.object(version, "_atomic_write", side_effect=flaky):
            with self.assertRaises(OSError):
                version.bump_version(self.ws, part="patch")
        self.assertTrue([x for x in seen[2:] if x.endswith("pyproject.toml")], seen)
        self.assertEqual(version.get_pyproject_version(self.ws), "0.1.0",
                         "回滚必须把**盘上内容**改回旧版（不是靠桩没写盘蒙对）")

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

    def test_dynamic_version_reads_as_absent_not_error(self) -> None:
        ws = self._ws('[project]\nname = "x"\ndynamic = ["version"]\n')
        self.assertIsNone(version.get_pyproject_version(ws))
        self.assertEqual(version.validate_versions(ws), [])   # 与 get_version 同口径：不判违规
        no_canon = self._ws('[project]\nname = "x"\ndynamic = ["version"]\n', manifest=None)
        with self.assertRaises(FileNotFoundError):            # 真没 canonical ⇒ 明确报错
            version.bump_version(no_canon, part="patch")

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
if __name__ == "__main__":
    unittest.main()
