"""`cli/status` 的观测面：展示用遥测不得按缺省预算跑传输链；路由坏了不得说成"没待办"（ocr-387/389）。"""

import contextlib
import io
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from k3dge.cli import status as st
# **先于任何 mock.patch 固化绑定**：`lifecycle_next` 在函数体内懒导入 `audit_trigger`，
# 而 audit_trigger 模块级 `from milestone_pointer import get_current_milestone`——若它的
# 首次导入发生在下面某个 `patch(milestone_pointer.get_current_milestone)` 上下文**里面**，
# 捕获进模块状态的就是 mock（return_value 定死），patch 退出也不还原 ⇒ 后续任何测试
# 进程内 `compute_audit_suggestion` 的里程碑恒为假值（实测：三文件组合下 seal_flow 的
# 账齐断言红；全套件只是碰巧有人先导入才没炸）。这里用 `import_module` 触发首次导入
# ——不是 Import 语句，卫生守卫（AST 判死导入）不误报，名字也不必假装被用。
import importlib

importlib.import_module("k3dge.engine.audit_trigger")
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
        ns = st.lifecycle_next(ws)
    boom.assert_called_once()
    # ocr2-178：路由坏了不得渲染成"没待办"（None）⇒ 投专用态，机器面可区分。
    assert ns is not None and ns.state == "routing_error", ns
    text = err.getvalue()
    assert "WARN" in text, "把'路由坏了'渲染成'没有下一步'"
    assert "boom" in text, text


def test_seal_ready_for_reuses_precomputed_scans() -> None:
    """status 已算过票与前置闸，`seal_ready_for` 不得再各扫一遍（388）。"""
    from k3dge.engine import nextstep

    # （t-034 尾账）`unmet=`/`tasks=` 都给齐时 `seal_ready_for` 短路返回、零磁盘 IO——
    # 旧夹具的 `(root / ".agent").mkdir()` 是死 setup，删掉；root 只当形参占位。
    root = Path(tempfile.mkdtemp())
    atexit.register(shutil.rmtree, root, True)
    with mock.patch("k3dge.engine.seal.unmet_seal_preconditions") as unmet, \
            mock.patch("k3dge.engine.task_index.scan_milestone_tasks") as tasks:
        ns = nextstep.seal_ready_for(root, "M9", unmet=[], tasks=[object()])
    assert ns.state == "seal_ready"
    unmet.assert_not_called()
    tasks.assert_not_called()


def test_workspace_status_returns_error_shape_when_scan_raises(ws: Path) -> None:
    """ocr2-179：核心扫描抛错时两个出口都要拿到 error 形，不得逸出 traceback。"""
    with mock.patch.object(st, "cache_observability", return_value=None), \
            mock.patch.object(st, "ConsistencyEngine") as eng:
        eng.return_value.evaluate.side_effect = RuntimeError("boom")
        out = st.workspace_status(ws)
    assert out["ok"] is False and out["error"] == "StatusScanFailed", out
    assert "boom" in out["message"], out


def test_workspace_status_done_vocabulary_is_single_source_and_case_insensitive(ws: Path) -> None:
    """ocr2-180：`done` 词表取自引擎单源；正文 `Status` 匹配须忽略大小写。"""
    tasks = ws / "docs" / "tasks"
    tasks.mkdir(parents=True)
    (tasks / "T1-x.md").write_text("# T1\n\n- **STATUS**: Done\n", encoding="utf-8")
    with mock.patch.object(st, "cache_observability", return_value=None):
        out = st.workspace_status(ws)
    assert out["unfinished_tasks"] == [], out
    (tasks / "T2-y.md").write_text("# T2\n\n- **Status**: in-progress\n", encoding="utf-8")
    with mock.patch.object(st, "cache_observability", return_value=None):
        out2 = st.workspace_status(ws)
    assert [t["task"] for t in out2["unfinished_tasks"]] == ["T2-y"], out2


def test_lifecycle_next_scans_once_for_whole_render(ws: Path) -> None:
    """ocr2-413：上面的短路只钉了 `seal_ready_for` 自己——如果 `lifecycle_next`
    在调用点漏传 `unmet=`/`tasks=`，高频 status 路径照样双扫而上测仍绿。
    穿过真 `st.lifecycle_next` 钉：整轮渲染里两扫描各恰一次，且 kwargs 透传。"""
    from k3dge.engine import nextstep

    sentinel_tasks = [{"path": "t.md"}]
    with mock.patch("k3dge.engine.milestone_pointer.get_current_milestone",
                    return_value="M9"), \
            mock.patch("k3dge.engine.milestone_audit.scan_pending_findings",
                       return_value=(0, [])), \
            mock.patch("k3dge.engine.seal.unmet_seal_preconditions",
                       return_value=[]) as unmet, \
            mock.patch("k3dge.engine.task_index.scan_milestone_tasks",
                       return_value=sentinel_tasks) as tasks, \
            mock.patch.object(nextstep, "seal_ready_for",
                              wraps=nextstep.seal_ready_for) as srf:
        ns = st.lifecycle_next(ws)
    assert ns is not None and ns.state == "seal_ready", ns
    unmet.assert_called_once()
    tasks.assert_called_once()
    srf.assert_called_once()
    assert srf.call_args.kwargs.get("unmet") == []
    assert srf.call_args.kwargs.get("tasks") == sentinel_tasks
