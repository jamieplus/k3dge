"""peer 面（mcp_peers）：降级告警与 `.mcp.json` 状态区分。"""

from pathlib import Path


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
    """缺失/坏文件/真的没声明 是三种事实，旧都报同一句话（386）。"""
    import argparse
    import json

    from k3dge.cli.mcp_peers import cmd_mcp_probe

    args = argparse.Namespace(timeout=1, json=True)
    cases = {
        "没有 ": None,                       # 文件不存在
        "读不出/形状不对": "{ not json",       # 坏 JSON
        "没有声明任何 server": '{"other": 1}',  # 有文件没 mcpServers
    }
    for expect, body in cases.items():
        ws = Path(str(tmp_path) + f"-{abs(hash(expect))}")
        ws.mkdir(parents=True, exist_ok=True)
        if body is not None:
            (ws / ".mcp.json").write_text(body, encoding="utf-8")
        err = __import__("io").StringIO()
        with __import__("contextlib").redirect_stderr(err):
            rc = cmd_mcp_probe(args, ws)
        assert rc == 1
        assert expect in err.getvalue(), (expect, err.getvalue())
