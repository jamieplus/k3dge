import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from k3dge.engine.diff import _parse_porcelain, _strip_quotes, get_changed_files, resolve_base


class TestDiff(unittest.TestCase):
    def test_parse_rename_takes_destination(self) -> None:
        self.assertEqual(_parse_porcelain("R  old.py -> new.py\n"), ["new.py"])

    def test_parse_quoted_path(self) -> None:
        self.assertEqual(_parse_porcelain('?? "foo bar.py"\n'), ["foo bar.py"])

    def test_strip_quotes_unescapes(self) -> None:
        self.assertEqual(_strip_quotes('"a\\"b"'), 'a"b')

    def test_k3dge_base_sha_includes_committed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True, capture_output=True)
            (repo / "a.txt").write_text("1\n", encoding="utf-8")
            subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "one"], cwd=repo, check=True, capture_output=True)
            first = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
            ).stdout.strip()
            (repo / "b.txt").write_text("2\n", encoding="utf-8")
            subprocess.run(["git", "add", "b.txt"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "two"], cwd=repo, check=True, capture_output=True)
            with mock.patch.dict(os.environ, {"K3DGE_BASE_SHA": first}):
                files = get_changed_files(repo)
            self.assertIn("b.txt", files)

    def test_resolve_base_falls_back_to_head(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "dev"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True, capture_output=True)
            (repo / "a.txt").write_text("1\n", encoding="utf-8")
            subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "one"], cwd=repo, check=True, capture_output=True)
            self.assertEqual(resolve_base(repo), "HEAD")


if __name__ == "__main__":
    unittest.main()
