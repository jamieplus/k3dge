"""封版 ADR 硬闸：全 Accepted + 可解析落地指针。"""
import os
import sys
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
        out = adr_gate.adrs_all_accepted(ws) or ""
        assert "未 Accepted" in out
        # ocr2-713 同款：只钉汇总头时"错件归因"也绿——明细必须点名具体文件与状态
        assert "0001-a.md" in out and "Draft" in out, out


def test_missing_or_bad_pointer_blocks():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {"0001-a.md": "---\nStatus: Accepted\n---\n# ADR-0001\n"})
        out = adr_gate.adr_landed(ws) or ""
        assert "缺可解析落地指针" in out
        # ocr2-713：汇总头对 bad 列表任何原因都出现——"缺 Landed-by"错分类成
        # "指针不可解析"（或反之）时本行照绿。把逐件明细一起钉住。
        assert "0001-a.md(缺 Landed-by)" in out, out
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {"0001-a.md": "---\nStatus: Accepted\nLanded-by: docs/nope.md\n---\n# ADR-0001\n"})
        out2 = adr_gate.adr_landed(ws) or ""
        assert "指针不可解析" in out2
        assert "0001-a.md->docs/nope.md(指针不可解析)" in out2, out2


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
        # ocr2-420 真 round-trip：写入器自己的输出必须被识别器认出，否则每轮重写。
        from k3dge.engine.adr_gate import _is_superseded
        assert _is_superseded(old_text, "0002"), old_text
        assert adr_gate.reconcile_supersedes(ws) is None
        # adrs_all_accepted 应该跳过（obsolete/ 不在扫描范围）
        assert adr_gate.adrs_all_accepted(ws) is None
        # ocr2-419：归档件是 Superseded（白名单内）⇒ 上行在 `_adr_files` 退化成
        # rglob 时照样绿。`Rejected` 不在白名单 ⇒ 用它当真判别需要时补在下面；
        # 这里钉 `adr_landed` 判别：归档件不参与落地闸（0002 指针有效 ⇒ 全过）。
        assert adr_gate.adr_landed(ws) is None
        # 结构直钉：扫描面只有活跃目录顶层，obsolete/ 永远不可见（rglob 退化即红）。
        assert [p.name for p in adr_gate._adr_files(ws)] == ["0002-new.md"]


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
        # ocr2-419 真判别：Rejected 不在白名单 ⇒ 扫描面一旦把 obsolete/ 扫进来这里即红。
        assert adr_gate.adrs_all_accepted(ws) is None


def test_landing_pointer_must_stay_in_workspace_and_be_file():
    """落地指针越出 workspace（绝对路径 / `..`）或指向目录都不算落地（ocr-033）。

    旧测的越界靶（`/etc`、`../../etc/hosts`）都**不是文件**⇒ containment 检查删掉照样绿
    （t-061）。这里造一个**真实存在**的 workspace 外文件：`is_file()` 会真，
    只有 containment 拦得住。
    """
    with tempfile.TemporaryDirectory() as d:
        outer = Path(d)
        ws = _ws(outer / "ws", {})               # ws 嵌一层：让 outside 成为**真兄弟**（在 ws 外）
        outside = outer / "outside.md"           # tmp 根的兄弟件：在 ws 外、确实是文件
        outside.write_text("# outside landing\n", encoding="utf-8")
        assert adr_gate._pointer_resolves(ws, "docs/specs/x/spec.md") is True
        assert adr_gate._pointer_resolves(ws, "docs/specs/x") is False        # 目录不算
        assert outside.is_file()
        assert adr_gate._pointer_resolves(ws, str(outside)) is False          # 绝对越界（is_file 真）
        rel = os.path.relpath(outside, ws)                                    # ../outside.md
        assert rel.startswith("..") and adr_gate._pointer_resolves(ws, rel) is False
        # ocr2-714：下面两行是 POSIX-only——Windows 上 `/etc` 本来就不是文件，
        # "不解析"与"被 containment 拦"同脸；跨盘符时 relpath 还会抛 ValueError。
        # containment 的真判据是上面两行（ws 外真文件 + is_file 真而仍拒）。
        if sys.platform != "win32":
            assert adr_gate._pointer_resolves(ws, "/etc") is False
            assert adr_gate._pointer_resolves(ws, "../../etc/hosts") is False


def test_landed_end_to_end_rejects_outside_workspace_pointer():
    """helper 绿不等于闸绿：`Landed-by: <ws 外真实文件>` 必须让 adr_landed 拒（t-061 端到端面）。"""
    with tempfile.TemporaryDirectory() as d:
        outside = Path(d) / "outside.md"
        outside.write_text("# outside\n", encoding="utf-8")
        ws = _ws(Path(d) / "ws", {
            "0001-a.md": f"---\nStatus: Accepted\nLanded-by: {outside}\n---\n# ADR-0001\n",
        })
        out = adr_gate.adr_landed(ws)
        assert out and "指针不可解析" in out


def test_reconcile_validates_all_before_touching_disk():
    """两遍结构的行为面（t-063）：坏声明必须**全部**拦在动盘之前。

    只测单条声明＝融合"校验+动盘"也照样绿——前半合法声明先落盘、后半坏声明才拒，
    工作区停在"部分生效"。两个晚发现型失败各测一条：缺目标（声明相）与
    目标无规范 Status 行（原实现要到**写相**才撞上）。
    """
    # ① 0002 合法取代 0001 + 0003 指向不存在的 ADR-0099 ⇒ 整轮拒，0001 未动
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {
            "0001-old.md": "---\nStatus: Accepted\nSupersedes: -\n---\n# ADR-0001\n",
            "0002-new.md": "---\nStatus: Accepted\nSupersedes: ADR-0001\nLanded-by: docs/specs/x/spec.md\n---\n# ADR-0002\n",
            "0003-x.md": "---\nStatus: Accepted\nSupersedes: ADR-0099\nLanded-by: docs/specs/x/spec.md\n---\n# ADR-0003\n",
        })
        orig = {(ws / "docs" / "adr" / n).read_text(encoding="utf-8") for n in
                ("0001-old.md", "0002-new.md", "0003-x.md")}
        out = adr_gate.reconcile_supersedes(ws)
        assert out and "SEAL REJECTED" in out and "ADR-0099" in out
        assert (ws / "docs" / "adr" / "0001-old.md").is_file(), "部分生效：0001 已先被归档"
        assert not (ws / "docs" / "adr" / "obsolete").exists()
        # ocr2-421：只钉存在性抓不住"计划相就地改 0001 再拒"——原文逐字钉住 + 无 .tmp 残留。
        for n in ("0001-old.md", "0002-new.md", "0003-x.md"):
            assert (ws / "docs" / "adr" / n).read_text(encoding="utf-8") in orig, f"{n} 被部分改写"
        assert list((ws / "docs" / "adr").glob("*.tmp")) == []
    # ② 0002 合法 + 0004 的目标 0005 没有可改 Status 行 ⇒ 同样先拒后动
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {
            "0001-old.md": "---\nStatus: Accepted\nSupersedes: -\n---\n# ADR-0001\n",
            "0002-new.md": "---\nStatus: Accepted\nSupersedes: ADR-0001\nLanded-by: docs/specs/x/spec.md\n---\n# ADR-0002\n",
            "0004-y.md": "---\nStatus: Accepted\nSupersedes: ADR-0005\nLanded-by: docs/specs/x/spec.md\n---\n# ADR-0004\n",
            "0005-bad.md": "# ADR-0005 没有 frontmatter\n",
        })
        orig2 = {n: (ws / "docs" / "adr" / n).read_text(encoding="utf-8") for n in
                 ("0001-old.md", "0002-new.md", "0004-y.md", "0005-bad.md")}
        out = adr_gate.reconcile_supersedes(ws)
        assert out and "SEAL REJECTED" in out and "0005-bad.md" in out
        assert (ws / "docs" / "adr" / "0001-old.md").is_file(), "部分生效：0001 已先被归档"
        assert not (ws / "docs" / "adr" / "obsolete").exists()
        # ocr2-421 同款：逐字钉住原文 + 无 .tmp 残留。
        for n, body in orig2.items():
            assert (ws / "docs" / "adr" / n).read_text(encoding="utf-8") == body, f"{n} 被部分改写"
        assert list((ws / "docs" / "adr").glob("*.tmp")) == []


def test_supersede_refuses_to_overwrite_archived_source():
    """撞名守卫（ocr-193）此前**零覆盖**（t-064）：obsolete/ 已有同名件时拒、不覆盖。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {
            "0001-old.md": "---\nStatus: Accepted\nSupersedes: -\n---\n# ADR-0001 活跃件\n",
            "0002-new.md": "---\nStatus: Accepted\nSupersedes: ADR-0001\nLanded-by: docs/specs/x/spec.md\n---\n# ADR-0002\n",
        })
        obs = ws / "docs" / "adr" / "obsolete"
        obs.mkdir(parents=True)
        (obs / "0001-old.md").write_text("---\nStatus: Accepted\n---\n# 归档事实源（别毁）\n",
                                         encoding="utf-8")
        out = adr_gate.reconcile_supersedes(ws)
        assert out and "拒绝覆盖归档事实源" in out
        assert "别毁" in (obs / "0001-old.md").read_text(encoding="utf-8")
        assert (ws / "docs" / "adr" / "0001-old.md").is_file()


def test_rejected_archival_refuses_to_overwrite_archived_name():
    """Rejected 分支以前裸 `write_text` 直写，同名归档件被静默销毁（t-064 的不对称）。

    修后与 Supersedes 同规则：撞名 ⇒ 拒，活件与归档件都原样留着。
    """
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {"0003-bad.md": "---\nStatus: Rejected\n---\n# 活体\n"})
        obs = ws / "docs" / "adr" / "obsolete"
        obs.mkdir(parents=True)
        (obs / "0003-bad.md").write_text("---\nStatus: Rejected\n---\n# 归档事实源（别毁）\n",
                                         encoding="utf-8")
        out = adr_gate.reconcile_supersedes(ws)
        assert out and "拒绝覆盖归档事实源" in out
        assert "别毁" in (obs / "0003-bad.md").read_text(encoding="utf-8")
        assert (ws / "docs" / "adr" / "0003-bad.md").is_file()


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


def test_amend_format_non_object_schema_fail_closed():
    """ocr2-715：ocr-194 的 fail-closed 承诺是三条支路（缺失/损坏/顶层非对象），
    这里此前只钉两条——`isinstance(schema, dict)` 守卫在全树零覆盖。删掉它 ⇒
    顶层 `[...]`/`"..."` 时 `schema.get` 抛 AttributeError 打碎 seal 预审；
    改成 `return None` ⇒ 静默全绿。两种退化本测都拦。
    """
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {"0001-a.md": "---\nStatus: Accepted\n---\n# ADR-0001\n"})
        for bad in ("[1, 2]", '"just a string"'):
            (ws / "docs" / "adr" / ".schema.json").write_text(bad, encoding="utf-8")
            out = adr_gate.amend_format(ws)
            assert out and "顶层不是对象" in out, (bad, out)  # 结构化拒，不抛裸 AttributeError


def test_is_superseded_needs_the_actual_field_line() -> None:
    """正文提到 `superseded_by:`/`ADR-0026` 不算已标记（子串判据的假幂等，ocr-390）。"""
    from k3dge.engine.adr_gate import _is_superseded

    body = ("---\nStatus: Superseded\n---\n\n# ADR-0009 x\n\n"
            "讨论里写过 superseded_by: 与 ADR-0026 的引用，但 frontmatter 没有该字段\n")
    assert not _is_superseded(body, "0026")
    assert _is_superseded("---\nStatus: Superseded\nsuperseded_by: ADR-0026\n---\n", "26")


def test_is_superseded_field_line_must_live_in_frontmatter() -> None:
    """行锚定不等于归属：正文里**顶格**的示例行 `superseded_by: ADR-0026` 恰好吃中旧判据
    （t-062）⇒ 假"已标记"、reconcile 幂等早退、真字段永不写入——正是 ocr-390 那一类。
    同族的还有正文顶格 `Status: Rejected` 示例行（会把活件归档掉）⇒ 一并圈进 frontmatter。
    """
    from k3dge.engine.adr_gate import _is_superseded, _status

    prose = ("---\nStatus: Superseded\n---\n\n# ADR-0009\n\n"
             "文档示例（顶格、独立成行，与真字段一字不差）：\n\n"
             "superseded_by: ADR-0026\n")
    assert not _is_superseded(prose, "0026")
    assert _is_superseded("---\nStatus: Superseded\nsuperseded_by: ADR-0026\n---\n", "26")
    assert _status("---\nStatus: Accepted\n---\n\n# 例\n\nStatus: Rejected\n") == "Accepted"


def test_rejected_example_line_in_body_does_not_archive_live_adr() -> None:
    """端到端：`Status: Rejected` 只出现在正文示例 ⇒ 不得被收进 obsolete（t-062 同族）。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {
            "0006-doc.md": ("---\nStatus: Accepted\nLanded-by: docs/specs/x/spec.md\n---\n"
                            "# ADR-0006\n\n反例长这样（顶格）：\n\nStatus: Rejected\n"),
        })
        assert adr_gate.reconcile_supersedes(ws) is None
        assert (ws / "docs" / "adr" / "0006-doc.md").is_file()
        assert not (ws / "docs" / "adr" / "obsolete").exists()


def test_mark_superseded_refuses_when_no_status_line() -> None:
    """没有规范 `Status:` 行 ⇒ 返回 None，调用方必须拒（旧实现照样归档并宣告"已 Superseded"，391）。"""
    from k3dge.engine.adr_gate import _mark_superseded

    assert _mark_superseded("# ADR-0009 x\n\n正文\n", "0026") is None
    out = _mark_superseded("---\nStatus: Accepted\n---\n\n# ADR-0009\n", "0026")
    assert out is not None and "Status: Superseded" in out and "superseded_by: ADR-0026" in out


def test_body_only_supersedes_does_not_trigger_reconcile() -> None:
    """正文顶格的 `Supersedes:` 示例行不得触发破坏性 reconcile（ocr2-001）。

    `Supersedes:` 只在 frontmatter 内成立；全文搜会把正文引用当声明，把被引 ADR 归档。
    """
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {
            "0001-old.md": "---\nStatus: Accepted\nSupersedes: -\n---\n# ADR-0001\n",
            "0002-new.md": ("---\nStatus: Accepted\nSupersedes: -\nLanded-by: docs/specs/x/spec.md\n---\n"
                            "# ADR-0002\n\n例如：Supersedes: ADR-0001\n"),
        })
        assert adr_gate.reconcile_supersedes(ws) is None
        assert (ws / "docs" / "adr" / "0001-old.md").is_file()
        assert not (ws / "docs" / "adr" / "obsolete").exists()


def test_body_only_landed_by_does_not_pass() -> None:
    """正文顶格的 `Landed-by:` 示例行不得让缺指针 ADR 过闸（ocr2-029，与 ocr2-001 同族）。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {
            "0001-a.md": ("---\nStatus: Accepted\n---\n# ADR-0001\n\n"
                          "例如：Landed-by: docs/specs/x/spec.md\n"),
        })
        bad = adr_gate.adr_landed(ws)
        assert bad is not None and "缺 Landed-by" in bad


def test_duplicate_supersede_target_is_rejected_not_crashed() -> None:
    """两处声明撞同一目标 ⇒ 拒（写相无法移动两次），不能崩/覆写（ocr2-030）。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {
            "0001-old.md": "---\nStatus: Accepted\nSupersedes: -\n---\n# ADR-0001\n",
            "0002-a.md": "---\nStatus: Accepted\nSupersedes: ADR-0001\nLanded-by: docs/specs/x/spec.md\n---\n# ADR-0002\n",
            "0003-b.md": "---\nStatus: Accepted\nSupersedes: ADR-0001\nLanded-by: docs/specs/x/spec.md\n---\n# ADR-0003\n",
        })
        r = adr_gate.reconcile_supersedes(ws)
        assert r is not None and "同时 Supersede" in r
        assert (ws / "docs" / "adr" / "0001-old.md").is_file()


def test_mark_superseded_updates_existing_provenance() -> None:
    """已有 `superseded_by:` 时更新为本次取代方，不留旧值（ocr2-031）。"""
    from k3dge.engine.adr_gate import _mark_superseded

    out = _mark_superseded("---\nStatus: Accepted\nsuperseded_by: ADR-0001\n---\n# X\n", "0002")
    assert out is not None and "superseded_by: ADR-0002" in out and "ADR-0001" not in out


def test_reconcile_rejects_unreadable_target_fail_closed(monkeypatch) -> None:
    """ocr2-181：Supersedes 目标不可读 ⇒ 硬闸 fail-closed，不得静默跳过或移动。"""
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {
            "0001-old.md": "---\nStatus: Accepted\nSupersedes: -\n---\n# ADR-0001\n",
            "0002-new.md": ("---\nStatus: Accepted\nSupersedes: ADR-0001\n"
                            "Landed-by: docs/specs/x/spec.md\n---\n# ADR-0002\n"),
        })
        target = ws / "docs" / "adr" / "0001-old.md"
        real = Path.read_text

        def fake_read(self, *a, **k):
            if self == target:
                raise OSError("permission denied")
            return real(self, *a, **k)

        monkeypatch.setattr(Path, "read_text", fake_read)
        out = adr_gate.reconcile_supersedes(ws)
        assert out is not None and "SEAL REJECTED" in out and "不可读" in out, out
        assert target.is_file(), "不可读 target 不得被移走/归档"
        assert not (ws / "docs" / "adr" / "obsolete").exists()
