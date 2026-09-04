"""bundle：内容构成（范围/排除/脱敏/签名/manifest）× store 存取（v2，git tree）。"""
from __future__ import annotations

import json
import tarfile  # noqa: F401  (回退路断言用不到，保留 import 让旧环境差异显形)
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from k3dge.engine.bundle import build_bundle, extract_signatures, load_bundle_config
from k3dge.engine.store import GitStore


def _mk_ws(root: Path) -> None:
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "mod.py").write_text(
        "from pkg.dep import helper\n\nAPI_KEY = 'sekrit-123'\n\n"
        "def run(x: int, y: str = 'a') -> bool:\n    return helper(x) > 0\n",
        encoding="utf-8",
    )
    (root / "src" / "pkg" / "dep.py").write_text(
        "def helper(x: int) -> int:\n    # body must not leak into signatures\n    return x * 2\n",
        encoding="utf-8",
    )
    (root / "src" / "pkg" / "__pycache__").mkdir()
    (root / "src" / "pkg" / "__pycache__" / "junk.pyc").write_bytes(b"\x00\x01")
    (root / ".DS_Store").write_bytes(b"noise")


def _materialized(ws: Path, b: dict) -> dict:
    dest = ws / ".k3dge" / "served" / b["hash"].split(":")[-1][:12]
    GitStore(ws).get(b["ref"], dest)
    return {p.relative_to(dest).as_posix(): p.read_bytes() for p in dest.rglob("*") if p.is_file()}


class TestBundle(unittest.TestCase):
    def test_v2_store_format_and_determinism(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            _mk_ws(ws)
            b1 = build_bundle(ws, ["src"], milestone_id="M1")
            b2 = build_bundle(ws, ["src"], milestone_id="M1")
            self.assertEqual(b1["format"], "git-bundle")
            self.assertTrue(b1["commit"] and b1["bundle_file"] and (ws / b1["bundle_file"]).is_file())
            self.assertEqual(b1["hash"], b2["hash"])          # 同内容必同基线
            self.assertTrue(b1["ref"].startswith("cas://sha256:"))
            self.assertIsNone(b1["path"])                      # 内容在对象库，无文件路径
            names = set(_materialized(ws, b1))
            self.assertIn("MANIFEST.json", names)
            self.assertIn("target/src/pkg/mod.py", names)

    def test_noise_excluded(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            _mk_ws(ws)
            b = build_bundle(ws, ["src", ".DS_Store"])
            paths = [f["path"] for f in b["manifest"]["files"]]
            self.assertTrue(any(p.endswith("mod.py") for p in paths))
            self.assertFalse(any("__pycache__" in p or ".DS_Store" in p for p in paths))

    def test_scrub_before_leaving_boundary(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            _mk_ws(ws)
            (ws / ".agent").mkdir(exist_ok=True)
            (ws / ".agent" / "bundle.toml").write_text('scrub_keys = ["API_KEY"]\n', encoding="utf-8")
            self.assertEqual(load_bundle_config(ws)["scrub_keys"], ["API_KEY"])
            b = build_bundle(ws, ["src"])
            body = _materialized(ws, b)["target/src/pkg/mod.py"].decode("utf-8")
            self.assertNotIn("sekrit-123", body)
            self.assertIn("<redacted>", body)

    def test_signatures_headers_not_bodies(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            _mk_ws(ws)
            b = build_bundle(ws, ["src/pkg/mod.py"])
            self.assertIn("src/pkg/dep.py", b["manifest"]["signatures"])
            blob = _materialized(ws, b)["signatures/src/pkg/dep.py.sig"].decode("utf-8")
            self.assertIn("def helper(x: int) -> int", blob)
            self.assertNotIn("x * 2", blob)

    def test_manifest_lists_every_member_with_sha(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            _mk_ws(ws)
            b = build_bundle(ws, ["src"])
            m = json.loads(_materialized(ws, b)["MANIFEST.json"])
            self.assertEqual(m["bundle_version"], 3)
            for ent in m["files"]:
                self.assertEqual(len(ent["sha256"]), 64)

    def test_provenance_explains_baseline_shift(self) -> None:
        # ④：改一行 ignore 配置 ⇒ config_digest 变、可归因（镜头三的可复现性件）
        with TemporaryDirectory() as d:
            ws = Path(d)
            _mk_ws(ws)
            b1 = build_bundle(ws, ["src"])
            (ws / ".agent").mkdir(exist_ok=True)
            (ws / ".agent" / "bundle.toml").write_text('ignore = ["__pycache__", ".DS_Store", "logs"]\n', encoding="utf-8")
            b2 = build_bundle(ws, ["src"])
            import json as _j
            m1 = _j.loads(b1["manifest"]["pack_provenance"]["config_digest"]) if False else b1["manifest"]["pack_provenance"]
            m2 = b2["manifest"]["pack_provenance"]
            self.assertNotEqual(m1["config_digest"], m2["config_digest"])

    def test_store_diff_is_the_ratchet_delta(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            _mk_ws(ws)
            b1 = build_bundle(ws, ["src"])
            (ws / "src" / "pkg" / "new.py").write_text("z = 1\n", encoding="utf-8")
            b2 = build_bundle(ws, ["src"])
            delta = GitStore(ws).diff(b1["ref"], b2["ref"])
            self.assertIn("+", {c for c, _, _ in delta})
            self.assertTrue(any(p.endswith("new.py") for c, p, _ in delta if c == "+"))

    def test_extract_signatures_tolerates_garbage(self) -> None:
        self.assertEqual(extract_signatures("def broken(:"), "")


if __name__ == "__main__":
    unittest.main()
