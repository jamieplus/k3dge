"""peer 面（mcp_peers）：降级告警与 `.mcp.json` 状态区分。"""


class TestNonObjectPeerEntry:
    """ocr2-579：`.mcp.json` 里已有非对象 peer 条目时必须出声，不得静默丢弃探到的 sibling。"""

    def test_existing_non_object_entry_warns_and_preserves_user_content(self, tmp_path, capsys) -> None:
        from unittest import mock

        from k3dge.cli import mcp_peers as mp

        (tmp_path / ".mcp.json").write_text(
            '{"mcpServers": {"k3dit": "python -m k3dit"}}', encoding="utf-8")
        with mock.patch.object(mp, "probe_peer_mcp",
                               return_value=(str(tmp_path.parent / "k3dit"), "k3dit.mcp", "/x/src")):
            err = mp._sync_peers_into_mcp(tmp_path, {"peers": {"k3dit": {"enabled": True}}})
        assert err is None, err
        out = capsys.readouterr().err
        assert "不是对象" in out, out
        assert "k3dit" in out, out
        # 用户内容原样保留（不断言、不覆盖，只出声）
        import json

        data = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
        assert data["mcpServers"]["k3dit"] == "python -m k3dit", data



def test_peer_fallback_warn_prints_once_plain_in_non_tty() -> None:
    """非 TTY 仍打 ANSI 且同一告警印两遍 ⇒ 下游按 WARN[DOWNGRADE] 计数翻倍（385）。"""
    import contextlib
    import io

    from k3dge.cli.mcp_peers import _peer_fallback_warn

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        _peer_fallback_warn("k3dit", "timeout", "manual")
    out = err.getvalue()
    assert out.count("WARN[DOWNGRADE]") == 1, out
    assert "\033[" not in out, out
    # ocr2-704：光数 marker 时"丢正文/换参/多行 double-print"回归照样绿——钉单行 + 三事实
    lines = [l for l in out.splitlines() if "WARN[DOWNGRADE]" in l]
    assert len(lines) == 1, out
    assert "k3dit" in lines[0] and "timeout" in lines[0], lines[0]
    assert "fallback to DEFAULT" in lines[0] and "manual" in lines[0], lines[0]


def test_probe_distinguishes_missing_corrupt_and_empty(tmp_path) -> None:
    """缺失/坏文件/真的没声明 是三种事实，旧都报同一句话（386）。

    夹具收口（t-005）：工作区从 `str(tmp_path)+abs(hash(...))` 的**兄弟目录**改为
    `tmp_path` 下的确定子目录——旧形状三病：①落在 fixture 管外，残留不回收；
    ②`hash(str)` 随 PYTHONHASHSEED 漂移，失败现场无法复现；seed 钉死时
    `exist_ok=True` 又不清旧内容，"缺文件"用例可能继承上一轮的坏 `.mcp.json`，
    断言变成历史相关。
    判据收口（t-006）：`"没有 "`（两字符＋尾随空格，格式化一strip就退化成通用子串）
    改为三条**互斥 needle**——本例必中、另两例必无，"实现把三句话全印出来"
    这种回归旧测放得过。
    """
    import argparse
    import contextlib
    import io
    from unittest import mock

    from k3dge.cli.mcp_peers import cmd_mcp_probe

    args = argparse.Namespace(timeout=1, json=True)
    # (期望 needle, 文件内容或 None)：needle 取三句措辞的**互斥核**（不含路径、不含尾随空格）
    cases = [
        ("（跑 k3dge mcp sync 生成）", None),           # 文件不存在
        ("读不出/形状不对", "{ not json"),                # 坏 JSON
        ("里没有声明任何 server", '{"other": 1}'),        # 有文件但没 mcpServers
    ]
    needles = [n for n, _b in cases]
    # ocr2-705：本测只走静态早退分支——若 loader 回退到注入默认端点，执行会掉进真握手
    # （spawn 子进程、挂/flake 才红）。把活路桩成显式失败，掉进去就当场红。
    with mock.patch("k3dge.engine.pipeline_runner.probe_servers",
                    side_effect=AssertionError("掉进真握手：早退分支已失守")) as _live:
        for idx, (expect, body) in enumerate(cases):
            ws = tmp_path / f"ws{idx}"                    # fixture 管内、确定性命名、天然隔离
            ws.mkdir(parents=True, exist_ok=True)
            if body is not None:
                (ws / ".mcp.json").write_text(body, encoding="utf-8")
            else:
                assert not (ws / ".mcp.json").exists()    # "缺文件"分支真的没有历史残留
            err = io.StringIO()
            sout = io.StringIO()
            # ocr2-407①：诊断必须绑定传入的 workspace，不能指到进程 CWD 的真仓。
            # ocr2-407②：json=True 时机器可读流走 stdout——早退路径 stdout 必须空，
            # 否则人类诊断污染 JSON 消费方；只听 stderr 会漏检。
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(sout):
                rc = cmd_mcp_probe(args, ws)
            text = err.getvalue()
            assert rc == 1
            assert expect in text, (expect, text)
            assert str(ws / ".mcp.json") in text, (str(ws), text)
            assert sout.getvalue() == "", f"早退路径 stdout 必须空（json 通道污染）：{sout.getvalue()!r}"
            for other in needles:
                if other != expect:
                    assert other not in text, (expect, other, text)
    _live.assert_not_called()  # ocr2-705：三例全走早退，真握手一次都不得被碰


def test_sync_peers_rejects_non_table_peers(tmp_path) -> None:
    """ocr2-175：`[[peers]]`/`peers.x=true` 不得让整条合并 AttributeError 崩掉。"""
    from k3dge.cli import mcp_peers as mp

    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp.json").write_text("{}", encoding="utf-8")
    err = mp._sync_peers_into_mcp(tmp_path, {"peers": [{"x": 1}]})
    assert err is not None and "不是表" in err, err


def test_warn_missing_peers_survives_malformed_peer(tmp_path) -> None:
    """ocr2-176：坏 peer 不得连坐其余 peer 的告警（调用方吞异常 ⇒ 循环内绝不能抛）。"""
    import contextlib
    import io

    from k3dge.cli import mcp_peers as mp

    (tmp_path / ".mcp.json").write_text("{}", encoding="utf-8")
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        mp._warn_missing_peer_servers(
            tmp_path, {"peers": {"bad": True, "k3dit": {"enabled": True}}})
    text = err.getvalue()
    assert "形状不对" in text, text
    assert "k3dit" in text, text


def test_cmd_mcp_sync_qualifies_success_when_peers_skipped(tmp_path, capsys) -> None:
    """ocr2-177：跳过 peer 合并时成功行必须自述 k3dge-only，不得裸报 synced。"""
    from k3dge.cli import mcp_peers as mp

    (tmp_path / ".agent").mkdir(parents=True, exist_ok=True)
    rc = mp.cmd_mcp_sync(tmp_path)
    out = capsys.readouterr().out
    assert rc == 0
    assert "k3dge only" in out, out
