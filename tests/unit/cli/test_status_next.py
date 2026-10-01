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
    seen = {}

    class R:
        ok, provider, payload = True, "mcp", '{"ok": true, "total": 1}'

    def fake(workspace, ref, **kw):
        seen.update(kw)
        return R()

    with mock.patch("k3dge.engine.pipeline_runner.run_action", side_effect=fake):
        st.cache_observability(ws)
    assert seen.get("timeout_default") == 10, seen      # 展示件不得占着 60s/跳的缺省


def test_lifecycle_next_warns_when_routing_breaks(ws: Path) -> None:
    err = io.StringIO()
    with mock.patch("k3dge.engine.milestone_pointer.get_current_milestone", return_value="M9"), \
            mock.patch("k3dge.engine.milestone_audit.scan_pending_findings",
                       side_effect=RuntimeError("boom")), \
            contextlib.redirect_stderr(err):
        assert st.lifecycle_next(ws) is None
    assert "WARN" in err.getvalue(), "把'路由坏了'渲染成'没有下一步'"


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
