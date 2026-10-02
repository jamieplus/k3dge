"""消费侧**独立验收**（`engine/audit_verify`）：报告完备性 + 本地闭环 + 内容哈希链。

判据是"**k3dge 自己从包的文件夹里算**"，不调产出方——所以这些用例全部用**合成包**，
并且刻意做出各类**不合格**的包（缺行、必需格空、表头顺序错、ID 重复、状态自报与事实不符、内容被篡改）。
"""

import difflib
import hashlib
import json
from pathlib import Path

from k3dge.engine import audit_verify as av

_PRE = "x = 1\ny = 2\n"
_PIN_LINE = "# k3dit:fixed code-1 复核通过\n"
_OLD_PIN = "# k3dit:leftover old-1 上一轮留的钉\n"
_HEADER = ("| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")


def _patch(a: str, b: str, rel: str = "src/a.py") -> str:
    """真生成 unified diff（手写补丁的上下文常常不自洽 ⇒ 夹具必须真算）。"""
    return "".join(difflib.unified_diff(a.splitlines(keepends=True), b.splitlines(keepends=True),
                                        fromfile=f"a/{rel}", tofile=f"b/{rel}"))


def make_bundle(root: Path, *, version: int = 1, claimed: str = "closed", row_state: str = "已修",
                verify_cell: str = "验证：跑通 tests/unit/x.py", dup: bool = False,
                drop_row: bool = False, header_swapped: bool = False, tamper: bool = False,
                finding_state: str = "fixed", review_ack: bool = True,
                disposition: str = "已改：加了 added_by_fix",
                input_path: str = "/tmp/ws", order=("fix.patch", "pins.patch"),
                preexisting_pin: bool = False, pins_in_code: bool = True) -> Path:
    """造一个**结构完整**的包：`code/` + `baseline.json` + 12 列表格 + 真生成的补丁。

    `preexisting_pin` ⇒ 输入树里本来就有一枚钉（baseline 存**去钉语义层** ⇒ 重放后要能对上）。
    `pins_in_code=False` ⇒ artifact 形态：`code/` 已是去钉语义层，钉只在 `pins.patch` 里。
    """
    b = root / "bundle"
    (b / "code" / "src").mkdir(parents=True, exist_ok=True)
    pre = (_OLD_PIN if preexisting_pin else "") + _PRE
    mid = pre + "added_by_fix = True\n"
    post = (_OLD_PIN if preexisting_pin else "") + _PIN_LINE + _PRE + "added_by_fix = True\n"
    (b / "fix.patch").write_text(_patch(pre, mid), encoding="utf-8")
    (b / "pins.patch").write_text(_patch(mid, post), encoding="utf-8")
    code_text = post if pins_in_code else mid
    if tamper:      # 在（含钉的）文件里追加一行代码 ⇒ 必须被哈希链抓住
        code_text += "tampered = True\n"
    (b / "code" / "src" / "a.py").write_text(code_text, encoding="utf-8")
    # 摘要算法随包版本（与 k3dit pack._ALGO_BY_VERSION / k3dge _ALGO_BY_VERSION 同表）
    digest = (hashlib.sha1 if version == 1 else hashlib.sha256)(_PRE.encode()).hexdigest()
    (b / "baseline.json").write_text(json.dumps({
        "files": {"src/a.py": digest},
        "tree_hash": "x", "count": 1}, ensure_ascii=False), encoding="utf-8")
    (b / "findings.json").write_text(json.dumps({"items": [
        {"id": "code-1", "state": finding_state, "review_ack": review_ack,
         "location": "src/a.py:1",          # 真包含 location（部分落地要靠它把未关项所在文件排除）
         "disposition": disposition, "verification": "跑通 tests/unit/x.py"}]},
        ensure_ascii=False), encoding="utf-8")
    hdr = _HEADER
    if header_swapped:      # 表头顺序错（消费侧判据必须按序）
        hdr = ("| ID | 优先级 | 严重度 | 日期 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
               "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
    row = ("| code-1 | 2026-09-27 | 中 | P1 | 正确性 | 说明 | src/a.py:1 | "
           f"{row_state} | {disposition} | {verify_cell} | | |\n")
    rows = "" if drop_row else (row + (row if dup else ""))
    (b / "report.md").write_text("# 审计\n\n" + hdr + rows, encoding="utf-8")
    (b / "manifest.json").write_text(json.dumps({
        "bundle_version": version, "status": claimed, "unclosed": 0 if claimed == "closed" else 1,
        "apply_order": list(order), "input": input_path, "mode": "full", "job_id": "j1",
        "pins": {"count": 1, "by_state": {"fixed": 1}, "in_code": pins_in_code},
        "flow": {"windows": {"fix": 2, "review": 1}, "rework_ratio": 1.0}, "coverage": {"audited_files": 1},
    }, ensure_ascii=False), encoding="utf-8")
    return b


def _errors(res) -> str:
    return " | ".join(res.get("errors") or [])


def test_valid_bundle_passes_local_verification(tmp_path):
    res = av.verify_bundle_local(make_bundle(tmp_path), expect_input="/tmp/ws")
    assert res["ok"], _errors(res)
    assert res["report_rows"] == 1 and res["unclosed"] == [] and res["hash"]["checked"] == 1
    assert res["cross_check"]["agree"] is True


def test_report_must_match_findings_one_to_one(tmp_path):
    res = av.verify_bundle_local(make_bundle(tmp_path, drop_row=True))
    assert not res["ok"] and "报告漏行" in _errors(res), _errors(res)
    res2 = av.verify_bundle_local(make_bundle(tmp_path / "d", dup=True))
    assert not res2["ok"] and "重复 ID" in _errors(res2), _errors(res2)
    b = make_bundle(tmp_path / "e")          # 报告多一行（findings 里没有）也算不完备
    (b / "report.md").write_text(
        "# 审计\n\n" + _HEADER + "| code-9 | 2026-09-27 | 低 | P3 | 规范 | 幽灵 | x:1 | 已修 | 处置 | 验证 | | |\n",
        encoding="utf-8")
    res3 = av.verify_bundle_local(b)
    assert not res3["ok"] and "报告多行" in _errors(res3), _errors(res3)


def test_fixed_row_requires_disposition_and_verification(tmp_path):
    """名字承诺两列、此前只钉了「验证」半（t-093）。现在两列各断一次——
    「处置」空走 REQUIRED_CELLS 的「必需列 `处置` 为空」，与「验证」列是两条独立护栏。"""
    res = av.verify_bundle_local(make_bundle(tmp_path, verify_cell=""))
    assert not res["ok"] and "「验证」列为空" in _errors(res), _errors(res)
    res2 = av.verify_bundle_local(make_bundle(tmp_path / "d", disposition=""))
    assert not res2["ok"] and "`处置` 为空" in _errors(res2), _errors(res2)


def test_report_header_must_be_the_exact_12_columns(tmp_path):
    res = av.verify_bundle_local(make_bundle(tmp_path, header_swapped=True))
    assert not res["ok"] and "12 列" in _errors(res), _errors(res)


def test_closure_is_computed_locally_and_disagreement_is_reported(tmp_path):
    """产出方自报 `closed` 但 findings 里还有未关项 ⇒ **报出来**（以本地算的为准）。"""
    res = av.verify_bundle_local(make_bundle(tmp_path, claimed="closed", finding_state="pending",
                                             row_state="待修"), require_closed=True)
    assert not res["ok"] and "闭环事实不一致" in _errors(res) and "未闭环（消费侧算）" in _errors(res)
    assert res["unclosed"] == ["code-1"]
    ok = av.verify_bundle_local(make_bundle(tmp_path / "p", claimed="partial", finding_state="pending",
                                            row_state="待修"), require_closed=False)
    assert ok["ok"] and ok["cross_check"]["agree"] is True, _errors(ok)     # 纯审计不要求闭环


def test_hash_chain_uses_contract_grammar_and_catches_tampering(tmp_path):
    """哈希链＝**去钉后**逐文件比（语法单源＝`engine/markers`）——含钉文件**不豁免**。

    先前的写法把"被 pins.patch 碰过的文件"整份跳过 ⇒ 在那类文件里**追加任何代码都抓不到**（真漏洞）。
    现在用契约 §8 的规范正则去钉后再比：既容得下"上一轮留下的钉"，也抓得到同一文件里的篡改。
    """
    ok = av.verify_bundle_local(make_bundle(tmp_path / "pin", preexisting_pin=True))
    assert ok["ok"], _errors(ok)
    assert ok["hash"]["checked"] == 1 and ok["hash"]["files_with_markers"] == ["src/a.py"]
    res = av.verify_bundle_local(make_bundle(tmp_path, tamper=True))      # 含钉文件里追加代码
    assert not res["ok"] and "内容哈希链不通过" in _errors(res), _errors(res)
    # artifact 形态（`pins.in_code=false`）：`code/` 已是语义层 ⇒ **不反向** pins.patch（只反向 fix.patch）
    art = av.verify_bundle_local(make_bundle(tmp_path / "art", pins_in_code=False))
    assert art["ok"], _errors(art)
    # **组合形状**（t-094）：既有钉 + 篡改——旧 bug 正是"被 pins.patch 碰过的文件整份跳过"，
    # 于是这类文件里追加的代码永远抓不到。先 `preexisting_pin` 让钉能挺过两遍反向应用，
    # 再 tamper 加一行代码：strip_markers 仍容忍旧钉，但**必须**抓到多出来的代码。
    combo = av.verify_bundle_local(make_bundle(tmp_path / "combo", preexisting_pin=True, tamper=True))
    assert not combo["ok"] and "内容哈希链不通过" in _errors(combo), _errors(combo)


def test_hash_chain_accepts_raw_baseline_when_no_final_newline(tmp_path):
    """产出方 `baseline.json` 是**原始字节**摘要：无尾换行、且**未被任何补丁触及**的文件
    不能被 `strip_markers` 补的 `\n` 多出一个字节而误判（真跑 M11：10 文件
    `raw==baseline` 仍被判"哈希链不通过"）。补丁不碰它 ⇒ 重放树原样带出，纯比摘要。
    """
    extra, rel = "no trailing newline", "src/b.txt"
    b = make_bundle(tmp_path, version=2)
    (b / "code" / rel).write_text(extra, encoding="utf-8")
    bl = json.loads((b / "baseline.json").read_text(encoding="utf-8"))
    bl["files"][rel] = hashlib.sha256(extra.encode()).hexdigest()
    (b / "baseline.json").write_text(json.dumps(bl, ensure_ascii=False), encoding="utf-8")
    ok = av.verify_bundle_local(b)
    assert ok["ok"], _errors(ok)
    assert ok["hash"]["checked"] == 2
    # 对照：篡改这份无尾换行文件 ⇒ raw 与 sem 都变，仍必须红。
    (b / "code" / rel).write_text(extra + "\ntampered = 1", encoding="utf-8")
    bad = av.verify_bundle_local(b)
    assert not bad["ok"] and "内容哈希链不通过" in _errors(bad), _errors(bad)


def test_v2_bundle_is_dual_read_with_sha256(tmp_path):
    """pack v2（SHA-256）双读：布局不变、算法随版本（k3dit ocr-220 的消费侧另一半）。"""
    res = av.verify_bundle_local(make_bundle(tmp_path, version=2))
    assert res["ok"], _errors(res)


def test_v2_bundle_rejects_sha1_digest(tmp_path):
    """算法不许**猜**：v2 包里塞 sha1 摘要＝哈希链必须不通过（用错算法比不算更糟——
    能把篡改洗成"通过"）。旧的单算法实现测不出这条分叉。"""
    b = make_bundle(tmp_path, version=2)
    bl = json.loads((b / "baseline.json").read_text(encoding="utf-8"))
    bl["files"]["src/a.py"] = hashlib.sha1(_PRE.encode()).hexdigest()
    (b / "baseline.json").write_text(json.dumps(bl, ensure_ascii=False), encoding="utf-8")
    res = av.verify_bundle_local(b)
    assert not res["ok"] and "哈希链" in _errors(res), _errors(res)


def test_unknown_bundle_version_does_not_guess_algo(tmp_path):
    """白名单外的版本：哈希链显式"不可核"，不拿任何算法硬算。"""
    b = make_bundle(tmp_path, version=3)
    bl = json.loads((b / "baseline.json").read_text(encoding="utf-8"))
    bl["files"]["src/a.py"] = hashlib.sha256(_PRE.encode()).hexdigest()
    (b / "baseline.json").write_text(json.dumps(bl, ensure_ascii=False), encoding="utf-8")
    res = av.verify_bundle_local(b)
    assert not res["ok"]
    assert "bundle_version" in _errors(res) and "不可核" in _errors(res), _errors(res)


def test_version_and_input_identity_are_gated(tmp_path):
    res = av.verify_bundle_local(make_bundle(tmp_path, version=999))
    assert not res["ok"] and "bundle_version" in _errors(res)
    res2 = av.verify_bundle_local(make_bundle(tmp_path / "i"), expect_input="/tmp/OTHER")
    assert not res2["ok"] and "输入身份不符" in _errors(res2), _errors(res2)


def test_input_identity_is_read_from_the_bundle_not_a_constant(tmp_path):
    """用**非缺省** `input_path` 验身份比对（t-092：该旋钮此前恒为 `/tmp/ws`）。

    若实现把期望值写死、或干脆不读 `facts["input"]`，"喂不同 input 应红"这条永远测不到。
    正反两面：包 input 与 expect 一致 ⇒ 过；不一致 ⇒ `输入身份不符`。
    """
    b = make_bundle(tmp_path, input_path="/tmp/elsewhere")
    ok = av.verify_bundle_local(b, expect_input="/tmp/elsewhere")
    assert ok["ok"], _errors(ok)
    bad = av.verify_bundle_local(make_bundle(tmp_path / "x", input_path="/tmp/elsewhere"),
                                 expect_input="/tmp/ws")
    assert not bad["ok"] and "输入身份不符" in _errors(bad), _errors(bad)


def test_apply_order_unknown_patch_rejected(tmp_path):
    """`apply_order` 含未知/越界补丁名（t-092：`order` 旋钮此前恒为默认对）。

    这条同时是 `replay_to_baseline` 的路径穿越闸——只认白名单补丁名。
    """
    res = av.verify_bundle_local(make_bundle(tmp_path, order=("fix.patch", "../evil.patch")))
    assert not res["ok"] and "未知补丁" in _errors(res), _errors(res)
    # 对照：**顺序是有语义的**（重放按声明序反向做）——换序不是"另一个合法值"，
    # 而是会让哈希链反向应用失败；这里只证"白名单外的名字被闸下"。
    ok = av.verify_bundle_local(make_bundle(tmp_path / "same", order=("fix.patch", "pins.patch")))
    assert ok["ok"], _errors(ok)


def test_terminal_state_without_review_ack_is_unclosed(tmp_path):
    """`review_ack` 旋钮此前恒 True ⇒ "终态但没背书＝未关"这条闭环判据从没测到（t-092）。"""
    res = av.verify_bundle_local(
        make_bundle(tmp_path, finding_state="fixed", review_ack=False, row_state="已修"),
        require_closed=True)
    assert not res["ok"] and "未闭环（消费侧算）" in _errors(res), _errors(res)
    assert res["unclosed"] == ["code-1"], res


def test_missing_files_and_empty_patch_fail_clear(tmp_path):
    b = make_bundle(tmp_path)
    (b / "report.md").unlink()
    res = av.verify_bundle_local(b)
    assert not res["ok"] and "必需文件缺失：report.md" in _errors(res)
    b2 = make_bundle(tmp_path / "o")
    (b2 / "pins.patch").write_text("", encoding="utf-8")
    res2 = av.verify_bundle_local(b2)
    assert not res2["ok"] and "缺失或为空" in _errors(res2), _errors(res2)


def test_baseline_drift_is_accepted_only_explicitly_and_off_patch_surface(tmp_path):
    """旧包的 `baseline` 语义层口径漂移（产出方旧 strip 规则）：**显式带理由**可接受，但硬条件两条——

    ① 给了理由；② 漂移文件**不被任何补丁触及**（补丁要落的地方必须逐字节自洽）。
    """
    b = make_bundle(tmp_path / "drift")
    (b / "code" / "src" / "a.py").write_text(
        (b / "code" / "src" / "a.py").read_text(encoding="utf-8") + "drifted = True\n", encoding="utf-8")
    assert not av.verify_bundle_local(b)["ok"]                       # 默认拒
    # 漂移文件恰是**补丁触及**的（src/a.py）⇒ 给了理由也不接受
    r = av.verify_bundle_local(b, accept_baseline_drift="旧 strip 规则")
    assert not r["ok"] and "不接受" in " ".join(r["errors"]), r
    # 漂移落在**没被补丁触及**的文件上 ⇒ 显式理由可接受，且事实被记录
    b2 = make_bundle(tmp_path / "drift2")
    (b2 / "code" / "docs").mkdir(parents=True, exist_ok=True)
    (b2 / "code" / "docs" / "x.md").write_text("x\n", encoding="utf-8")
    (b2 / "baseline.json").write_text(json.dumps({
        "files": {**json.loads((b2 / "baseline.json").read_text(encoding="utf-8"))["files"],
                  "docs/x.md": hashlib.sha1(b"old\n").hexdigest()}, "tree_hash": "x", "count": 2},
        ensure_ascii=False), encoding="utf-8")
    ok = av.verify_bundle_local(b2, accept_baseline_drift="产出方旧 strip 规则 ⇒ 文档面语义层漂移")
    assert ok["ok"] and ok["accepted_drift"] == ["docs/x.md"], ok


def test_checklist_counts_escalations_as_pending(tmp_path):
    """升级标记（报告**验证**列）必须计入 `pending`：否则封板前置闸会**虚报已审**。

    用户裁定：未关项不改"状态"列（保持产出方原样），升级由 k3dge 的审后闸报出 ⇒ 所以 k3dge 必须自己数。
    """
    from k3dge.engine import audit_checklist
    from k3dge.engine.audit_bundle import ESCALATION_NOTLANDED, ESCALATION_UNCLOSED

    ws = tmp_path
    (ws / ".agent").mkdir(parents=True, exist_ok=True)
    (ws / "docs" / "reviews").mkdir(parents=True, exist_ok=True)
    (ws / "docs" / "reviews" / "2026-09-27-M1-external-audit.md").write_text(
        "# 审计\n\n| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        f"| a-1 | 2026-09-27 | 中 | P1 | 正确性 | x | src/a.py:1 | 已修 | 改了 | {ESCALATION_UNCLOSED} | | |\n"
        f"| a-2 | 2026-09-27 | 中 | P1 | 正确性 | y | src/b.py:2 | 已修 | 改了 | {ESCALATION_NOTLANDED}（`--exclude`）待人工 | | |\n"
        "| a-3 | 2026-09-27 | 低 | P3 | 规范 | z | src/c.py:3 | 已修 | 改了 | 验了 | | |\n",
        encoding="utf-8")
    data = audit_checklist.build_checklist(ws, "M1")
    assert data["closure"]["audit"]["escalated"] == 2, data["closure"]
    assert data["closure"]["audit"]["pending"] == 2, data["closure"]


def test_baseline_non_object_is_rejected(tmp_path):
    """`baseline.json` 合法 JSON 但非对象 ⇒ 哈希链不可核，不抛 AttributeError（ocr2-048）。"""
    b = make_bundle(tmp_path)
    (b / "baseline.json").write_text('["not", "an", "object"]', encoding="utf-8")
    res = av.verify_bundle_local(b)
    assert not res["ok"] and "不是对象" in _errors(res), _errors(res)


def test_duplicate_finding_ids_are_reported(tmp_path):
    """`findings.json` 重复 ID 不得静默折叠（ocr2-049）：后条覆盖前条 ⇒ 必须报错。"""
    import json as _json

    b = make_bundle(tmp_path)
    items = _json.loads((b / "findings.json").read_text(encoding="utf-8"))
    items["items"] = items["items"] + [dict(items["items"][0])]
    (b / "findings.json").write_text(_json.dumps(items, ensure_ascii=False), encoding="utf-8")
    res = av.verify_bundle_local(b)
    assert not res["ok"] and "ID 重复" in _errors(res), _errors(res)
