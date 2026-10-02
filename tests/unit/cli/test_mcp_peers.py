"""peer 面（mcp_peers）：降级告警与 `.mcp.json` 状态区分。"""


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

    from k3dge.cli.mcp_peers import cmd_mcp_probe

    args = argparse.Namespace(timeout=1, json=True)
    # (期望 needle, 文件内容或 None)：needle 取三句措辞的**互斥核**（不含路径、不含尾随空格）
    cases = [
        ("（跑 k3dge mcp sync 生成）", None),           # 文件不存在
        ("读不出/形状不对", "{ not json"),                # 坏 JSON
        ("里没有声明任何 server", '{"other": 1}'),        # 有文件但没 mcpServers
    ]
    needles = [n for n, _b in cases]
    for idx, (expect, body) in enumerate(cases):
        ws = tmp_path / f"ws{idx}"                    # fixture 管内、确定性命名、天然隔离
        ws.mkdir(parents=True, exist_ok=True)
        if body is not None:
            (ws / ".mcp.json").write_text(body, encoding="utf-8")
        else:
            assert not (ws / ".mcp.json").exists()    # "缺文件"分支真的没有历史残留
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = cmd_mcp_probe(args, ws)
        text = err.getvalue()
        assert rc == 1
        assert expect in text, (expect, text)
        for other in needles:
            if other != expect:
                assert other not in text, (expect, other, text)
