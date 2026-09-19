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
    """下游可配路径：用 .agent/gates.toml 把审计线两步清空（本仓缺省引用 k3dit 角色）。"""
    _write(root, ".agent/gates.toml",
           "[checks.audit]\nstages_produce = []\nstages_verify = []\n")


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

        缺省 `[checks.audit]` 要 `audit.actions.audit|verify`；这里只给了 audit 一条腿。
        """
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(
                root,
                ".agent/pipeline.toml",
                '[roles.audit]\nbind = "k3dit"\n'
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
            # bind 指向未登记的 server ⇒ 必须红
            self._mk(root,
                     "[roles.audit]\nbind = \"ghost\"\n"
                     "[peers.dummy.actions.produce]\n"
                     "transports = [ { provider = \"mcp\", tool = \"dummy_submit\" } ]\n",
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
