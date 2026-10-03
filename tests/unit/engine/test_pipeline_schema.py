import pathlib
import unittest

from k3dge.engine.pipeline_schema import validate_pipeline_config


class TestProviderSingleSource(unittest.TestCase):
    """守卫：合法 provider 集只能有一处定义，执行层 import 校验层那份（同一对象）。

    曾发生：`pipeline_runner` 与 `pipeline_schema` 各写一份相同的 frozenset，
    加新 provider 时容易只改一处。

    收进 TestCase（t-221）：pytest 裸函数＋`assert` 的两种死法——`python -m unittest`
    / 直跑根本不收集它；`python -O` 下 assert 被剥成空语句——"单源"回归可以全绿通过。
    """

    def test_valid_providers_has_single_source(self) -> None:
        from k3dge.engine import pipeline_runner, pipeline_schema

        self.assertIs(pipeline_runner._VALID_PROVIDERS, pipeline_schema._VALID_PROVIDERS)


def _write(root: pathlib.Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")



def _mk_cfg(root, toml, mcp_json=None):
    """写 pipeline.toml（＋可选 .mcp.json）的共享夹具。

    原来是 `TestPipelineSchema._mk`：别的类里 `_mk(...)` 一被真收集就 AttributeError，
    而它过去恰好被同名类的遮蔽掩盖着（t-219）。提到模块级后所有类共用一份。
    """
    _write(root, ".agent/pipeline.toml", toml)
    if mcp_json is not None:
        _write(root, ".mcp.json", mcp_json)
    return pathlib.Path(root)

def _neutralize_key(body: str, key: str) -> str:
    """把 `key = <值>` 的值原地换成 `[]`（ocr2-503）。

    只动这两个 stage 键，别把整个 `[checks.audit]` 段（或它的其它键）一起删掉——
    旧夹具抄行扫描，容忍不了 `[ checks.audit ]`/行尾注释/内联表，且会把表内其它
    声明一并抹掉，让调用方对着"没人写过的配置"断言绿。这里 brace/引号感知地吃掉
    多行数组，保留一切别的内容。
    """
    import re as _re

    pat = _re.compile(r"(?<![\w])" + _re.escape(key) + r"[ \t]*=")
    idx = 0
    while True:
        m = pat.search(body, idx)
        if not m:
            return body
        i = m.end()
        depth = 0
        j = i
        in_str = None
        while j < len(body):
            ch = body[j]
            if in_str:
                if ch == "\\":
                    j += 2
                    continue
                if ch == in_str:
                    in_str = None
            elif ch in "\"'":
                in_str = ch
            elif ch in "[{":
                depth += 1
            elif ch in "]}":
                if depth == 0:
                    break
                depth -= 1
            elif ch == "\n" and depth == 0:
                break
            elif ch == "," and depth == 0:
                break
            j += 1
        body = body[:m.end()] + " []" + body[j:]
        idx = m.end() + 3


def _no_audit_stages(root: pathlib.Path) -> None:
    """下游可配路径：在**同一声明面**（pipeline.toml）把审计线两步清空。

    幂等（t-222）：重复调用不产生重复 `[checks.audit]` 表。清空只针对
    `stages_produce`/`stages_verify` 两个键（ocr2-503）：容忍 `[ checks.audit ]`
    / 行尾注释 / 内联表等合法写法，且保留表内其它声明（否则调用方在验一份
    没人写过的配置）。
    """
    cfg = root / ".agent" / "pipeline.toml"
    body = cfg.read_text(encoding="utf-8") if cfg.is_file() else ""
    for key in ("stages_produce", "stages_verify"):
        body = _neutralize_key(body, key)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(body, encoding="utf-8")


class TestNoAuditStagesHelper(unittest.TestCase):
    """夹具自身的契约（t-222）：重复调用不产生重复 `[checks.audit]` 表。"""

    def test_double_apply_is_idempotent(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, ".agent/pipeline.toml",
                   '[roles.audit]\nbind = "k3dit"\n'
                   '[checks.audit]\nstages_produce = []\nstages_verify = []\n'
                   '[peers.k3dit.actions.audit]\ntransports = [ { provider = "skip" } ]\n'
                   '[peers.k3dit.actions.verify]\ntransports = [ { provider = "skip" } ]\n')
            _no_audit_stages(root)
            _no_audit_stages(root)
            body = (root / ".agent" / "pipeline.toml").read_text(encoding="utf-8")
            self.assertEqual(body.count("[checks.audit]"), 1, body)
            # ocr2-504：不能只断"表头一次 + 校验绿"——破坏性夹具把 peers 删光也满足。
            # 钉住必须**存活**的声明与必须被清空的 stage。
            self.assertIn("[roles.audit]", body)
            self.assertIn("[peers.k3dit.actions.audit]", body)
            self.assertIn("[peers.k3dit.actions.verify]", body)
            self.assertNotIn('stages_produce = ["', body)
            self.assertEqual(validate_pipeline_config(root), [], body)
            # 幂等且确实清空了（不是"表在而键没动"）
            try:
                import tomllib as _toml
            except ImportError:  # pragma: no cover - py3.10
                import tomli as _toml  # type: ignore
            data = _toml.loads(body)
            self.assertEqual(data["checks"]["audit"]["stages_produce"], [])
            self.assertEqual(data["checks"]["audit"]["stages_verify"], [])

    def test_no_audit_stages_tolerates_equivalent_spellings(self) -> None:
        """ocr2-503：`[ checks.audit ]` / 行尾注释 / 内联表都要认，且只清两个键。"""
        import tempfile

        bodies = [
            '[checks.audit]   # note\nstages_produce = ["a"]\nstages_verify = ["b"]\n'
            '[nodes.audit]\nkind = "fact"\n',
            '[ checks.audit ]\nstages_produce = [\n  "a",\n  "b",\n]\nstages_verify = []\n',
        ]
        for body in bodies:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as d:
                root = pathlib.Path(d)
                _write(root, ".agent/pipeline.toml", body)
                _no_audit_stages(root)
                out = (root / ".agent" / "pipeline.toml").read_text(encoding="utf-8")
                self.assertNotIn('"a"', out)
                self.assertNotIn('"b"', out)
                if "[nodes.audit]" in body:
                    self.assertIn("[nodes.audit]", out, "表内其它声明被夹具误删")
                self.assertNotIn("PIPELINE_SYNTAX_ERROR",
                                 [c for c, _ in validate_pipeline_config(root)])


class TestPipelineSchema(unittest.TestCase):
    def test_absent_file_is_graceful(self):
        import tempfile

        # ocr2-762: 旧夹具测的是"路径根本不存在"——从没走到"仓在而
        # pipeline.toml 缺席"分支（下游最小仓恰恰是这个形状）。
        # 且 /tmp 全局路径若被他处建出会误红。用新鲜临时仓。
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / ".agent").mkdir()
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

    def test_mcp_transport_must_be_wired_in_mcp_json(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _mk_cfg(root,
                     "[peers.other.actions.score]\n"
                     "transports = [ { provider = \"mcp\", tool = \"other_score\" } ]\n",
                     '{"mcpServers": {"k3dit": {"command": "python"}}}')
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_PEER_UNWIRED" and "other" in m for c, m in errs), errs)

    def test_mcp_transport_may_not_leak_endpoint_facts(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _mk_cfg(root,
                     "[peers.k3dit.actions.audit]\n"
                     "transports = [ { provider = \"mcp\", tool = \"t\", command = \"python\" } ]\n",
                     '{"mcpServers": {"k3dit": {"command": "python"}}}')
            errs = validate_pipeline_config(root)
            self.assertTrue(any(c == "PIPELINE_SCHEMA_INVALID" and "leaks endpoint facts" in m
                                for c, m in errs), errs)

    def test_role_bind_resolves_to_wired_server(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            # 角色 audit 绑定到 dummy 服务；只验"bind 到已注册 server ⇒ 无错"（`[pipelines.*]` 已废）
            _mk_cfg(root,
                     "[roles.audit]\nbind = \"dummy\"\n"
                     "[peers.dummy.actions.produce]\n"
                     "transports = [ { provider = \"mcp\", tool = \"dummy_submit\" } ]\n",
                     '{"mcpServers": {"dummy": {"command": "python"}}}')
            _no_audit_stages(root)   # 本例只测角色绑定，不涉审计线两步
            self.assertEqual(validate_pipeline_config(root), [])
            # bind 指向**声明了 mcp 跳**但未登记的 peer ⇒ 必须红
            #（规则 2026-09-26 收紧：只有声明 mcp 跳的 peer 才要求在册——纯 cli 的 peer 不必）
            _mk_cfg(root,
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
            # 被遮蔽期间这条从没跑过：写成 `_write(root, 路径, toml, mcp)`（4 个实参）——
            # 意图是 `_mk_cfg(root, toml, mcp)`，现在才真跑得起来
            _mk_cfg(root,
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
            _mk_cfg(root,
                     "[roles.audit]\nbind = \"k3dit\"\nmode = \"bundle\"\n\n"
                     "[peers.k3dit]\nenabled = false\n\n"
                     "[peers.k3dit.actions.verify]\n"
                     "transports = [ { provider = \"mcp\", tool = \"k3dit_check_report\" } ]\n",
                     '{"mcpServers": {"k3dge": {"command": "python"}}}')
            self.assertTrue([e for e in validate_pipeline_config(root)
                             if e[0] == "PIPELINE_PEER_UNWIRED"])


class TestTransportShapeRobustness(unittest.TestCase):
    """畸形 TOML 值不能让校验器崩，也不能顺带放过 peer 级校验（ocr-284/286/287）。"""

    def _errs(self, body: str):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            # ocr2-764: 复用模块级 _mk_cfg（_write 已做 mkdir），不另立 writer。
            return validate_pipeline_config(_mk_cfg(pathlib.Path(d), body))

    def test_malformed_actions_still_checks_peer_transports(self):
        errs = self._errs('[peers.k3dit]\nactions = 7\n'
                          'transports = [ { provider = "mcp" } ]\n')
        codes = [c for c, _ in errs]
        self.assertIn("PIPELINE_SCHEMA_INVALID", codes)
        self.assertTrue(any("tool" in m for _, m in errs), errs)

    def test_unhashable_provider_does_not_crash(self):
        """不崩 **且必须报**（t-223）：`assertIsInstance(errs, list)` 恒真——校验器把
        不可哈希的 provider 吞成"无违例"也照样绿。崩溃由异常本身证；这里钉的另一半是
        "形状怪的值要进违例清单，不是静默通过"。"""
        errs = self._errs('[peers.k3dit.actions.a]\n'
                          'transports = [ { provider = ["mcp"], tool = "x" } ]\n')
        codes = [c for c, _ in errs]
        self.assertIn("PIPELINE_SCHEMA_INVALID", codes, errs)

    def test_manual_protocol_must_be_string(self):
        errs = self._errs('[peers.k3dit.actions.v]\n'
                          'transports = [ { provider = "manual", protocol = { path = "x.md" } } ]\n')
        # ocr2-763: 只比自由文本时改措辞就误红、无关违例含同串就误绿——钉死规则码。
        self.assertTrue(any(c == "PIPELINE_SCHEMA_INVALID" and "must be a string" in m
                            for c, m in errs), errs)

    def test_manual_protocol_stays_inside_workspace(self):
        errs = self._errs('[peers.k3dit.actions.v]\n'
                          'transports = [ { provider = "manual", protocol = "../secret.md" } ]\n')
        self.assertTrue(any(c == "PIPELINE_SCHEMA_INVALID" and "workspace" in m
                            for c, m in errs), errs)


if __name__ == "__main__":
    unittest.main()
