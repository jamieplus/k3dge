import json
import tempfile
import unittest
from pathlib import Path

from k3dge.engine import version


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
        # Make manifest unreadable as JSON to trigger failure in bump's second phase? Instead patch write
        import unittest.mock as mock

        orig_read = Path.read_text

        def flaky_read(self_path, *a, **kw):
            if "manifest.json" in str(self_path) and "0.1.0" not in orig_read(self_path, *a, **kw):
                return orig_read(self_path, *a, **kw)
            return orig_read(self_path, *a, **kw)

        # Simulate failure on second write (manifest)
        with mock.patch.object(Path, "write_text", side_effect=[None, OSError("disk full"), None]):
            # First write is pyproject, second is manifest which fails
            try:
                version.bump_version(self.ws, part="patch")
            except OSError:
                pass
            # pyproject should be rolled back to 0.1.0
            self.assertEqual(version.get_pyproject_version(self.ws), "0.1.0")

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


if __name__ == "__main__":
    unittest.main()
