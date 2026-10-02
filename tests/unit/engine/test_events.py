"""events: append-only JSONL + rotate + read_events."""
import json
import tempfile
from pathlib import Path

from k3dge.engine import events


def test_emit_writes_jsonl():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        events.emit(ws, "gate_pass", violations=0)
        f = ws / ".k3dge" / "events.jsonl"
        assert f.is_file()
        entry = json.loads(f.read_text(encoding="utf-8").strip())
        assert entry["evt"] == "gate_pass"
        assert entry["violations"] == 0
        assert "ts" in entry


def test_emit_appends():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        events.emit(ws, "gate_pass")
        events.emit(ws, "audit_submit", job_id="abc")
        lines = (ws / ".k3dge" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[1])["job_id"] == "abc"


def test_emit_never_raises_but_really_fails(tmp_path) -> None:
    r"""(t-109) `/dev/null/fake` 只在 POSIX 上"不可写"：Windows 解成 `<盘>:\dev\null\fake`，
    mkdir 直接**成功**——失败支路从没走、事件文件写到沙箱外、测还是绿的。
    换跨平台必然失败：`.k3dge` 的位置放一个普通文件 ⇒ `mkdir(parents=True, exist_ok=True)`
    恒抛被吞。判据也不止"不抛"：事后**没产任何文件**（失败真发生了）。
    """
    ws = tmp_path
    blocker = ws / ".k3dge"
    blocker.write_text("我是普通文件，不是目录\n", encoding="utf-8")
    events.emit(ws, "gate_pass")                      # 不得抛
    assert blocker.read_text(encoding="utf-8") == "我是普通文件，不是目录\n"
    assert not (ws / ".k3dge" / "events.jsonl").exists()


def test_rotate_keeps_tail():
    """旋转语义从常量推导（t-110）：旧断言 `<=1000 + 末行 + 首行>0` 被"只留最后一行"
    的实现照样喂饱——`_KEEP_LINES=800` 其实没人验；`1000` 还复制了常量，一改就烂。
    现在钉：**连续**尾段、末条＝全序最后、长度＝_KEEP_LINES+尾追数。
    """
    total = events._MAX_LINES + 100            # 越阈一次触发旋转，之后再尾追 100 条
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        for i in range(total):
            events.emit(ws, "evt", i=i)
        lines = (ws / ".k3dge" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        idx = [json.loads(l)["i"] for l in lines]
        assert idx[-1] == total - 1, idx[-5:]
        assert idx == list(range(idx[0], total)), "留存段不连续（只留了尾巴？）"
        assert len(idx) >= events._KEEP_LINES, f"旋转后只剩 {len(idx)}，低于保留额 {events._KEEP_LINES}"
        assert len(idx) <= events._MAX_LINES + 100
        assert idx[0] == total - len(idx) >= 0, "头部没截断＝旋转根本没跑"


def test_read_events():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        assert events.read_events(ws) == []
        for i in range(5):
            events.emit(ws, "evt", i=i)
        got = events.read_events(ws, last=3)
        assert len(got) == 3
        assert [e["i"] for e in got] == [2, 3, 4]


def test_read_events_guard_rails(tmp_path):
    """`read_events` 的四条护栏此前只测了 happy path（t-111）：

    - `last<=0` 必须 `[]`：删掉那个分支后 `lines[-0:]` 会回**全部**（ocr-242）；
    - `last` 大于存量 ⇒ 全量不越界；
    - 缺省 `last=20` 真的截断；
    - 坏行/非对象 JSONL 被逐行滤掉（`except JSONDecodeError: continue` 与
      `isinstance(dict)` 两条护栏的存在理由）。
    """
    for i in range(5):
        events.emit(tmp_path, "evt", i=i)
    assert events.read_events(tmp_path, last=0) == []
    assert events.read_events(tmp_path, last=-1) == []
    assert [e["i"] for e in events.read_events(tmp_path, last=99)] == [0, 1, 2, 3, 4]
    assert len(events.read_events(tmp_path)) == 5          # 缺省 20，存 5
    p = tmp_path / ".k3dge" / "events.jsonl"
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("{坏行\n" + json.dumps(["不是对象"]) + "\n")
    tail = events.read_events(tmp_path, last=7)
    assert [e["i"] for e in tail] == [0, 1, 2, 3, 4], tail


def test_next_persist_emits_next_event():
    """nextstep.persist() 内部复用 events.emit → events.jsonl 有 next 行。"""
    from k3dge.engine.nextstep import NextStep, persist
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        persist(ws, NextStep.from_state("seal_ready", "M10"))
        got = events.read_events(ws)
        assert len(got) == 1
        assert got[0]["evt"] == "next"
        assert got[0]["state"] == "seal_ready"
