"""`k3dge milestone seal-check <id>`：只读全量封板前置清单（#3）。

判据：全绿 ⇒ 退 0；有未过项 ⇒ 退 1（供 CI/脚本问"现在能封吗"）。不执行任何动作。
"""

import io
from contextlib import redirect_stdout
from pathlib import Path

from k3dge.cli.main import main


def _ws(tmp_path: Path, preconditions: str) -> Path:
    (tmp_path / ".agent").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".agent" / "milestone").write_text("M10\n", encoding="utf-8")
    (tmp_path / ".agent" / "pipeline.toml").write_text(
        f"[checks.seal]\npreconditions = [{preconditions}]\n", encoding="utf-8")
    return tmp_path


def test_all_green_exits_zero(tmp_path, monkeypatch):
    """必须**真有一项通过**才算验过"全绿"：空 preconditions 一条 ✅ 都不生成，
    而 `"✅" not in out or "❌" not in out` 只要少一个符号就成立 ⇒ 绿色项转红也抓不到（t-002）。"""
    ws = _ws(tmp_path, '"guides_filled"')          # 空仓里这条真会过（无 docs/guides ⇒ 无未填桩）
    monkeypatch.chdir(ws)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["milestone", "seal-check", "M10"])
    out = buf.getvalue()
    assert rc == 0, out
    assert "封板前置清单（M10）" in out
    assert "✅ guides_filled" in out, out         # 阳性面：声明的闸确实被判过
    assert "❌" not in out, out                   # 阴性面：没有任何未过项


def test_failing_gate_shows_red_and_exits_1(tmp_path, monkeypatch):
    """挑一条**真需要人办**的闸：`align_pass` 会被 `satisfies` 标成 ⚙️（seal 自己会跑），
    不是 ❌ ⇒ 用它当"红样例"只会测到自动档。`guides_filled` 有未填桩才是人办红。"""
    ws = _ws(tmp_path, '"guides_filled"')
    (ws / "docs" / "guides").mkdir(parents=True)
    (ws / "docs" / "guides" / "g.md").write_text("# G\n<!-- k3dge:guide-stub -->\n", encoding="utf-8")
    monkeypatch.chdir(ws)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["milestone", "seal-check", "M10"])
    out = buf.getvalue()
    assert rc == 1, out
    assert "❌ guides_filled" in out, out
    assert "✅" not in out, out


def test_empty_precondition_list_renders_zero_of_zero(tmp_path, monkeypatch):
    """空声明＝0/0：形状单独钉住，别再让它冒充"全绿"。"""
    ws = _ws(tmp_path, "")
    monkeypatch.chdir(ws)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["milestone", "seal-check", "M10"])
    out = buf.getvalue()
    assert rc == 0 and "✅" not in out and "0/0 通过" in out, out


def test_unmet_exits_one_and_lists_reason(tmp_path, monkeypatch):
    # 空仓里形式闸几乎都"过"（无 guides/无 ADR ＝ 无偏差）⇒ 放一个 guide-stub 才是真失败项
    ws = _ws(tmp_path, '"guides_filled"')
    (ws / "docs" / "guides").mkdir(parents=True, exist_ok=True)
    (ws / "docs" / "guides" / "g.md").write_text("# G\n<!-- k3dge:guide-stub -->\n", encoding="utf-8")
    monkeypatch.chdir(ws)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["milestone", "seal-check", "M10"])
    out = buf.getvalue()
    assert rc == 1
    assert "❌ guides_filled" in out
    assert "需你先办 1 项" in out
    # durable 证据一栏（ADR-0004 §2.1.10）：只陈述事实，不影响退出码
    assert "[EVIDENCE]" in out


def test_read_only_does_not_touch_state(tmp_path, monkeypatch):
    """只读＝**全文件内容快照**对账（t-003），不是路径集合差。

    旧形状的三处欠账：①只比 `after - before`——**改了既有票/报告/配置**、或删文件，
    都不违反"新增皆 logs"，全部逃逸；②白名单是裸 `startswith("logs")`，
    `logs.md`、`logsbackup/x.json` 一并放行；③注释点名"不得产侧车 .k3dge/next.json"，
    却没有任何断言——写进**已存在**的 `.k3dge/` 在集合差里根本不可见。
    """
    ws = _ws(tmp_path, '"tasks_all_done", "guides_filled", "docs_normalized"')
    (ws / ".k3dge").mkdir()                      # 先有侧车目录：写它里面的东西集合差看不见
    (ws / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
    (ws / "docs" / "tasks" / "2026-09-01-M10-idea-x.md").write_text(
        "---\nstatus: idea\nmilestone: M10\npriority: P2\ndate: 2026-09-01\n---\n\n# X\n",
        encoding="utf-8")
    monkeypatch.chdir(ws)

    def snap() -> dict:
        return {p.relative_to(ws).as_posix(): p.read_bytes()
                for p in ws.rglob("*") if p.is_file() and "__pycache__" not in p.parts}

    before = snap()
    assert any(k.startswith("docs/tasks/") for k in before), "既有票没建出来，快照对账无从谈起"
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(["milestone", "seal-check", "M10"])
    out = buf.getvalue()
    # ocr2-412：空 preconditions 下闸求值零次，快照只审了空转——声明真闸并钉住求值发生。
    assert "0/0 通过" not in out, f"清单一条闸都没求值 ⇒ 快照只审到了空转：{out[-500:]}"
    assert "tasks_all_done" in out and "guides_filled" in out, out[-800:]
    after = snap()
    changed = {k for k in before.keys() & after.keys() if before[k] != after[k]}
    assert not changed, f"只读命令改了既有文件：{sorted(changed)}"
    removed = set(before) - set(after)
    assert not removed, f"只读命令删了既有文件：{sorted(removed)}"
    added = set(after) - set(before)
    assert all(p == "logs/k3dge.log" or p.startswith("logs/") for p in added), \
        f"白名单只认 logs/ 目录本身，logs.md/logsbackup 不算：{added}"
    assert not (ws / ".k3dge" / "next.json").exists(), "只读命令不得产侧车"
