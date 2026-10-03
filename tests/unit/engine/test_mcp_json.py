
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
            self.assertIsNone(load_mcp_document(ws))   # 空文件 ⇒ 文档 None（与坏 JSON 同脸）
            self.assertEqual(load_mcp_endpoints(ws), {})
            names, err = self._names_capture(ws)
            self.assertEqual(names, set())
            self.assertIn("WARN", err)

    def test_non_object_root_is_present_not_missing(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            for bad in ("[]", '"text"', "123"):
                with self.subTest(root=bad):
                    (ws / _MCP_CONFIG_REL).write_text(bad, encoding="utf-8")
                    self.assertIsNone(load_mcp_document(ws), f"根非对象应 None：{bad}")
                    self.assertEqual(load_mcp_endpoints(ws), {}, f"根非对象端点应 {{}}：{bad}")
                    names, err = self._names_capture(ws)
                    self.assertEqual(names, set(), f"根非对象被读成缺失（{bad}）⇒ peer 闸静默跳过")
                    self.assertIn("WARN", err)

    # ocr2-750：旧名 "present_with_none" 与断言/契约矛盾——None 在本文件只表示"文件缺失"，
    # 此例（有文件、无 mcpServers 键）返回空集 + WARN。改名，免得后人"恢复" None 行为。
    def test_absent_servers_key_is_present_with_empty_set(self) -> None:
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


    def test_module_reads_through_the_shared_constant(self) -> None:
        """写侧/读侧同路径（防 t-148 的"文件名孤岛"回潮）：写进常量所指的路，loader 才读得到。"""
        with TemporaryDirectory() as d:
            ws = Path(d)
            p = ws / _MCP_CONFIG_REL
            p.write_text(json.dumps({"mcpServers": {"a": {}}}), encoding="utf-8")
            self.assertEqual(mcp_server_names(ws), {"a"})
            self.assertEqual(mcp_json_mod._MCP_CONFIG_REL, ".mcp.json")

    def test_writer_constants_agree_with_reader(self) -> None:
        """单源钉：写侧硬编码不得与读侧常量漂移（t-148 文件名孤岛的真病灶）。"""
        from k3dge.engine import pipeline_runner as pr_mod
        self.assertEqual(pr_mod._MCP_CONFIG_REL, _MCP_CONFIG_REL)
        # mcp_peers 写侧用字面量 ".mcp.json"：钉住它仍等于读侧常量
        import pathlib as _pl
        peers_src = (_pl.Path(__file__).resolve().parents[3]
                     / "src" / "k3dge" / "cli" / "mcp_peers.py").read_text(encoding="utf-8")
        self.assertIn('".mcp.json"', peers_src)
        self.assertEqual(_MCP_CONFIG_REL, ".mcp.json")

    def test_end_to_end_writer_then_loader(self) -> None:
        """端到端：经写侧常量路径写入后，读侧 loader 必须读回同一 server。"""
        with TemporaryDirectory() as d:
            ws = Path(d)
            (ws / _MCP_CONFIG_REL).write_text(
                json.dumps({"mcpServers": {"e2e": {"command": "x"}}}), encoding="utf-8")
            self.assertEqual(mcp_server_names(ws), {"e2e"})
            self.assertIn("e2e", load_mcp_endpoints(ws))


class TestStatFailureIsNotAbsence(unittest.TestCase):
    """`stat` 失败不是"文件缺失"（ocr2-268）。"""

    def test_directory_entry_is_present_not_missing(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            (ws / _MCP_CONFIG_REL).mkdir()
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                names = mcp_server_names(ws)
            self.assertEqual(names, set())            # 存在但不是普通文件 ⇒ 空集+WARN，不是 None
            self.assertIn("WARN", err.getvalue())


class TestProbePeerWhitespace(unittest.TestCase):
    """探测用净化后的 id，而不是原始 `pid`（ocr2-269）。"""

    def test_whitespace_pid_probes_with_sanitized_name(self) -> None:
        from k3dge.engine.mcp_json import probe_peer_mcp

        with TemporaryDirectory() as d:
            parent = Path(d)
            ws = parent / "main"
            ws.mkdir()
            peer = parent / "foo"
            (peer / "src" / "foo").mkdir(parents=True)
            (peer / "src" / "foo" / "mcp.py").write_text("", encoding="utf-8")
            probe, mod, py_path = probe_peer_mcp(ws, " foo ")
            self.assertIsNotNone(probe)
            self.assertEqual(mod, "foo.mcp")
            self.assertIsNotNone(py_path)
