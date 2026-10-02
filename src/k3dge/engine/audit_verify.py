"""消费侧**独立验收**（ADR-0012：产物 + 消费者 + 到达）——不把验收外包给产出方。

拿到交付包的第一步**不是**问产出方"你自证了吗"（那是自查），而是 k3dge 自己从包的**文件**里验：

1. **包完备性**：`bundle_version` 白名单、输入身份、`apply_order` 里的补丁存在且非空、必需文件齐；
2. **报告完备性**：12 列**精确**表头（顺序一致）、行与 `findings.json` **一一对应**（无缺/无多/无重）、
   每行必需格非空、状态 ∈ 闭集、`已修` 必有「处置 + 验证」；
3. **闭环由 k3dge 自己算**：未关＝`pending`/`fixnote`/`disputed` 或终态未背书（`review_ack` 假）
   —— 不读产出方自报的 `status`/`unclosed`（只作交叉核，不一致时**报出来**，以本地算的为准）；
4. **内容哈希链**：在临时副本上按 `apply_order` **反序**反向应用补丁，再与 `baseline.json` 逐文件比
   （算法按 `bundle_version` 双读：v1=sha1、v2=sha256，见 `_ALGO_BY_VERSION`）。含钉文件单列
   （`strip` 是产出方的口径，不由消费侧复刻）。

过了这道闸，才轮到 k3dge **自己**把补丁落到主干（`audit_bundle.apply_bundle`）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

#: **不另立口径**：列名/状态枚举/表格解析一律引用既有单源 `engine/report_table`
#: （它的注释写着"唯一来源；消费方不再各自硬编码"）；未关态引用 `engine/markers.OPEN_KINDS`
#: （契约 §8 的机械手：`closure_ok` 的 blockers 就是这三个）。
from k3dge.engine.markers import KINDS as _MARKER_KINDS
from k3dge.engine.markers import OPEN_KINDS as _OPEN_KINDS
from k3dge.engine.report_table import STATUSES as REPORT_STATUSES
from k3dge.engine.report_table import TABLE_HEADER, parse_rows

REPORT_COLUMNS = tuple(TABLE_HEADER.split("|"))
OPEN_STATES = tuple(sorted(_OPEN_KINDS))
CLOSED_STATES = tuple(k for k in _MARKER_KINDS if k not in _OPEN_KINDS)
#: 英文态（findings 字段）→ 报告里的中文状态：**桥接表**，不是判据；下面的断言保证它两侧都覆盖
#: （任一侧加值而没更新这里 ⇒ 导入即失败，而不是悄悄放过）。
ROW_STATE_ZH = {"fixed": "已修", "leftover": "有意留", "pending": "待修",
                "fixnote": "待验证", "disputed": "待裁"}
assert set(ROW_STATE_ZH) == set(_MARKER_KINDS), "桥接表与 markers.KINDS 不同步"
assert set(ROW_STATE_ZH.values()) <= set(REPORT_STATUSES) | {"待验证", "待裁"}, "桥接表与 report_table.STATUSES 不同步"
#: 每行**必须**非空的列（其余列允许空：复审/验收由席按情况填）
REQUIRED_CELLS = ("ID", "日期", "严重度", "优先级", "类型", "问题描述", "位置", "状态", "处置")


def _read_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _table_rows(text: str) -> Tuple[Optional[List[str]], List[Dict[str, str]], int]:
    """拆报告表格（**调用单源解析器** `report_table.parse_rows`）：返回 (表头, 数据行, 表格行总数)。

    第三项用于检出**畸形行**（单源解析器按契约"跳过列数不符的行"，消费侧要把它**报出来**而不是忽略）。
    """
    header, rows = parse_rows(text)
    if header is None:
        return None, [], 0
    count = 0
    seen_header = False
    for line in (text or "").splitlines():
        s = line.strip()
        if not s.startswith("|"):
            if seen_header:
                break
            continue
        cells = [c.strip() for c in s.strip().strip("|").split("|")]
        if not seen_header:
            if all(h in cells for h in ("ID", "状态")):
                seen_header = True
            continue
        if "".join(cells).strip() == "" or set("".join(cells)) <= set("-: "):
            continue
        count += 1
    return header, [dict(zip(header, [c for c in r.values()])) for _, r in rows], count


def _unclosed_local(findings: Dict[str, Any]) -> List[str]:
    """k3dge **自己**算未关项：开的态，或终态但没背书。"""
    out = []
    for fid, rec in (findings or {}).items():
        if not isinstance(rec, dict):
            continue
        st = str(rec.get("state") or "")
        if st in OPEN_STATES or st not in ROW_STATE_ZH:      # 未关＝契约的 open 集合（§8）；未知态也算未关
            out.append(str(fid))
    return sorted(out)


def has_marker_line(text: str, rel: str) -> bool:
    """这一行是**钉**吗（行首注释 + `k3dit:<state> <id>`，契约 §8 语法单源）。"""
    from k3dge.engine.markers import MARKER_RE, MARKER_RE_MD

    rx = MARKER_RE_MD if rel.endswith((".md", ".html")) else MARKER_RE
    return any(rx.match(line.lstrip()) for line in text.splitlines())


def strip_markers(text: str, rel: str) -> str:
    """去钉后的**语义层**文本（契约 §8 语法单源＝`k3dge.engine.markers`，不在消费侧另抄一份）。

    行首注释 + `k3dit:<state> <id>` 才算钉（"提到 ≠ 在用"：文档里举例的钉不会被去掉）。
    """
    from k3dge.engine.markers import MARKER_RE, MARKER_RE_MD

    rx = MARKER_RE_MD if rel.endswith((".md", ".html")) else MARKER_RE
    keep = [line for line in text.splitlines() if not rx.match(line.lstrip())]
    return "".join(line + "\n" for line in keep)


def replay_to_baseline(bundle: Path, dest: Optional[Path] = None,
                       only: Optional[List[str]] = None) -> Dict[str, Any]:
    """把包的 `code/` **反向重放**回基线（审前语义层）——消费侧据此拿到**三路合并的 base**。

    方向取决于 `pins.in_code`（与判据同一口径）：
      - `True`（inplace）：`code/` 带钉 ⇒ 反序反向应用（`pins.patch` → `fix.patch`）；
      - `False`（artifact）：`code/` 已是语义层 ⇒ **不反向** `pins.patch`，只反向 `fix.patch`。
    返回 {ok, root, detail}；失败时 `root` 为空。
    """
    facts = _read_json(Path(bundle) / "manifest.json") or {}
    order = [str(x) for x in (facts.get("apply_order") or [])]
    pins_in_code = bool((facts.get("pins") or {}).get("in_code"))
    code = Path(bundle) / "code"
    if not code.is_dir():
        return {"ok": False, "root": "", "detail": "包内无 code/（无法重放基线）"}
    work = Path(dest) if dest else Path(tempfile.mkdtemp(prefix="k3dge-base-"))
    if dest:
        # 调用方传的任意路径**绝不 rmtree**：误传工作区/主干目录就是不可逆数据丢失，且
        # `ignore_errors=True` 会连失败都吞掉（ocr-218）。只接受不存在或空的目录。
        if work.exists() and any(work.iterdir()):
            return {"ok": False, "root": "", "replay": [],
                    "detail": f"dest 非空目录，拒绝清空：{work}"}
    elif work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    for child in work.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
    shutil.copytree(code, work, dirs_exist_ok=True)
    env = {"GIT_AUTHOR_NAME": "k3dge", "GIT_AUTHOR_EMAIL": "k3dge@local",
           "GIT_COMMITTER_NAME": "k3dge", "GIT_COMMITTER_EMAIL": "k3dge@local",
           "PATH": "/usr/bin:/bin"}
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=k3dge@local", "-c", "user.name=k3dge", "commit", "-qm", "code"]):
        try:
            r = subprocess.run(cmd, cwd=work, capture_output=True, env=env, check=False)
        except OSError as exc:
            shutil.rmtree(work, ignore_errors=True)
            return {"ok": False, "root": "", "replay": [], "detail": f"git 不可用：{exc}"}
        if r.returncode != 0:   # 环境故障不得伪装成"产物不合格"（反向应用失败/哈希链不通过，ocr-219）
            shutil.rmtree(work, ignore_errors=True)
            return {"ok": False, "root": "", "replay": [],
                    "detail": f"重放树初始化失败（git {cmd[1]} rc={r.returncode}）："
                              + (r.stderr or b"").decode("utf-8", "replace")[:160]}
    if only is not None:      # `only`＝只反向这些补丁（合并器用它拿"语义层修复后"的中间树）
        replay = [p for p in order if p in set(only)]
    else:
        replay = [p for p in order if p == "fix.patch"]
        if pins_in_code:
            replay = list(reversed([p for p in order if p in ("fix.patch", "pins.patch")]))
    _ALLOWED_PATCHES = {"fix.patch", "pins.patch"}
    for name in replay:
        # 补丁名来自**不可信**的 `manifest.json`（外部包）⇒ 白名单 + 不得含路径分隔/`..`，
        # 否则 `bundle / "../../x"` 会让本进程读/应用包外的文件（ocr-054）。
        if name not in _ALLOWED_PATCHES or Path(name).name != name:
            shutil.rmtree(work, ignore_errors=True)
            return {"ok": False, "root": "", "replay": replay,
                    "detail": f"非法补丁名（路径穿越？）：{name!r}"}
        rc = subprocess.run(["git", "apply", "-R", "-p1", str(Path(bundle) / name)],
                            cwd=work, capture_output=True, env=env)
        if rc.returncode != 0:
            shutil.rmtree(work, ignore_errors=True)
            return {"ok": False, "root": "", "replay": replay,
                    "detail": f"反向应用 {name} 失败：{(rc.stderr or b'').decode('utf-8', 'replace')[:200]}"}
    return {"ok": True, "root": str(work), "replay": replay, "detail": ""}


#: 内容摘要算法由**包结构版本**决定——与产出方 `k3dit.pack._ALGO_BY_VERSION` 同一张双读表
#: （v1＝sha1 只读兼容；v2＝sha256：SHA-1 有实用 chosen-prefix 碰撞，被审方可控文件集下
#: "送审树≠后门树同哈希"在攻击面内，ocr-220）。版本标记＝迁移记录，不在包内再造口径。
_ALGO_BY_VERSION = {1: "sha1", 2: "sha256"}


def _replay_hashes(bundle: Path) -> Dict[str, Any]:
    """反向重放后逐文件比 `baseline.json`（重放本身走 `replay_to_baseline`，与合并器同源）。"""
    import hashlib

    baseline = _read_json(Path(bundle) / "baseline.json") or {}
    want = baseline.get("files") or {}
    if not want:
        return {"ok": False, "checked": 0, "mismatched": [], "files_with_markers": [], "skipped_pin_files": [],
                "detail": "baseline.json 缺 files"}
    ver = (_read_json(bundle / "manifest.json") or {}).get("bundle_version")
    algo = _ALGO_BY_VERSION.get(ver)
    if algo is None:
        # 白名单闸会另报；这里**不猜算法**——用错算法比"不算"更糟（把篡改洗成"哈希通过"）
        return {"ok": False, "checked": 0, "mismatched": sorted(want), "files_with_markers": [],
                "skipped_pin_files": [], "detail": f"bundle_version={ver!r} 无已知摘要算法，哈希链不可核"}
    rep = replay_to_baseline(bundle)
    if not rep.get("ok"):
        return {"ok": False, "checked": 0, "mismatched": [], "files_with_markers": [],
                "skipped_pin_files": [], "detail": rep.get("detail") or "重放失败"}
    work = Path(rep["root"])
    try:
        mismatched, with_pins, checked = [], [], 0
        work_root = work.resolve()
        for rel, digest in sorted(want.items()):
            # `rel` 来自**不可信**的 `baseline.json`（外部包）：绝对路径/`..` 会逃出重放树、读任意文件
            # （内容 oracle）⇒ containment 校验，越界计入 mismatched（ocr-055）。
            try:
                f = (work / rel).resolve()
                inside = f.is_relative_to(work_root)
            except (OSError, ValueError):
                inside = False
            if not inside or not f.is_file():
                mismatched.append(rel)
                continue
            try:
                raw = f.read_bytes().decode("utf-8", errors="surrogateescape")   # 无损往返
            except OSError as exc:
                mismatched.append(rel)
                continue
            sem = strip_markers(raw, rel)          # **去钉后比语义层**（契约 §8 语法单源）
            if has_marker_line(raw, rel):          # 只按"真匹配到钉行"计数（二进制文件不误标）
                with_pins.append(rel)
            # **两种摘要任一命中即通过**（真跑实证，ocr-220 消费侧另一半）：
            #  - 产出方的 `baseline.json` 是**原始字节**摘要（真跑：无尾换行的文件 raw 命中、sem 不命中）；
            #  - 契约 §8 又要求容忍"上一轮留下的钉" ⇒ 去钉语义层也是合法读法。
            # 旧实现只比 `sem`：`strip_markers` 走 `splitlines()` + 补 `\n`，对**无尾换行**的文件
            # 会多出一个字节 ⇒ 与产出方的 raw 摘要永远差 1，把 `raw==baseline` 的好包整判
            # "内容哈希链不通过"（真跑 M11 实证 10 文件全 raw_bytes_match=True 仍被误拒）。
            # 篡改在同一文件里**追加代码**：raw 与 sem 都会变 ⇒ 两条腿都抓得到，不削弱。
            # `errors="surrogateescape"`：坏字节无损往返（`errors="replace"` 会变 U+FFFD，摘要必错，409）。
            got_raw = hashlib.new(algo, raw.encode("utf-8", errors="surrogateescape")).hexdigest()
            got_sem = hashlib.new(algo, sem.encode("utf-8", errors="surrogateescape")).hexdigest()
            if got_raw == digest or got_sem == digest:
                checked += 1
            else:
                mismatched.append(rel)             # 含钉文件**不豁免**：篡改一样抓得到
        return {"ok": not mismatched, "checked": checked, "mismatched": mismatched,
                "mismatched_preview": mismatched[:10],
                "files_with_markers": with_pins[:10], "skipped_pin_files": [], "detail": ""}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def verify_bundle_local(bundle: Path, *, expect_input: str = "", require_closed: bool = True,
                        accept_baseline_drift: str = "") -> dict:
    """k3dge 自己的验收（不调 k3dit）。返回 {ok, errors[], facts{}, report_rows, unclosed, hash{}, cross_check{}}。"""
    bundle = Path(bundle)
    errors: List[str] = []
    facts = _read_json(bundle / "manifest.json") or {}
    if not facts:
        return {"ok": False, "errors": ["manifest.json 缺失或不可解析"], "facts": {},
                "report_rows": 0, "unclosed": [], "hash": {}, "cross_check": {}}
    if not isinstance(facts, dict):
        # 合法 JSON 但不是 object（数组/字符串/数字）⇒ `facts.get` 会 AttributeError 崩验收（ocr-220）
        return {"ok": False, "errors": [f"manifest.json 顶层不是对象（{type(facts).__name__}）"],
                "facts": {}, "report_rows": 0, "unclosed": [], "hash": {}, "cross_check": {}}
    try:
        from k3dge.engine.audit_bundle import SUPPORTED_BUNDLE_VERSIONS, bundle_input_matches
    except Exception:      # pragma: no cover - 防御
        SUPPORTED_BUNDLE_VERSIONS = (1, 2)
        bundle_input_matches = None
    ver = facts.get("bundle_version")
    if ver not in SUPPORTED_BUNDLE_VERSIONS:
        errors.append(f"bundle_version={ver!r} 不在白名单 {SUPPORTED_BUNDLE_VERSIONS}")
    if expect_input:
        if bundle_input_matches is None:      # pragma: no cover - 回退旧 realpath 判据
            try:
                if Path(str(facts.get("input") or "")).resolve() != Path(str(expect_input)).resolve():
                    errors.append(f"输入身份不符：包为 {facts.get('input')!r}，目标是 {expect_input!r}")
            except OSError:
                pass
        elif not bundle_input_matches(facts.get("input"), expect_input):
            errors.append(f"输入身份不符：包为 {facts.get('input')!r}，目标是 {expect_input!r}")
    order = [str(x) for x in (facts.get("apply_order") or [])]
    for name in order:
        if name not in ("fix.patch", "pins.patch"):
            errors.append(f"apply_order 含未知补丁 {name!r}")
        elif not (bundle / name).is_file() or (bundle / name).stat().st_size == 0:
            errors.append(f"apply_order 声明了 {name}，但包里缺失或为空")
    for rel in ("report.md", "findings.json", "baseline.json"):
        if not (bundle / rel).is_file():
            errors.append(f"必需文件缺失：{rel}")

    # ---- 报告完备性 + 闭环（本地算） ----
    items = _read_json(bundle / "findings.json") or {}
    findings = items.get("items") if isinstance(items, dict) else items
    if not isinstance(findings, list):
        findings = []
        errors.append("findings.json 结构不可识别（期望 {items: [...]}）")
    by_id = {str(x.get("id")): x for x in findings if isinstance(x, dict) and x.get("id")}
    unclosed = _unclosed_local({i: x for i, x in by_id.items()})
    terminal_unacked = sorted(str(i) for i, x in by_id.items()
                              if str(x.get("state") or "") in CLOSED_STATES and not x.get("review_ack"))
    # 模块开头的判据写着"未关＝open 态 **或终态未背书**"，但旧实现只把 `terminal_unacked` 放进
    # cross_check 当信息 ⇒ 自报已关而无人背书的项会被算成已关（判据与实现漂移，ocr-217）。
    unclosed = sorted(set(unclosed) | set(terminal_unacked))
    report_rows = 0
    if (bundle / "report.md").is_file():
        try:
            report_text = (bundle / "report.md").read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:   # 报告含非法字节 ⇒ 报 errors，不崩验收（ocr-221）
            errors.append(f"report.md 不可读：{exc}")
            report_text = ""
        header, rows, table_lines = _table_rows(report_text)
        report_rows = len(rows)
        if tuple(header or ()) != REPORT_COLUMNS:
            errors.append(f"报告表头不是 12 列（或顺序不符）：{header!r}")
        if table_lines != len(rows):
            errors.append(f"报告有 {table_lines - len(rows)} 行**畸形行**（列数与表头不符）⇒ 不完备")
        ids: List[str] = []
        for row in rows:
            rid = row["ID"]
            ids.append(rid)
            for col in REQUIRED_CELLS:
                if not row.get(col):
                    errors.append(f"{rid}：必需列 `{col}` 为空")
            zh = row["状态"]
            if zh not in set(ROW_STATE_ZH.values()):
                errors.append(f"{rid}：状态 {zh!r} 不在闭集 {sorted(set(ROW_STATE_ZH.values()))}")
            if zh == "已修" and not row.get("验证"):
                errors.append(f"{rid}：状态「已修」但「验证」列为空（没验证过的修复不算已修）")
        if len(ids) != len(set(ids)):
            errors.append("报告里有重复 ID")
        missing = sorted(set(by_id) - set(ids))
        extra = sorted(set(ids) - set(by_id))
        if missing:
            errors.append(f"报告漏行（findings 里有、报告里没有）：{missing[:5]}")
        if extra:
            errors.append(f"报告多行（报告里有、findings 里没有）：{extra[:5]}")

    # ---- 交叉核：产出方自报的闭环状态（不一致要报出来，但**以本地为准**） ----
    claimed = str(facts.get("status") or "")
    cross = {"claimed_status": claimed, "claimed_unclosed": facts.get("unclosed"),
             "local_unclosed": len(unclosed), "agree": (claimed == "closed") == (not unclosed),
             # 产出方账目字段（`review_ack`）**不作判据**：只作为信息项列出来给人工看
             "terminal_without_ack": terminal_unacked}
    if not cross["agree"]:
        errors.append(f"闭环事实不一致：包自报 status={claimed!r}/unclosed={facts.get('unclosed')!r}，"
                      f"而消费侧从 findings 算出未关 {len(unclosed)} 项（以本地为准）")
    if require_closed and unclosed:
        errors.append(f"未闭环（消费侧算）：{unclosed[:5]}{'…' if len(unclosed) > 5 else ''}")

    # ---- 内容哈希链（反向重放） ----
    pins_in_code = bool((facts.get("pins") or {}).get("in_code"))
    hash_res = _replay_hashes(bundle) if (bundle / "code").is_dir() else {
        "ok": True, "checked": 0, "mismatched": [], "skipped_pin_files": [], "detail": "包内无 code/（跳过）"}
    accepted: List[str] = []
    if not hash_res.get("ok"):
        # `baseline` 的语义层口径随产出方版本变过（旧版把"提到钉的文档行"也 strip）⇒ 旧包在**文档**上必然
        # 对不上。这时允许调用方**显式、带理由**地接受——但有两个硬条件：① 给了理由；② 漂移文件**不被任何
        # 补丁触及**（补丁要落的地方必须逐字节自洽）。接受的事实进 `accepted_drift`，由调用方写进提交信息/账。
        from k3dge.engine.audit_merge import touched_files

        drifted = set(hash_res.get("mismatched") or [])
        touched = touched_files(bundle)
        if accept_baseline_drift and drifted and not (drifted & touched):
            accepted = sorted(drifted)
            hash_res = {**hash_res, "ok": True, "accepted_drift": accepted,
                        "reason": accept_baseline_drift}
        else:
            why = "" if not accept_baseline_drift else "（漂移文件与补丁触及面相交，不接受）"
            errors.append("内容哈希链不通过" + why + "：" +
                          (hash_res.get("detail") or f"不匹配 {hash_res.get('mismatched_preview')}"))

    return {"ok": not errors, "errors": errors, "facts": facts, "report_rows": report_rows,
            "unclosed": unclosed, "hash": hash_res, "cross_check": cross,
            "accepted_drift": accepted,
            "counts": {"findings": len(by_id), "report_rows": report_rows, "unclosed": len(unclosed)}}
