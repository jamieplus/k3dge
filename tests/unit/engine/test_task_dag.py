"""任务 DAG 透镜：blocking 环 + CPM 关键路径。"""
from __future__ import annotations

from pathlib import Path

from k3dge.engine import task_dag


def _task(ws: Path, stem: str, blocking: str = "") -> None:
    d = ws / "docs" / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    body = f"---\nstatus: idea\nmilestone: M9\nblocking: {blocking}\n---\n\n# {stem}\n"
    (d / f"{stem}.md").write_text(body, encoding="utf-8")


def test_critical_path_follows_blocking_chain(tmp_path: Path) -> None:
    _task(tmp_path, "a", "b")
    _task(tmp_path, "b", "c")
    _task(tmp_path, "c")
    assert task_dag.blocking_cycles(tmp_path)["cyclic"] is False
    cp = task_dag.critical_path(tmp_path)
    assert cp["path"] == ["a", "b", "c"] and cp["length"] == 3


def test_blocking_cycle_detected(tmp_path: Path) -> None:
    _task(tmp_path, "a", "b")
    _task(tmp_path, "b", "a")
    assert task_dag.blocking_cycles(tmp_path)["cyclic"] is True
    assert task_dag.critical_path(tmp_path)["path"] == []


def test_unknown_blocking_ignored(tmp_path: Path) -> None:
    _task(tmp_path, "a", "does-not-exist")
    assert task_dag.blocking_graph(tmp_path)["a"] == []
