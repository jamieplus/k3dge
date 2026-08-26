import unittest

from k3dge.engine.manifest import Manifest, ManifestError


class TestManifest(unittest.TestCase):
    def test_ignore_must_be_list_of_strings(self) -> None:
        with self.assertRaises(ManifestError):
            Manifest({"domains": {}, "ignore": "*.pyc"})

    def test_rejects_parent_relative_paths(self) -> None:
        with self.assertRaises(ManifestError):
            Manifest(
                {
                    "package_root": "src",
                    "domains": {
                        "core": {
                            "src": "src/core",
                            "spec": "../secret.md",
                        }
                    },
                }
            )

    def test_rejects_absolute_paths(self) -> None:
        with self.assertRaises(ManifestError):
            Manifest(
                {
                    "package_root": "src",
                    "domains": {"core": {"src": "/tmp/core"}},
                }
            )

    def test_rejects_non_string_src(self) -> None:
        with self.assertRaises(ManifestError):
            Manifest({"domains": {"core": {"src": 1}}})

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


if __name__ == "__main__":
    unittest.main()
