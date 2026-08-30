import pathlib
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.protocol import (
    ProtocolResolutionError,
    ProtocolResolver,
    validate_protocols_config,
    write_incident,
)


def _ws(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


class TestProtocolResolver(unittest.TestCase):
    def test_resolves_registered_type(self):
        root = Path(__file__).resolve().parents[3]
        ref = ProtocolResolver(root).resolve("audit")
        self.assertEqual(ref.task_type, "audit")
        self.assertEqual(ref.rel, "docs/protocols/audit_default.md")
        self.assertTrue(ref.exists)

    def test_resolve_raw_returns_markdown(self):
        root = Path(__file__).resolve().parents[3]
        text = ProtocolResolver(root).resolve_raw("audit")
        self.assertIn("Audit Protocol", text)

    def test_list_types_includes_registry(self):
        root = Path(__file__).resolve().parents[3]
        self.assertIn("audit", ProtocolResolver(root).list_types())
        self.assertIn("verify", ProtocolResolver(root).list_types())

    def test_unknown_type_raises(self):
        root = Path(__file__).resolve().parents[3]
        with self.assertRaises(ProtocolResolutionError):
            ProtocolResolver(root).resolve("does-not-exist")

    def test_absent_config_falls_back_to_builtin(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ref = ProtocolResolver(root).resolve("audit")
            self.assertEqual(ref.rel, "docs/protocols/audit_default.md")
            # builtin path does not physically exist in the temp dir
            self.assertFalse(ref.exists)


class TestProtocolValidation(unittest.TestCase):
    def test_absent_config_is_graceful(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(validate_protocols_config(Path(d)), [])

    def test_missing_target_file_flags(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _ws(
                root,
                {
                    ".agent/protocols.toml": (
                        '[protocols]\n'
                        'audit = "docs/protocols/missing.md"\n'
                        '[settings]\n'
                        'default = "audit"\n'
                    )
                },
            )
            errs = validate_protocols_config(root)
            self.assertTrue(any(c == "PROTOCOL_REGISTRY_INVALID" for c, _ in errs))

    def test_valid_config_passes(self):
        root = Path(__file__).resolve().parents[3]
        # This repo's own registry must be physically consistent (no false positives).
        self.assertEqual(validate_protocols_config(root), [])

    def test_empty_registry_flags(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _ws(root, {".agent/protocols.toml": "[protocols]\n"})
            errs = validate_protocols_config(root)
            self.assertTrue(any(c == "PROTOCOL_REGISTRY_INVALID" for c, _ in errs))


class TestProtocolPathRouting(unittest.TestCase):
    def _registry(self, root: Path) -> None:
        _ws(
            root,
            {
                ".agent/protocols.toml": (
                    '[protocols]\n'
                    'audit = "docs/protocols/audit_default.md"\n'
                    'verify = "docs/protocols/verify_default.md"\n'
                    '[settings]\n'
                    'default = "audit"\n'
                    '[paths]\n'
                    '"docs/reviews/**" = "audit"\n'
                    '"docs/**" = "verify"\n'
                ),
                "docs/protocols/audit_default.md": "# audit\n",
                "docs/protocols/verify_default.md": "# verify\n",
            },
        )

    def test_resolve_by_path_matches(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._registry(root)
            ref = ProtocolResolver(root).resolve_by_path(root / "docs/reviews/2026-x.md")
            self.assertIsNotNone(ref)
            self.assertEqual(ref.task_type, "audit")

    def test_most_specific_glob_wins(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._registry(root)
            # docs/** maps to verify, but docs/reviews/** (more specific) maps to audit
            ref = ProtocolResolver(root).resolve_by_path(root / "docs/reviews/2026-x.md")
            self.assertEqual(ref.task_type, "audit")
            ref2 = ProtocolResolver(root).resolve_by_path(root / "docs/guides/x.md")
            self.assertEqual(ref2.task_type, "verify")

    def test_no_match_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._registry(root)
            self.assertIsNone(ProtocolResolver(root).resolve_by_path(root / "src/k3dge/engine/x.py"))

    def test_path_maps_to_unregistered_protocol_flags(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _ws(
                root,
                {
                    ".agent/protocols.toml": (
                        '[protocols]\n'
                        'audit = "docs/protocols/audit_default.md"\n'
                        '[paths]\n'
                        '"docs/reviews/**" = "ghost"\n'
                    ),
                    "docs/protocols/audit_default.md": "# audit\n",
                },
            )
            errs = validate_protocols_config(root)
            self.assertTrue(any(c == "PROTOCOL_REGISTRY_INVALID" for c, _ in errs))


class TestProtocolChallenge(unittest.TestCase):
    def _registry(self, root: Path) -> None:
        _ws(
            root,
            {
                ".agent/protocols.toml": (
                    '[protocols]\n'
                    'audit = "docs/protocols/audit_default.md"\n'
                    '[settings]\n'
                    'default = "audit"\n'
                    '[paths]\n'
                    '"docs/reviews/**" = "audit"\n'
                ),
                "docs/protocols/audit_default.md": "# audit protocol\n",
            },
        )

    def test_challenge_is_deterministic_12_hex(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._registry(root)
            c1 = ProtocolResolver(root).challenge(target=root / "docs/reviews/x.md", task_id="T1")
            c2 = ProtocolResolver(root).challenge(target=root / "docs/reviews/x.md", task_id="T1")
            self.assertEqual(c1, c2)
            self.assertEqual(len(c1), 12)
            self.assertTrue(all(ch in "0123456789abcdef" for ch in c1))

    def test_challenge_binds_task_id(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._registry(root)
            a = ProtocolResolver(root).challenge(target=root / "docs/reviews/x.md", task_id="T1")
            b = ProtocolResolver(root).challenge(target=root / "docs/reviews/x.md", task_id="T2")
            self.assertNotEqual(a, b)

    def test_challenge_none_when_no_protocol(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._registry(root)
            self.assertIsNone(ProtocolResolver(root).challenge(target=root / "src/x.py", task_id="T1"))


class TestProtocolEntryTicket(unittest.TestCase):
    def _registry_with_constraints(self, root: Path) -> None:
        _ws(
            root,
            {
                ".agent/protocols.toml": (
                    '[protocols]\n'
                    'audit = "docs/protocols/audit_default.md"\n'
                    '[settings]\n'
                    'default = "audit"\n'
                    '[paths]\n'
                    '"docs/reviews/**" = "audit"\n'
                ),
                "docs/protocols/audit_default.md": (
                    "# audit\n\n## Constraints\n"
                    "- must write 12-column report\n"
                    "- must run 5-pass lens\n"
                ),
            },
        )

    def test_expected_constraints_parsed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._registry_with_constraints(root)
            cons = ProtocolResolver(root).expected_constraints(target=root / "docs/reviews/x.md")
            self.assertEqual(cons, ["must write 12-column report", "must run 5-pass lens"])

    def test_valid_ticket_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._registry_with_constraints(root)
            ticket = {
                "protocol": "audit",
                "task_id": "T1",
                "binding": [
                    {"constraint": "must write 12-column report", "how": "emit 12-col to docs/reviews/x.md"},
                    {"constraint": "must run 5-pass lens", "how": "run passes 1-5"},
                ],
            }
            self.assertEqual(
                ProtocolResolver(root).validate_ticket(target=root / "docs/reviews/x.md", ticket=ticket, task_id="T1"),
                [],
            )

    def test_ticket_missing_constraint_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._registry_with_constraints(root)
            ticket = {
                "protocol": "audit",
                "task_id": "T1",
                "binding": [{"constraint": "must write 12-column report", "how": "ok"}],
            }
            errs = ProtocolResolver(root).validate_ticket(target=root / "docs/reviews/x.md", ticket=ticket, task_id="T1")
            self.assertTrue(any("must run 5-pass lens" in e for e in errs))

    def test_ticket_protocol_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._registry_with_constraints(root)
            ticket = {"protocol": "verify", "task_id": "T1", "binding": []}
            errs = ProtocolResolver(root).validate_ticket(target=root / "docs/reviews/x.md", ticket=ticket, task_id="T1")
            self.assertTrue(any("protocol" in e for e in errs))

    def test_ticket_not_required_when_no_protocol(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._registry_with_constraints(root)
            # src path maps to no protocol => ticket not required => valid (empty errors)
            self.assertEqual(
                ProtocolResolver(root).validate_ticket(target=root / "src/x.py", ticket={"protocol": "audit"}),
                [],
            )


class TestProtocolSpecificityTie(unittest.TestCase):
    def _ws(self, root, files, toml):
        _ws(root, files)
        _ws(root, {".agent/protocols.toml": toml})

    def test_same_specificity_overlap_flags(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._ws(
                root,
                {
                    "docs/protocols/a.md": "# a\n",
                    "docs/protocols/b.md": "# b\n",
                    "src/modules/user/handler.py": "# overlap\n",
                },
                '[protocols]\n'
                'a = "docs/protocols/a.md"\n'
                'b = "docs/protocols/b.md"\n'
                '[settings]\n'
                'default = "a"\n'
                '[paths]\n'
                '"src/modules/*/handler.py" = "a"\n'
                '"src/*/user/handler.py" = "b"\n',
            )
            errs = validate_protocols_config(root)
            self.assertTrue(any(c == "PROTOCOL_REGISTRY_INVALID" for c, _ in errs))

    def test_specificity_gradient_no_tie(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._ws(
                root,
                {
                    "docs/protocols/a.md": "# a\n",
                    "docs/protocols/b.md": "# b\n",
                    "src/modules/user/handler.py": "# overlap\n",
                },
                '[protocols]\n'
                'a = "docs/protocols/a.md"\n'
                'b = "docs/protocols/b.md"\n'
                '[settings]\n'
                'default = "a"\n'
                '[paths]\n'
                '"src/modules/**" = "a"\n'
                '"src/modules/user/handler.py" = "b"\n',
            )
            errs = validate_protocols_config(root)
            self.assertFalse(any(c == "PROTOCOL_REGISTRY_INVALID" for c, _ in errs))


class TestProtocolSoftGate(unittest.TestCase):
    def _registry_with_constraints(self, root: Path) -> None:
        _ws(
            root,
            {
                ".agent/protocols.toml": (
                    '[protocols]\n'
                    'audit = "docs/protocols/audit_default.md"\n'
                    '[settings]\n'
                    'default = "audit"\n'
                    '[paths]\n'
                    '"docs/reviews/**" = "audit"\n'
                ),
                "docs/protocols/audit_default.md": (
                    "# audit\n\n## Constraints\n- must write 12-column report\n- must run 5-pass lens\n"
                ),
            },
        )

    def test_verify_pass_when_no_protocol(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._registry_with_constraints(root)
            v = ProtocolResolver(root).verify(target=root / "src/x.py")
            self.assertEqual(v["verdict"], "pass")

    def test_verify_advise_when_ticket_missing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._registry_with_constraints(root)
            v = ProtocolResolver(root).verify(target=root / "docs/reviews/x.md", task_id="T1")
            self.assertEqual(v["verdict"], "advise")
            self.assertIn("remediation", v)

    def test_verify_pass_when_ticket_valid(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._registry_with_constraints(root)
            ticket = {
                "protocol": "audit",
                "task_id": "T1",
                "binding": [
                    {"constraint": "must write 12-column report", "how": "x"},
                    {"constraint": "must run 5-pass lens", "how": "y"},
                ],
            }
            v = ProtocolResolver(root).verify(target=root / "docs/reviews/x.md", ticket=ticket, task_id="T1")
            self.assertEqual(v["verdict"], "pass")

    def test_write_incident_creates_human_visible_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = write_incident(root, "docs/reviews/x.md", "audit", "T1", "agent ignored the gate")
            self.assertTrue(p.is_file())
            self.assertIn("agent ignored the gate", p.read_text(encoding="utf-8"))
            self.assertEqual(p.parent.name, "incidents")


if __name__ == "__main__":
    unittest.main()
