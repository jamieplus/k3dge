"""过程审计面：证据链完整性/可追溯闸（process_audit）。"""
from __future__ import annotations

import subprocess
from pathlib import Path

from k3dge.engine import process_audit

_HEADER = "ID|日期|严重度|优先级|类型|问题描述|位置|状态|处置|验证|复审|验收"
_ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _report(ws: Path, *, sign: bool, name: str = "2026-09-13-M9-audit.md") -> Path:
    reviews = ws / "docs" / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    lines = ["# Audit M9", f"| {_HEADER} |", "| --- |"]
    if sign:
        lines += ["- **审计人**: k3dit", "- **透镜来源**: k3dit 工单",
                  "- **基线**: " + "0" * 40]   # 本层只验"可解析"，不需真 sha
    p = reviews / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _git(ws: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(ws), *args], check=True, capture_output=True, env=_ENV)


def test_evidence_chain_ok_when_signed_and_tracked(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-qb", "main", str(tmp_path)], check=True, capture_output=True, env=_ENV)
    _report(tmp_path, sign=True)
    _git(tmp_path, "add", "-A")
    assert process_audit.evidence_chain_error(tmp_path, "M9") is None


def test_evidence_chain_missing_signature(tmp_path: Path) -> None:
    _report(tmp_path, sign=False)
    err = process_audit.evidence_chain_error(tmp_path, "M9")
    assert err is not None and "不完整" in err


def test_evidence_chain_untracked_report(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-qb", "main", str(tmp_path)], check=True, capture_output=True, env=_ENV)
    _report(tmp_path, sign=True)
    err = process_audit.evidence_chain_error(tmp_path, "M9")
    assert err is not None and "不可追溯" in err


def test_evidence_chain_missing_baseline(tmp_path: Path) -> None:
    """`基线` 是必填的内容锚点（#1）：缺它 ⇒ 证据链不完整。

    为何：报告的 `- **基线**: <sha>` 是**durable** 的"报告对应当前内容"依据（随报告入库）；
    `.agent/audit_jobs.json` 是 gitignored 的本地状态，新克隆/CI 没有它 ⇒ 不能作为判据。
    """
    subprocess.run(["git", "init", "-qb", "main", str(tmp_path)], check=True, capture_output=True, env=_ENV)
    reviews = tmp_path / "docs" / "reviews"
    reviews.mkdir(parents=True)
    (reviews / "2026-09-13-M9-audit.md").write_text(
        "\n".join(["# Audit M9", f"| {_HEADER} |", "| --- |",
                   "- **审计人**: k3dit", "- **透镜来源**: k3dit 工单"]) + "\n",
        encoding="utf-8")
    _git(tmp_path, "add", "-A")
    err = process_audit.evidence_chain_error(tmp_path, "M9")
    assert err and "基线" in err
