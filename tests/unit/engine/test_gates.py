"""硬闸契约加载器：声明面唯一（`.agent/pipeline.toml`）+ 缺省完整 + 坏配置回落。

ADR-0026 §2.7：代码内缺省必须完整（下游删掉整段也能跑）；解析失败回落缺省
（**闸不因配置坏而失效**）；未知 id 由执行器拒绝（"不让声明空转"）。
"""
import tempfile
from pathlib import Path

from k3dge.engine import gates


def _ws(d, body=None):
    p = Path(d) / ".agent"
    p.mkdir(parents=True)
    if body is not None:
        (p / "pipeline.toml").write_text(body, encoding="utf-8")
    return Path(d)


def test_defaults_when_absent():
    """无声明文件 ⇒ 代码内缺省完整可用（下游最小仓不必配）。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d)
        assert gates.get(ws, "audit_trigger", "c2_nesting_max") == 5
        assert gates.get(ws, "audit_trigger", "volume_max") == 8


def test_override_keeps_other_defaults():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, "[gates.audit_trigger]\nc2_nesting_max = 3\n")
        assert gates.get(ws, "audit_trigger", "c2_nesting_max") == 3
        assert gates.get(ws, "audit_trigger", "volume_max") == 8   # 同段其它键不被清掉


def test_malformed_falls_back_to_defaults():
    """坏 TOML ⇒ 回落缺省，不抛（闸不因配置坏而失效）。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, "this is not toml = = =\n")
        assert gates.get(ws, "audit_trigger", "c2_nesting_max") == 5
        assert gates.preconditions(ws, "seal")            # 缺省编排仍在


def test_pipeline_toml_with_peers_only_keeps_check_defaults():
    """下游只配了 peer、没碰 [checks.*] ⇒ 编排走缺省（两段互不干扰）。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, '[roles.audit]\nbind = "k3dit"\n[peers.k3dit.actions.audit]\n'
                    'transports = [ { provider = "skip" } ]\n')
        assert gates.preconditions(ws, "seal")[0] == "tasks_all_done"
        # 缺省＝**无外部审计步**（审计是本地工具调用，2026-09-26 起）：仍有对等 harness 的仓显式声明
        assert gates.stages(ws, "audit", "produce") == []
        assert gates.stages(ws, "audit", "verify") == []


def test_seal_preconditions_default_and_override():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d)
        # `docs_normalized` 是耐久闸（ADR-0022 §2.2 🅰1.4）：规约化须在封板前做完
        # 预审＝进审计的门槛（ADR-0004 §2.1.9 相位 1）：报告存在性/新鲜度已移出
        # （报告降为可选产物、边界改由 `tag <M>=<B>` 表达）
        assert gates.preconditions(ws, "seal") == [
            "tasks_all_done", "align_pass", "guides_filled",
            "adrs_all_accepted", "adr_landed", "adr_amend_format", "docs_normalized",
        ]
        # 三相位＝声明序：预审(full_matrix) → 审计(audit) → 审核后(archive/version_bump/seal_record/…)
        assert gates.actions(ws, "seal") == [
            "full_matrix", "audit", "archive", "version_bump", "closure_note",
            "seal_record", "prune",
        ]
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, "[checks.seal]\npreconditions = []\n")
        assert gates.preconditions(ws, "seal") == []
        assert gates.actions(ws, "seal")                   # 逐键覆盖：没写的键保留缺省
        assert gates.get(ws, "audit_trigger", "c2_nesting_max") == 5


def test_markers_and_output_defaults_and_override():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d)
        assert gates.get(ws, "markers", "max_note") == 80
        assert gates.get(ws, "markers", "max_note_pending") == 500
        assert gates.get(ws, "output", "default_lines") == 10
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, "[gates.markers]\nmax_note = 200\n")
        assert gates.get(ws, "markers", "max_note") == 200
        assert gates.get(ws, "markers", "max_note_pending") == 500


def test_repo_declares_the_same_values_as_defaults():
    """自举：本仓声明段的值 == 代码缺省（声明是显式化，不是偷偷改语义）。

    前科：本仓曾有 `.agent/gates.toml`，是 DEFAULTS 的冗余副本且已漂移（覆盖列表漏了
    reconcile ⇒ 功能静默死亡，见 2026-09-17-M10-refactor-adr_archive_to_sync）。
    """
    repo = Path(__file__).resolve().parents[3]
    declared = {k: v for k, v in gates.load(repo).items() if k != "nodes"}
    fresh = {k: v for k, v in gates.load(Path(tempfile.mkdtemp())).items() if k != "nodes"}
    # `[nodes.*]` 覆盖的是 nodes.NODE_DEFAULTS（另一张表）⇒ 由 test_nodes 的自举断言管，不在此比
    assert declared == fresh, {
        k: (declared.get(k), fresh.get(k)) for k in set(declared) | set(fresh)
        if declared.get(k) != fresh.get(k)
    }


def test_legacy_gates_toml_is_detected():
    """已废的第二个配置文件：检测到（由 pipeline_schema 红一次逼迁移，不静默忽略）。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d)
        assert gates.legacy_config_present(ws) is False
        (ws / ".agent" / "gates.toml").write_text("[checks.seal]\npreconditions = []\n", encoding="utf-8")
        assert gates.legacy_config_present(ws) is True
        # 且它**不再生效**（声明面只有一处）
        assert gates.preconditions(ws, "seal")[0] == "tasks_all_done"
