"""封版 ADR 硬闸：全 Accepted + 可解析落地指针。"""
import tempfile
from pathlib import Path

from k3dge.engine import adr_gate


def _ws(d, adrs):
    root = Path(d)
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "docs" / "specs" / "x").mkdir(parents=True)
    (root / "docs" / "specs" / "x" / "spec.md").write_text("# spec\n", encoding="utf-8")
    for name, body in adrs.items():
        (root / "docs" / "adr" / name).write_text(body, encoding="utf-8")
    return root


def test_no_adrs_pass():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {})
        assert adr_gate.adrs_all_accepted(ws) is None
        assert adr_gate.adr_landed(ws) is None


def test_all_accepted_and_landed_pass():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {
            "0001-a.md": "---\nStatus: Accepted\nLanded-by: docs/specs/x/spec.md §2\n---\n# ADR-0001\n",
        })
        assert adr_gate.adrs_all_accepted(ws) is None
        assert adr_gate.adr_landed(ws) is None


def test_draft_blocks():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {"0001-a.md": "---\nStatus: Draft\n---\n# ADR-0001\n"})
        assert "未 Accepted" in (adr_gate.adrs_all_accepted(ws) or "")


def test_missing_or_bad_pointer_blocks():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {"0001-a.md": "---\nStatus: Accepted\n---\n# ADR-0001\n"})
        assert "缺可解析落地指针" in (adr_gate.adr_landed(ws) or "")
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {"0001-a.md": "---\nStatus: Accepted\nLanded-by: docs/nope.md\n---\n# ADR-0001\n"})
        assert "指针不可解析" in (adr_gate.adr_landed(ws) or "")


def test_reconcile_supersedes_auto_marks_old():
    """ADR-0002 Supersedes: ADR-0001 → 自动将 0001 标记为 Superseded 并移入 obsolete/。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {
            "0001-old.md": "---\nStatus: Accepted\nSupersedes: -\n---\n# ADR-0001\n",
            "0002-new.md": "---\nStatus: Accepted\nSupersedes: ADR-0001\nLanded-by: docs/specs/x/spec.md\n---\n# ADR-0002\n",
        })
        result = adr_gate.reconcile_supersedes(ws)
        assert result is not None
        assert "ADR RECONCILED" in result
        # 旧 ADR 已移入 obsolete/
        assert not (ws / "docs" / "adr" / "0001-old.md").exists()
        old_text = (ws / "docs" / "adr" / "obsolete" / "0001-old.md").read_text(encoding="utf-8")
        assert "Status: Superseded" in old_text
        assert "superseded_by: ADR-0002" in old_text
        # adrs_all_accepted 应该跳过（obsolete/ 不在扫描范围）
        assert adr_gate.adrs_all_accepted(ws) is None


def test_reconcile_supersedes_idempotent():
    """已标记 Superseded 且在 obsolete/ 的不再修复。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {
            "0002-new.md": "---\nStatus: Accepted\nSupersedes: ADR-0001\nLanded-by: docs/specs/x/spec.md\n---\n# ADR-0002\n",
        })
        # 手动把旧 ADR 放进 obsolete/（模拟已完成）
        obs = ws / "docs" / "adr" / "obsolete"
        obs.mkdir(parents=True)
        (obs / "0001-old.md").write_text(
            "---\nStatus: Superseded\nSupersedes: -\nsuperseded_by: ADR-0002\n---\n# ADR-0001\n",
            encoding="utf-8",
        )
        assert adr_gate.reconcile_supersedes(ws) is None


def test_reconcile_supersedes_missing_target():
    """Supersedes 指向不存在的 ADR → 报错。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {
            "0002-new.md": "---\nStatus: Accepted\nSupersedes: ADR-0099\nLanded-by: docs/specs/x/spec.md\n---\n# ADR-0002\n",
        })
        result = adr_gate.reconcile_supersedes(ws)
        assert result is not None
        assert "SEAL REJECTED" in result
        assert "ADR-0099" in result


def test_rejected_auto_archived():
    """Status: Rejected 自动移入 obsolete/。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {
            "0003-bad-idea.md": "---\nStatus: Rejected\n---\n# ADR-0003\n",
        })
        result = adr_gate.reconcile_supersedes(ws)
        assert result is not None
        assert "ADR RECONCILED" in result
        assert "Rejected" in result
        assert not (ws / "docs" / "adr" / "0003-bad-idea.md").exists()
        assert (ws / "docs" / "adr" / "obsolete" / "0003-bad-idea.md").is_file()
        # Rejected 移走后不再阻断
        assert adr_gate.adrs_all_accepted(ws) is None


def test_rejected_idempotent():
    """已在 obsolete/ 的 Rejected 不再重复移。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {})
        obs = ws / "docs" / "adr" / "obsolete"
        obs.mkdir(parents=True)
        (obs / "0003-bad.md").write_text("---\nStatus: Rejected\n---\n# ADR-0003\n", encoding="utf-8")
        assert adr_gate.reconcile_supersedes(ws) is None


def test_landing_pointer_must_stay_in_workspace_and_be_file():
    """落地指针越出 workspace（绝对路径 / `..`）或指向目录都不算落地（ocr-033）。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {})
        assert adr_gate._pointer_resolves(ws, "docs/specs/x/spec.md") is True
        assert adr_gate._pointer_resolves(ws, "docs/specs/x") is False        # 目录不算
        assert adr_gate._pointer_resolves(ws, "/etc") is False                # 绝对路径越界
        assert adr_gate._pointer_resolves(ws, "../../etc/hosts") is False     # `..` 越界


def test_supersedes_self_is_refused():
    """`Supersedes` 指向自身必须拒（否则把生效决策自己归档，ocr-035）。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {"0001-a.md": "---\nStatus: Accepted\nSupersedes: ADR-0001\n---\n# ADR-0001\n"})
        out = adr_gate.reconcile_supersedes(ws)
        assert out and "自身" in out
        assert (ws / "docs" / "adr" / "0001-a.md").is_file()


def test_amend_format_missing_schema_fail_closed():
    """`.schema.json` 缺失 ⇒ seal 前置 `adr_amend_format` 必须红（不能静默全绿，ocr-194）。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {"0001-a.md": "---\nStatus: Accepted\n---\n# ADR-0001\n"})
        out = adr_gate.amend_format(ws)
        assert out and ".schema.json 缺失" in out


def test_amend_format_corrupt_schema_fail_closed():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {"0001-a.md": "---\nStatus: Accepted\n---\n# ADR-0001\n"})
        (ws / "docs" / "adr" / ".schema.json").write_text("{ broken", encoding="utf-8")
        out = adr_gate.amend_format(ws)
        assert out and "不可读/损坏" in out


def test_is_superseded_needs_the_actual_field_line() -> None:
    """正文提到 `superseded_by:`/`ADR-0026` 不算已标记（子串判据的假幂等，ocr-390）。"""
    from k3dge.engine.adr_gate import _is_superseded

    body = ("---\nStatus: Superseded\n---\n\n# ADR-0009 x\n\n"
            "讨论里写过 superseded_by: 与 ADR-0026 的引用，但 frontmatter 没有该字段\n")
    assert not _is_superseded(body, "0026")
    assert _is_superseded("---\nStatus: Superseded\nsuperseded_by: ADR-0026\n---\n", "26")


def test_mark_superseded_refuses_when_no_status_line() -> None:
    """没有规范 `Status:` 行 ⇒ 返回 None，调用方必须拒（旧实现照样归档并宣告"已 Superseded"，391）。"""
    from k3dge.engine.adr_gate import _mark_superseded

    assert _mark_superseded("# ADR-0009 x\n\n正文\n", "0026") is None
    out = _mark_superseded("---\nStatus: Accepted\n---\n\n# ADR-0009\n", "0026")
    assert out is not None and "Status: Superseded" in out and "superseded_by: ADR-0026" in out
