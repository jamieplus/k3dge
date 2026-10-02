"""硬闸契约加载器：声明面唯一（`.agent/pipeline.toml`）+ 缺省完整 + 坏配置回落。

ADR-0026 §2.7：代码内缺省必须完整（下游删掉整段也能跑）；解析失败回落缺省
（**闸不因配置坏而失效**）；未知 id 由执行器拒绝（"不让声明空转"）。
"""
import tempfile
from pathlib import Path

from k3dge.engine import gates
import shutil
import atexit


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
    """坏 TOML ⇒ 回落缺省**且必须出声**（t-124）。

    模块 docstring 与 `gates.load` 都写着"回落缺省但**必须出声**"——静默放宽
    阈值/前置闸＝假绿；此前全树没有任何测试碰过那条 WARN，删掉它这里照样绿。
    异常类名也要可见：编码/权限坏了不得伪装成"坏 TOML"（排查面靠它分流）。
    """
    import contextlib
    import io

    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, "this is not toml = = =\n")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            data = gates.load(ws)
        assert data == gates.DEFAULTS                      # 内容＝缺省
        assert gates.get(ws, "audit_trigger", "c2_nesting_max") == 5
        assert gates.preconditions(ws, "seal")             # 缺省编排仍在
        text = err.getvalue()
        assert "[gates] WARN" in text and "按缺省跑" in text, text
        assert "TOMLDecodeError" in text, text             # 坏因是 TOML，不是别的 bug

    # 对照：**缺文件**才是合法的静默（下游最小仓不必配）；出声义务只属于"有而读不出"
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d)                                        # 无 pipeline.toml
        err2 = io.StringIO()
        with contextlib.redirect_stderr(err2):
            gates.load(ws)
        assert err2.getvalue() == "", err2.getvalue()


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
        # 逐键覆盖＝**没写的键保留缺省原值**（t-126）：裸真值只能证"非空"，
        # 若实现把 actions 也清成 [] 之外的占位甚至只剩一个 id 都看不出来——对账缺省全表。
        assert gates.actions(ws, "seal") == list(gates.DEFAULTS["checks"]["seal"]["actions"]), \
            gates.actions(ws, "seal")
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
    # 前提（t-125）：`gates.load` 对**任何**读不到声明件的目录都回 DEFAULTS——根一漂，
    # declared 就变成缺省自己的复印件，"declared == fresh" 恒真，本测什么都不比就绿。
    assert (repo / ".agent" / "pipeline.toml").is_file(), f"仓根解析错误：{repo}"
    declared = {k: v for k, v in gates.load(repo).items() if k != "nodes"}
    fresh_ws = Path(tempfile.mkdtemp())
    atexit.register(shutil.rmtree, fresh_ws, True)
    fresh = {k: v for k, v in gates.load(fresh_ws).items() if k != "nodes"}
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


class TestUnknownKeyFailsLoud:
    """未知键不得静默返回 0（会翻转闸语义，ocr2-258）。"""

    def test_unknown_key_raises(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d)
            import pytest

            with pytest.raises(KeyError):
                gates.get(ws, "audit_trigger", "typo_key")
