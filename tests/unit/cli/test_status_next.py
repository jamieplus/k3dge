"""`cli/status` 的观测面：展示用遥测不得按缺省预算跑传输链；路由坏了不得说成"没待办"（ocr-387/389）。"""

import contextlib
import io
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from k3dge.cli import status as st
import shutil
import atexit


@pytest.fixture()
def ws(tmp_path: Path) -> Path:
    (tmp_path / ".k3che").mkdir()
    (tmp_path / ".agent").mkdir()
    (tmp_path / ".agent" / "manifest.json").write_text(
        '{"package_root":"src","domains":{}}', encoding="utf-8")
    return tmp_path


def test_cache_observability_runs_with_a_short_budget(ws: Path) -> None:
    """调用形状漂移要**当场可诊断**（t-035）。

    `cache_observability()` 吞一切异常返回 None——旧的手写 `fake` 把返回值扔掉、只记
    kwargs：哪天 `run_action` 加了位置参或改了签名，TypeError 被静默吃掉，本测红成
    "{} == 10"（读起来像预算回归，实际是形状漂移）。换成可断言的 Mock：
    调用发生过、返回值被消费（payload 进投影）、kwargs 形状钉住。
    """
    result = mock.Mock(ok=True, provider="mcp", payload='{"ok": true, "total": 1}')
    with mock.patch("k3dge.engine.pipeline_runner.run_action",
                    return_value=result) as rm:
        out = st.cache_observability(ws)
    rm.assert_called_once()
    assert rm.call_args.kwargs.get("timeout_default") == 10, rm.call_args   # 展示件不得占 60s 缺省
    assert out == {"total": 1}, out    # 返回值真被消费（payload→投影；吞成 None 即红）


def test_lifecycle_next_warns_when_routing_breaks(ws: Path) -> None:
    """钉"注入的破坏**真的发生过**"（t-033）。

    `lifecycle_next()` 整个函数体包在 `except Exception` 里、任何失败都渲染 WARN+None——
    旧断言分不清 None 来自被注入的那次调用还是**无关错误**（manifest 缺失、patch 落点
    搬家后变成 inert 等）。换真 mock：调用次数断言 + WARN 文本必须带注入错文
    （生产渲染 `type(exc).__name__: exc`，`boom` 应出现在 stderr）。
    """
    err = io.StringIO()
    boom = mock.Mock(side_effect=RuntimeError("boom"))
    with mock.patch("k3dge.engine.milestone_pointer.get_current_milestone", return_value="M9"), \
            mock.patch("k3dge.engine.milestone_audit.scan_pending_findings", boom), \
            contextlib.redirect_stderr(err):
        assert st.lifecycle_next(ws) is None
    boom.assert_called_once()
    text = err.getvalue()
    assert "WARN" in text, "把'路由坏了'渲染成'没有下一步'"
    assert "boom" in text, text


def test_seal_ready_for_reuses_precomputed_scans() -> None:
    """status 已算过票与前置闸，`seal_ready_for` 不得再各扫一遍（388）。"""
    from k3dge.engine import nextstep

    root = Path(tempfile.mkdtemp())
    atexit.register(shutil.rmtree, root, True)
    (root / ".agent").mkdir()
    with mock.patch("k3dge.engine.seal.unmet_seal_preconditions") as unmet, \
            mock.patch("k3dge.engine.task_index.scan_milestone_tasks") as tasks:
        ns = nextstep.seal_ready_for(root, "M9", unmet=[], tasks=[object()])
    assert ns.state == "seal_ready"
    unmet.assert_not_called()
    tasks.assert_not_called()
