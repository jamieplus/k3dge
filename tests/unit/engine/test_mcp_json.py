from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from k3dge.engine.mcp_json import load_mcp_document, load_mcp_endpoints, mcp_server_names


class TestMcpJson(unittest.TestCase):
    def test_missing_file(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            self.assertIsNone(load_mcp_document(ws))
            self.assertEqual(load_mcp_endpoints(ws), {})
            self.assertIsNone(mcp_server_names(ws))

    def test_broken_json(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            (ws / ".mcp.json").write_text("{not json", encoding="utf-8")
            self.assertIsNone(load_mcp_document(ws))
            self.assertEqual(load_mcp_endpoints(ws), {})
            self.assertIsNone(mcp_server_names(ws))

    def test_servers_map(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            (ws / ".mcp.json").write_text(
                json.dumps({"mcpServers": {"audit": {"command": "python"}}}),
                encoding="utf-8",
            )
            self.assertEqual(set(load_mcp_endpoints(ws)), {"audit"})
            self.assertEqual(mcp_server_names(ws), {"audit"})
