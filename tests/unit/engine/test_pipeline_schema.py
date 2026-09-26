import pathlib
import unittest

from k3dge.engine.pipeline_schema import validate_pipeline_config


def test_valid_providers_has_single_source():
    """守卫：合法 provider 集只能有一处定义，执行层 import 校验层那份（同一对象）。

    曾发生：`pipeline_runner` 与 `pipeline_schema` 各写一份相同的 frozenset，
    加新 provider 时容易只改一处。
    """
    from k3dge.engine import pipeline_runner, pipeline_schema

    assert pipeline_runner._VALID_PROVIDERS is pipeline_schema._VALID_PROVIDERS


def _write(root: pathlib.Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _no_audit_stages(root: pathlib.Path) -> None:
    """下游可配路径：在**同一声明面**（pipeline.toml）把审计线两步清空。"""
    cfg = root / ".agent" / "pipeline.toml"
    body = cfg.read_text(encoding="utf-8") if cfg.is_file() else ""
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(body + "\n[checks.audit]\nstages_produce = []\nstages_verify = []\n",
                   encoding="utf-8")


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

    def test_retired_pipelines_section_is_flagged(self):
        """`[pipelines.*]` 已废（只有校验、没有执行者）⇒ 下游还留着必须显式红一次逼迁移。"""
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, ".agent/pipeline.toml",
                   '[roles.audit]\nbind = "k3dit"\n'
                   '[peers.k3dit.actions.audit]\n'
                   "transports = [ { provider = \"manual\", protocol = \"p.md\" } ]\n"
                   '[peers.k3dit.actions.verify]\n'
                   "transports = [ { provider = \"manual\", protocol = \"p.md\" } ]\n"
                   "[pipelines.on_pre_seal]\n"
                   'stages = [ "k3dit.actions.verify" ]\n')
            _write(root, "p.md", "# protocol\n")
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_SCHEMA_INVALID" and "retired" in m
                                for c, m in errs), errs)

    def test_unresolved_stage(self):
        """声明的外部步解析不到 transports ⇒ 红（不让声明空转）。

        缺省 `[checks.audit]` 现在是空的（审计＝本地工具调用）⇒ 本用例**显式**声明两条外部步，
        再只给 audit 一条腿，验证"声明了就必须能解析"。
        """
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(
                root,
                ".agent/pipeline.toml",
                '[roles.audit]\nbind = "k3dit"\n'
                '[checks.audit]\nstages_produce = ["audit.actions.audit"]\n'
                'stages_verify = ["audit.actions.verify"]\n'
                '[peers.k3dit.actions.audit]\n'
                "transports = [ { provider = \"skip\" } ]\n",
            )
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_UNRESOLVED_STAGE" and "verify" in m
                                for c, m in errs), errs)

    def test_declared_stages_resolve_via_role_binding(self):
        """角色名 ref 经 `[roles.audit] bind` 解析到 peer ⇒ 绿（下游换实现不用改声明）。"""
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, ".agent/pipeline.toml",
                   '[roles.audit]\nbind = "myauditor"\n'
                   '[peers.myauditor.actions.audit]\n'
                   "transports = [ { provider = \"skip\" } ]\n"
                   '[peers.myauditor.actions.verify]\n'
                   "transports = [ { provider = \"skip\" } ]\n")
            self.assertEqual(validate_pipeline_config(root), [])

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

    def test_legacy_harnesses_hooks_rejected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(
                root,
                ".agent/pipeline.toml",
                "[harnesses.k3dit]\n"
                'mcp_tool = "k3dit_run_audit"\n'
                "[hooks]\n"
                "on_align_success = []\n",
            )
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_SCHEMA_INVALID" for c, _ in errs))
            msg = " ".join(m for _, m in errs)
            self.assertIn("harnesses", msg)
            self.assertIn("hooks", msg)

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


    def test_transport_args_must_be_a_table(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(
                root,
                ".agent/pipeline.toml",
                "[peers.k3dit]\n"
                "[peers.k3dit.actions.audit]\n"
                "transports = [ { provider = \"mcp\", tool = \"k3dit_run_audit_flow\", args = \"nope\", timeout = 5 } ]\n",
            )
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_SCHEMA_INVALID" and "['args'] must be a table" in m
                                for c, m in errs), errs)

    def test_transport_args_table_is_accepted(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(
                root,
                ".agent/pipeline.toml",
                "[peers.k3dit]\n"
                "[peers.k3dit.actions.audit]\n"
                "transports = [ { provider = \"mcp\", tool = \"k3dit_run_audit_flow\", "
                "args = { target_scope = \"code\" }, timeout = 5 } ]\n",
            )
            _write(root, ".mcp.json", '{"mcpServers": {"k3dit": {"command": "python", "args": ["-m", "k3dit.mcp"]}}}')
            _no_audit_stages(root)   # 本例只测 transport 的 args 表，不涉审计线两步
            self.assertEqual(validate_pipeline_config(root), [])

    def _mk(self, root, toml, mcp_json=None):
        _write(root, ".agent/pipeline.toml", toml)
        if mcp_json is not None:
            _write(root, ".mcp.json", mcp_json)

    def test_mcp_transport_must_be_wired_in_mcp_json(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            self._mk(root,
                     "[peers.other.actions.score]\n"
                     "transports = [ { provider = \"mcp\", tool = \"other_score\" } ]\n",
                     '{"mcpServers": {"k3dit": {"command": "python"}}}')
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_PEER_UNWIRED" and "other" in m for c, m in errs), errs)

    def test_mcp_transport_may_not_leak_endpoint_facts(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            self._mk(root,
                     "[peers.k3dit.actions.audit]\n"
                     "transports = [ { provider = \"mcp\", tool = \"t\", command = \"python\" } ]\n",
                     '{"mcpServers": {"k3dit": {"command": "python"}}}')
            errs = validate_pipeline_config(root)
            self.assertTrue(any("leaks endpoint facts" in m for c, m in errs), errs)

    def test_role_bind_resolves_to_wired_server(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            # 角色 audit 绑定到 dummy 服务；流程引用 audit.produce
            self._mk(root,
                     "[roles.audit]\nbind = \"dummy\"\n"
                     "[peers.dummy.actions.produce]\n"
                     "transports = [ { provider = \"mcp\", tool = \"dummy_submit\" } ]\n",
                     '{"mcpServers": {"dummy": {"command": "python"}}}')
            _no_audit_stages(root)   # 本例只测角色绑定，不涉审计线两步
            self.assertEqual(validate_pipeline_config(root), [])
            # bind 指向**声明了 mcp 跳**但未登记的 peer ⇒ 必须红
            #（规则 2026-09-26 收紧：只有声明 mcp 跳的 peer 才要求在册——纯 cli 的 peer 不必）
            self._mk(root,
                     "[roles.audit]\nbind = \"ghost\"\n"
                     "[peers.ghost.actions.produce]\n"
                     "transports = [ { provider = \"mcp\", tool = \"ghost_submit\" } ]\n",
                     '{"mcpServers": {"dummy": {"command": "python"}}}')
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_PEER_UNWIRED" and "'audit'" in m and "ghost" in m
                                for c, m in errs), errs)



    def test_role_kind_must_be_gate_or_service(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, ".mcp.json", '{"mcpServers": {"k3che": {"command": "python"}}}')
            _write(root, ".agent/pipeline.toml",
                   '[roles.cache]\nbind = "k3che"\nkind = "lucene"\n'
                   "[peers.k3che.actions.search]\n"
                   "transports = [ { provider = \"mcp\", tool = \"k3che_search\" } ]\n")
            errs = validate_pipeline_config(root)
            self.assertTrue(any("kind must be 'gate' or 'service'" in m for c, m in errs), errs)

    def test_role_kind_service_with_skip_chain_is_valid(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, ".mcp.json", '{"mcpServers": {"k3che": {"command": "python"}}}')
            _write(root, ".agent/pipeline.toml",
                   '[roles.cache]\nbind = "k3che"\nkind = "service"\n'
                   "[peers.k3che.actions.search]\n"
                   "transports = [ { provider = \"mcp\", tool = \"k3che_search\" }, { provider = \"skip\" } ]\n")
            _no_audit_stages(root)   # 本例只测 service 角色 + skip 链
            self.assertEqual(validate_pipeline_config(root), [])



if __name__ == "__main__":
    unittest.main()


class TestLegacyConfigGuard(unittest.TestCase):
    """已废的第二个配置文件：存在即红一次逼迁移（不静默忽略）。

    前科：本仓 `.agent/gates.toml` 曾是 DEFAULTS 的冗余副本且漂移——覆盖列表漏了
    reconcile ⇒ 功能静默死亡（2026-09-17-M10-refactor-adr_archive_to_sync）。
    """

    def test_gates_toml_present_is_flagged(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, ".agent/pipeline.toml",
                   '[roles.audit]\nbind = "k3dit"\n'
                   '[peers.k3dit.actions.audit]\ntransports = [ { provider = "skip" } ]\n'
                   '[peers.k3dit.actions.verify]\ntransports = [ { provider = "skip" } ]\n')
            self.assertEqual(validate_pipeline_config(root), [])   # 先证明基线绿
            _write(root, ".agent/gates.toml", "[checks.seal]\npreconditions = []\n")
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_SCHEMA_INVALID" and "gates.toml is retired" in m
                                for c, m in errs), errs)

    def test_repo_has_no_legacy_config(self):
        root = pathlib.Path(__file__).resolve().parents[3]
        self.assertFalse((root / ".agent" / "gates.toml").exists())
        self.assertTrue((root / ".agent" / "pipeline.toml").is_file())


    def test_cli_only_peer_need_not_be_registered_in_mcp_json(self):
        """PIPELINE_PEER_UNWIRED 的真实危害＝"声明了 mcp 跳却没注册 server"。

        反例（2026-09-26 实测）：k3dit 撤掉 MCP 服务端后只留 cli 传输，旧规则仍要求它出现在 `.mcp.json`
        ⇒ 把合法的 cli-only peer 判红。现在规则按"是否声明 mcp 跳"判。
        """
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, ".agent/pipeline.toml",
                   "[roles.audit]\nbind = \"k3dit\"\nmode = \"bundle\"\n\n"
                     "[peers.k3dit]\nenabled = false\n\n"
                     "[peers.k3dit.actions.verify]\n"
                     "transports = [ { provider = \"cli\", command = \"k3dit check-report {path}\" },\n"
                     "               { provider = \"manual\", protocol = \"docs/protocols/verify_default.md\" } ]\n",
                     '{"mcpServers": {"k3dge": {"command": "python"}}}')
            _no_audit_stages(root)
            self.assertFalse([e for e in validate_pipeline_config(root)
                              if e[0] == "PIPELINE_PEER_UNWIRED"])
            # 一旦声明 mcp 跳而没注册 ⇒ 仍要红（规则没被削弱）
            self._mk(root,
                     "[roles.audit]\nbind = \"k3dit\"\nmode = \"bundle\"\n\n"
                     "[peers.k3dit]\nenabled = false\n\n"
                     "[peers.k3dit.actions.verify]\n"
                     "transports = [ { provider = \"mcp\", tool = \"k3dit_check_report\" } ]\n",
                     '{"mcpServers": {"k3dge": {"command": "python"}}}')
            self.assertTrue([e for e in validate_pipeline_config(root)
                             if e[0] == "PIPELINE_PEER_UNWIRED"])


    def test_role_bind_resolves_to_wired_server(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            # 角色 audit 绑定到 dummy 服务；流程引用 audit.produce
            self._mk(root,
                     "[roles.audit]\nbind = \"dummy\"\n"
                     "[peers.dummy.actions.produce]\n"
                     "transports = [ { provider = \"mcp\", tool = \"dummy_submit\" } ]\n",
                     '{"mcpServers": {"dummy": {"command": "python"}}}')
            _no_audit_stages(root)   # 本例只测角色绑定，不涉审计线两步
            self.assertEqual(validate_pipeline_config(root), [])
            # bind 指向**声明了 mcp 跳**但未登记的 peer ⇒ 必须红
            #（规则 2026-09-26 收紧：只有声明 mcp 跳的 peer 才要求在册——纯 cli 的 peer 不必）
            self._mk(root,
                     "[roles.audit]\nbind = \"ghost\"\n"
                     "[peers.ghost.actions.produce]\n"
                     "transports = [ { provider = \"mcp\", tool = \"ghost_submit\" } ]\n",
                     '{"mcpServers": {"dummy": {"command": "python"}}}')
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_PEER_UNWIRED" and "'audit'" in m and "ghost" in m
                                for c, m in errs), errs)



    def test_role_kind_must_be_gate_or_service(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, ".mcp.json", '{"mcpServers": {"k3che": {"command": "python"}}}')
            _write(root, ".agent/pipeline.toml",
                   '[roles.cache]\nbind = "k3che"\nkind = "lucene"\n'
                   "[peers.k3che.actions.search]\n"
                   "transports = [ { provider = \"mcp\", tool = \"k3che_search\" } ]\n")
            errs = validate_pipeline_config(root)
            self.assertTrue(any("kind must be 'gate' or 'service'" in m for c, m in errs), errs)

    def test_role_kind_service_with_skip_chain_is_valid(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, ".mcp.json", '{"mcpServers": {"k3che": {"command": "python"}}}')
            _write(root, ".agent/pipeline.toml",
                   '[roles.cache]\nbind = "k3che"\nkind = "service"\n'
                   "[peers.k3che.actions.search]\n"
                   "transports = [ { provider = \"mcp\", tool = \"k3che_search\" }, { provider = \"skip\" } ]\n")
            _no_audit_stages(root)   # 本例只测 service 角色 + skip 链
            self.assertEqual(validate_pipeline_config(root), [])



if __name__ == "__main__":
    unittest.main()


class TestLegacyConfigGuard(unittest.TestCase):
    """已废的第二个配置文件：存在即红一次逼迁移（不静默忽略）。

    前科：本仓 `.agent/gates.toml` 曾是 DEFAULTS 的冗余副本且漂移——覆盖列表漏了
    reconcile ⇒ 功能静默死亡（2026-09-17-M10-refactor-adr_archive_to_sync）。
    """

    def test_gates_toml_present_is_flagged(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, ".agent/pipeline.toml",
                   '[roles.audit]\nbind = "k3dit"\n'
                   '[peers.k3dit.actions.audit]\ntransports = [ { provider = "skip" } ]\n'
                   '[peers.k3dit.actions.verify]\ntransports = [ { provider = "skip" } ]\n')
            self.assertEqual(validate_pipeline_config(root), [])   # 先证明基线绿
            _write(root, ".agent/gates.toml", "[checks.seal]\npreconditions = []\n")
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_SCHEMA_INVALID" and "gates.toml is retired" in m
                                for c, m in errs), errs)

    def test_repo_has_no_legacy_config(self):
        root = pathlib.Path(__file__).resolve().parents[3]
        self.assertFalse((root / ".agent" / "gates.toml").exists())
        self.assertTrue((root / ".agent" / "pipeline.toml").is_file())
