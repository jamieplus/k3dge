import pathlib
import unittest

from k3dge.engine.pipeline_schema import validate_pipeline_config


def _write(root: pathlib.Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


class TestPipelineSchema(unittest.TestCase):
    def test_absent_file_is_graceful(self):
        root = pathlib.Path("/tmp/does-not-exist-xyz")
        self.assertEqual(validate_pipeline_config(root), [])

    def test_valid_config_passes(self):
        root = pathlib.Path(__file__).resolve().parents[3]
        # This repo's own pipeline.toml must be valid (no false positives).
        errs = validate_pipeline_config(root)
        self.assertEqual(errs, [], f"unexpected pipeline violations: {errs}")

    def test_syntax_error(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, ".agent/pipeline.toml", "peers = { this is = not valid toml")
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_SYNTAX_ERROR" for c, _ in errs))

    def test_unresolved_stage(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(
                root,
                ".agent/pipeline.toml",
                '[peers.k3dit]\n'
                '[peers.k3dit.actions.audit]\n'
                "transports = [ { provider = \"mcp\", tool = \"k3dit_run_audit\" } ]\n"
                "[pipelines.on_pre_seal]\n"
                'stages = [ "k3dit.actions.lint" ]\n',
            )
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_UNRESOLVED_STAGE" for c, _ in errs))

    def test_mcp_missing_tool(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(
                root,
                ".agent/pipeline.toml",
                '[peers.k3dit]\n'
                '[peers.k3dit.actions.audit]\n'
                "transports = [ { provider = \"mcp\" } ]\n",
            )
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_SCHEMA_INVALID" for c, _ in errs))

    def test_protocol_not_found(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(
                root,
                ".agent/pipeline.toml",
                '[peers.k3dit]\n'
                '[peers.k3dit.actions.verify]\n'
                "transports = [ { provider = \"manual\", protocol = \"docs/protocols/does_not_exist.md\" } ]\n",
            )
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_PROTOCOL_NOT_FOUND" for c, _ in errs))


if __name__ == "__main__":
    unittest.main()
