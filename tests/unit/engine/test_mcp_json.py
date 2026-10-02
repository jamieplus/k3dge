
import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import k3dge.engine.mcp_json as mcp_json_mod
from k3dge.engine.mcp_json import (
    _MCP_CONFIG_REL,
    load_mcp_document,
    load_mcp_endpoints,
    mcp_server_names,
)


class TestMcpJson(unittest.TestCase):
    """三张脸的契约面（t-147/148/149）：缺失=`None`（唯一跳过信号）；在而坏/根非对象/
    没表=`set()`+WARN（peer 闸照常比对）；正常表=键集合。

    写文件一律走 `_MCP_CONFIG_REL`（t-148：硬编码文件名，常量一改这里写的就没人读，
    三条断言全 vacuous）。
    """

    def _names_capture(self, ws: Path):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            got = mcp_server_names(ws)
        return got, err.getvalue()

    def test_missing_file(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            self.assertIsNone(load_mcp_document(ws))
            self.assertEqual(load_mcp_endpoints(ws), {})
            names, err = self._names_capture(ws)
            self.assertIsNone(names)                      # 只有"文件不存在"才是 None
            self.assertEqual(err, "")                     # 且不该出声

    def test_broken_json_is_present_not_missing(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            (ws / _MCP_CONFIG_REL).write_text("{not json", encoding="utf-8")
            self.assertTrue((ws / _MCP_CONFIG_REL).is_file())   # 前置：loader 读的就是这个文件
            self.assertIsNone(load_mcp_document(ws))             # 解析失败 ⇒ 文档 None
            self.assertEqual(load_mcp_endpoints(ws), {})
            names, err = self._names_capture(ws)
            self.assertEqual(names, set())                       # 存在而坏 ≠ 缺失 ⇒ 空集
            self.assertIn("WARN", err)                           # 且必须出声（坏配置静默变绿是 ocr-261 的病根）

    def test_empty_file_is_broken(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            (ws / _MCP_CONFIG_REL).write_text("", encoding="utf-8")
            names, err = self._names_capture(ws)
            self.assertEqual(names, set())
            self.assertIn("WARN", err)

    def test_non_object_root_is_present_not_missing(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            for bad in ("[]", '"text"', "123"):
                with self.subTest(root=bad):
                    (ws / _MCP_CONFIG_REL).write_text(bad, encoding="utf-8")
                    names, err = self._names_capture(ws)
                    self.assertEqual(names, set(), f"根非对象被读成缺失（{bad}）⇒ peer 闸静默跳过")
                    self.assertIn("WARN", err)

    def test_absent_servers_key_is_present_with_none(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            (ws / _MCP_CONFIG_REL).write_text(json.dumps({"other": 1}), encoding="utf-8")
            names, err = self._names_capture(ws)
            self.assertEqual(names, set())            # 已配置但一个都没有
            self.assertIn("WARN", err)

    def test_empty_servers_map_is_explicit_none(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            (ws / _MCP_CONFIG_REL).write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
            names, err = self._names_capture(ws)
            self.assertEqual(names, set())            # {} 也是"无 server"，但不是缺文件
            self.assertEqual(err, "")                 # 合法声明零个，不冤枉

    def test_servers_map_passthrough(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            doc = {"mcpServers": {"audit": {"command": "python", "args": ["-m", "peer"]}},
                   "x-top-level": {"keep": True}}
            (ws / _MCP_CONFIG_REL).write_text(json.dumps(doc), encoding="utf-8")
            endpoints = load_mcp_endpoints(ws)
            # 注册表的意义＝端点负载（t-149）：`set(load_mcp_endpoints(ws))` 把值丢了，
            # 返回裸名单/值被清空/键被改名全都测不出。
            self.assertEqual(endpoints, doc["mcpServers"])
            self.assertEqual(mcp_server_names(ws), {"audit"})
            self.assertEqual(load_mcp_document(ws), doc)   # 顶层非 mcpServers 键整体透传


def test_module_reads_through_the_shared_constant() -> None:
    """写侧/读侧同路径（防 t-148 的"文件名孤岛"回潮）：写进常量所指的路，loader 才读得到。"""
    with TemporaryDirectory() as d:
        ws = Path(d)
        p = ws / _MCP_CONFIG_REL
        p.write_text(json.dumps({"mcpServers": {"a": {}}}), encoding="utf-8")
        assert mcp_server_names(ws) == {"a"}
        assert mcp_json_mod._MCP_CONFIG_REL == ".mcp.json"
