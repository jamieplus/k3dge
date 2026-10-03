"""next-step sidecar：单判定 `persist`（替换）/ 本轮多处理点 `emit`/`emit_all`（upsert+排序）。

形状：`{"next": [card...], "primary": <state>}`（旧单条形状读侧兼容，见 load_persisted）。
"""
import json
import tempfile
from pathlib import Path

from k3dge.engine.nextstep import (
    NextStep,
    _prio,
    begin_run,
    emit,
    emit_all,
    load_all,
    load_persisted,
    persist,
)


def _ns(state="seal_ready", mid="M10"):
    return NextStep.from_state(state, mid)


def _raw(ws) -> dict:
    return json.loads((ws / ".k3dge" / "next.json").read_text(encoding="utf-8"))


def test_persist_writes_sidecar():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        persist(ws, _ns())
        data = _raw(ws)
        assert data["primary"] == "seal_ready"
        card = data["next"][0]
        assert card["state"] == "seal_ready"
        assert card["milestone"] == "M10"
        # 陈述式事实 + 成对选项（ADR-0026 §2.2）；question 只给有应答通道的消费者
        assert "是否收这一章由你决定" in card["fact"]
        assert not card["fact"].rstrip().endswith(("？", "?"))
        assert len(card["options"]) >= 2
        assert "封板？" in card["question"]
        assert "ask" not in card and "if_y" not in card and "note" not in card


def test_persist_replaces():
    """`persist` 是单判定流程用的**替换**语义（seal_flow / milestone_audit 各只判一个）。"""
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        persist(ws, NextStep.from_state("audit_suggested", "M5"))
        persist(ws, NextStep.from_state("sealed", "M5"))
        data = _raw(ws)
        assert data["primary"] == "sealed"
        assert [c["state"] for c in data["next"]] == ["sealed"]


def test_persist_never_raises_but_says_so(tmp_path):
    """写不进也要**出声**（ocr-273 的可观测面；t-186）。

    旧夹具 `/dev/null/fake` 靠 POSIX 上 `/dev/null` 是字符设备才失败——Windows 上
    它会 mkdir 成功、真写盘，失败路径从没被走还污染开发机。改为可移植的强制失败：
    把侧车父目录位置放一个**普通文件**，`mkdir(parents=True, exist_ok=True)` 必然 OSError。
    """
    import contextlib
    import io

    ws = Path(tmp_path)
    (ws / ".k3dge").write_text("我是一个占位的普通文件\n", encoding="utf-8")
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        persist(ws, _ns())                       # 不得抛
    assert "[nextstep] WARN" in err.getvalue(), err.getvalue()
    assert "侧车写入失败" in err.getvalue()


def test_persist_never_raises_on_unserializable_card(tmp_path):
    """ocr2-755：`_write_cards` 只接 `OSError`——`json.dumps` 的 TypeError（如 reasons 里
    混进 Path/set/datetime）会直接掀翻 persist，正是本文件"永不抛"承诺要防的。
    序列化失败同样出声不断行，且侧车不留半截。"""
    import contextlib
    import io

    ws = Path(tmp_path)
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        persist(ws, NextStep.from_state("seal_ready", "M10", reasons=[Path("x")]))  # 不得抛
    assert "[nextstep] WARN" in err.getvalue(), err.getvalue()
    assert "序列化失败" in err.getvalue(), err.getvalue()
    assert not (ws / ".k3dge" / "next.json").exists()  # 失败路径不得留半截侧车


def test_emit_upserts_and_orders_by_priority():
    """一轮内多处理点：同 state 去重、按 priority 排、primary＝最小 priority。

    平级（两个 priority 4）之间的次序**不属契约**（t-187）——`emit` 的 `_upsert` 与
    `emit_all` 的 tie-break 规则本就不同（前者跟插入序，后者跟 STATE_OPTIONS 序），
    这里再锁状态序就会在"统一 tie 规则"那天红得莫名所以。只锁：档序、首条、平级集合。
    """
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        begin_run(ws)
        emit(ws, _ns("seal_ready"))                 # priority 4
        emit(ws, _ns("audit_suggested"))            # priority 4（原 ratchet_open 的 5 档已退休）
        emit(ws, NextStep.from_state("pending_findings", "M10", pending=2))   # priority 1
        data = _raw(ws)
        assert [c["priority"] for c in data["next"]] == [1, 4, 4]
        assert data["next"][0]["state"] == "pending_findings"
        assert {c["state"] for c in data["next"][1:]} == {"seal_ready", "audit_suggested"}
        assert data["primary"] == "pending_findings"


def test_emit_same_state_dedupes_and_merges_reasons():
    """去重的契约是"**后到的合并 reasons**"（ocr-274），旧测两张无差异的卡把"整条覆盖"
    的回归原样放过（t-188）。给两张**不同 reasons** 的同态卡：只剩一条，理由并集。"""
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        begin_run(ws)
        emit(ws, NextStep.from_state("seal_ready", "M10", reasons=["A 已满足"]))
        emit(ws, NextStep.from_state("seal_ready", "M10", reasons=["B 待办"]))
        data = _raw(ws)
        assert len(data["next"]) == 1, data
        merged = data["next"][0]["reasons"]
        assert "A 已满足" in merged and "B 待办" in merged, merged


def test_legacy_and_malformed_sidecars_are_survivable():
    """防御支路逐个走（t-190）：priority 缺失/null/字符串、非 dict 条目、坏 JSON——
    `load_all`/`_prio`/`load_persisted` 为它们写的分支此前只测过最优情况。"""
    card = {"state": "seal_ready", "milestone": "M10", "fact": "f", "options": ["a", "b"]}
    shapes = {
        "no_priority": {"next": [dict(card)], "primary": "seal_ready"},
        "null_priority": {"next": [dict(card, priority=None)], "primary": "seal_ready"},
        "string_priority": {"next": [dict(card, priority="4")], "primary": "seal_ready"},
        "non_numeric_string": {"next": [dict(card, priority="high")], "primary": "seal_ready"},
        "non_dict_entries": {"next": ["junk", dict(card), 42], "primary": "seal_ready"},
    }
    for name, payload in shapes.items():
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            p = ws / ".k3dge" / "next.json"
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            cards = load_all(ws)                       # 不抛；坏条目由 load_all 滤掉
            if name == "non_dict_entries":
                assert [c["state"] for c in cards] == ["seal_ready"], (name, cards)
            else:
                assert len(cards) == 1, (name, cards)
            assert load_persisted(ws)["state"] == "seal_ready", name
            # 再 emit 一张真卡：`_prio` 的兜底（缺省/坏值按 5）参与排序，不 KeyError/TypeError
            emit(ws, NextStep.from_state("pending_findings", "M10", pending=1))
            ordered = load_all(ws)
            assert len(ordered) == 2, (name, ordered)
            assert ordered[0]["state"] == "pending_findings", (name, ordered)  # priority 1 必在前
            if name == "string_priority":
                # "4" 可 coercion ⇒ 按 4 排在 pending_findings(1) 之后、seal_ready 之前无歧义
                assert _prio({"priority": "4"}) == 4, "数字串应 coerce 成 4"
            if name == "non_numeric_string":
                # 非数字串走 ValueError 兜底 ⇒ 按 5（排在 pending_findings 之后）
                assert _prio({"priority": "high"}) == 5, "非数字串必须兜底 5"
                assert ordered[1]["priority"] == "high", (name, ordered)
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        p = ws / ".k3dge" / "next.json"
        p.parent.mkdir(parents=True)
        p.write_text("{ broken", encoding="utf-8")     # 坏 JSON ⇒ "本轮无处理点"，不崩
        assert load_all(ws) == []
        assert load_persisted(ws) is None


def test_begin_run_clears_previous_run():
    """一轮开始的边界：上一条命令的处理点不得留到这一轮。"""
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        emit(ws, _ns("seal_ready"))
        assert load_all(ws)
        begin_run(ws)
        assert load_all(ws) == []
        assert load_persisted(ws) is None


def test_emit_all_orders_and_writes_all():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        begin_run(ws)
        emit_all(ws, [_ns("seal_ready"), _ns("audit_suggested"),
                      NextStep.from_state("audit_open", "M10", pending=3)])
        data = _raw(ws)
        # 同 priority（4）之间的次序不属契约 ⇒ 只断言"按 priority 排 + 集合一致"，不锁平级次序
        assert [c["priority"] for c in data["next"]] == [2, 4, 4]
        assert {c["state"] for c in data["next"]} == {"audit_open", "seal_ready", "audit_suggested"}
        assert data["primary"] == "audit_open"
        # 原子写的残留面（t-189）：`.tmp` + replace 是侧车与 git-hook/MCP 并发共存的前提，
        # 成功后不许留 `next.json.tmp`（留了＝上次替换断在半路，读侧下次读到过期快照）
        assert not (ws / ".k3dge" / "next.json.tmp").exists()


def test_emit_all_merges_with_cards_already_landed_this_run():
    """ocr-275 的行为面（t-189）：`begin_run` 会清空侧车，旧测先 clear 再 emit_all＝
    合并路径从没被走——把 `emit_all` 写成整片覆盖，全部断言照样绿。

    正确形状：本轮里 `emit`/`persist` 先落地的处理点，其后 `emit_all` 必须**并**进去，
    不抹掉（同轮多源：前一个 hook 的拒绝 + 本命令的汇总判定共存）。
    """
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        begin_run(ws)
        emit(ws, _ns("doc_fix"))                                   # 单点先落
        emit_all(ws, [NextStep.from_state("new_domain", "M10")])   # 汇总随后到
        states = {c["state"] for c in load_all(ws)}
        assert {"doc_fix", "new_domain"} <= states, f"emit_all 整片覆盖了先落的 {states}"
        # 平级 tie 不锁（同上），但 primary 必须是现存卡里 priority 最小者
        prim = load_all(ws)[0]
        assert prim["priority"] == min(c["priority"] for c in load_all(ws))
        persisted = load_persisted(ws)
        assert persisted["priority"] == min(c["priority"] for c in load_all(ws)), (
            f"primary 独立字段必须指向合并后最小 priority 卡，拿到 {persisted}")
        assert persisted["state"] == prim["state"]
        assert not (ws / ".k3dge" / "next.json.tmp").exists()


def test_stale_tmp_does_not_survive_next_write(tmp_path):
    """ocr2-756：旧断言只认字面 `next.json.tmp`——实现换成唯一 tmp 名（并发标准修法）时
    断言空转，而陈旧 tmp 照堆。同时"上次替换断半路"的故障从没被真的模拟过。
    种一个陈旧 tmp 再走一次成功写：侧车有效，且 `.k3dge/` 下不留任何 tmp 残留
    （固定名与唯一名两种实现都必须满足——断的是目录面，不是字面名）。"""
    ws = Path(tmp_path)
    (ws / ".k3dge").mkdir(parents=True)
    (ws / ".k3dge" / "next.json.tmp").write_text('{"stale": true}\n', encoding="utf-8")
    emit(ws, _ns("seal_ready"))
    assert (ws / ".k3dge" / "next.json").is_file()
    data = _raw(ws)
    assert data["primary"] == "seal_ready", data  # 读到的是新写，不是陈旧 tmp
    leftovers = list((ws / ".k3dge").glob("*.tmp"))
    assert leftovers == [], leftovers


def test_emit_all_prints_in_priority_order(capsys):
    import sys

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        begin_run(ws)
        emit_all(ws, [_ns("seal_ready"), NextStep.from_state("pending_findings", "M10", pending=1)],
                 stream=sys.stdout)
        out = capsys.readouterr().out
        assert out.index("pending_findings") < out.index("seal_ready")


def test_load_persisted_accepts_legacy_single_shape():
    """向后兼容：旧侧车是单条 `{"state": ...}` ⇒ 仍能读出主处理点。"""
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / ".k3dge").mkdir(parents=True)
        (ws / ".k3dge" / "next.json").write_text(
            json.dumps({"state": "sealed", "milestone": "M5", "fact": "旧形状"}), encoding="utf-8")
        assert load_persisted(ws)["state"] == "sealed"
        assert [c["state"] for c in load_all(ws)] == ["sealed"]


def test_emit_writes_sidecar_and_returns_text():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        text = emit(ws, _ns())
        assert "[NEXT]" in text and "seal_ready" in text
        assert (ws / ".k3dge" / "next.json").is_file()


def test_emit_with_stream_prints(capsys):
    import sys

    with tempfile.TemporaryDirectory() as d:
        emit(Path(d), _ns(), stream=sys.stdout)
        assert "[NEXT]" in capsys.readouterr().out


def test_emit_without_stream_no_print(capsys):
    with tempfile.TemporaryDirectory() as d:
        emit(Path(d), _ns())
        assert capsys.readouterr().out == ""
