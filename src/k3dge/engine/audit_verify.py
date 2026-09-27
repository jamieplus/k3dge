"""消费侧**独立验收**（ADR-0012：产物 + 消费者 + 到达）——不把验收外包给产出方。

拿到交付包的第一步**不是**问产出方"你自证了吗"（那是自查），而是 k3dge 自己从包的**文件**里验：

1. **包完备性**：`bundle_version` 白名单、输入身份、`apply_order` 里的补丁存在且非空、必需文件齐；
2. **报告完备性**：12 列**精确**表头（顺序一致）、行与 `findings.json` **一一对应**（无缺/无多/无重）、
   每行必需格非空、状态 ∈ 闭集、`已修` 必有「处置 + 验证」；
3. **闭环由 k3dge 自己算**：未关＝`pending`/`fixnote`/`disputed` 或终态未背书（`review_ack` 假）
   —— 不读产出方自报的 `status`/`unclosed`（只作交叉核，不一致时**报出来**，以本地算的为准）；
4. **内容哈希链**：在临时副本上按 `apply_order` **反序**反向应用补丁，再与 `baseline.json` 逐文件比
   （`sha1`）。含钉文件单列（`strip` 是产出方的口径，不由消费侧复刻）。

过了这道闸，才轮到 k3dge **自己**把补丁落到主干（`audit_bundle.apply_bundle`）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

#: 12 列（顺序即判据；k3dge 自己声明，不 import 产出方）
REPORT_COLUMNS = ("ID", "日期", "严重度", "优先级", "类型", "问题描述", "位置",
                  "状态", "处置", "验证", "复审", "验收")

#: 状态闭集 → 报告里的中文（消费侧判据；与 `rounds.TRANSITIONS` 的终态一致：`fixed`/`leftover` 无出边）
ROW_STATE_ZH = {"fixed": "已修", "leftover": "有意留", "pending": "待修",
                "fixnote": "待验证", "disputed": "待裁"}
OPEN_STATES = ("pending", "fixnote", "disputed")
CLOSED_STATES = ("fixed", "leftover")
#: 每行**必须**非空的列（其余列允许空：复审/验收由席按情况填）
REQUIRED_CELLS = ("ID", "日期", "严重度", "优先级", "类型", "问题描述", "位置", "状态", "处置")


def _read_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _table_rows(text: str) -> Tuple[Optional[List[str]], List[List[str]]]:
    """拆报告表格：返回 (表头, 数据行)。表头取第一行以 `| ID` 开头者。"""
    header: Optional[List[str]] = None
    rows: List[List[str]] = []
    for line in (text or "").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            if cells and cells[0] == "ID":
                header = cells
            continue
        if all(set(c) <= {"-", " "} for c in cells):
            continue                      # 分隔行
        rows.append(cells)
    return header, rows


def _unclosed_local(findings: Dict[str, Any]) -> List[str]:
    """k3dge **自己**算未关项：开的态，或终态但没背书。"""
    out = []
    for fid, rec in (findings or {}).items():
        if not isinstance(rec, dict):
            continue
        st = str(rec.get("state") or "")
        if st in OPEN_STATES or (st in CLOSED_STATES and not rec.get("review_ack")) or st not in ROW_STATE_ZH:
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


def _replay_hashes(bundle: Path, order: List[str], pins_in_code: bool) -> Dict[str, Any]:
    """反向重放（`apply_order` 反序）后逐文件比 `baseline.json`。返回 {ok, mismatched, skipped_pin_files, checked}。"""
    import hashlib

    baseline = _read_json(bundle / "baseline.json") or {}
    want = baseline.get("files") or {}
    code = bundle / "code"
    if not want or not code.is_dir():
        return {"ok": False, "checked": 0, "mismatched": [], "skipped_pin_files": [],
                "detail": f"baseline/code 缺失（baseline.files={len(want)}，code={'有' if code.is_dir() else '无'}）"}
    tmp = Path(tempfile.mkdtemp(prefix="k3dge-verify-"))
    try:
        work = tmp / "code"
        shutil.copytree(code, work)
        env = {"GIT_AUTHOR_NAME": "k3dge", "GIT_AUTHOR_EMAIL": "k3dge@local",
               "GIT_COMMITTER_NAME": "k3dge", "GIT_COMMITTER_EMAIL": "k3dge@local",
               "PATH": "/usr/bin:/bin"}
        for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                    ["git", "-c", "user.email=k3dge@local", "-c", "user.name=k3dge", "commit", "-qm", "code"]):
            subprocess.run(cmd, cwd=work, capture_output=True, env=env, check=False)
        # 重放方向取决于**钉在不在 `code/` 里**（`pins.in_code`）：
        #   in_code=True（inplace）⇒ `code/` 带钉 ⇒ 反序**反向**应用（pins.patch → fix.patch）回到语义层；
        #   in_code=False（artifact）⇒ `code/` 本身已是语义层（钉被剥离，只有 pins.patch 拎着）⇒ **不反向**
        #     pins.patch，只把 fix.patch 反向应用回去（真跑实测：对 artifact 包反向应用 pins.patch 必然打不上）。
        replay: List[str] = [p for p in order if p == "fix.patch"]
        if pins_in_code:
            replay = list(reversed([p for p in order if p in ("fix.patch", "pins.patch")]))
        for name in replay:
            rc = subprocess.run(["git", "apply", "-R", "-p1", str(bundle / name)],
                                cwd=work, capture_output=True, env=env)
            if rc.returncode != 0:
                return {"ok": False, "checked": 0, "mismatched": [], "skipped_pin_files": [],
                        "detail": f"反向应用 {name} 失败：{(rc.stderr or b'').decode('utf-8', 'replace')[:200]}"}
        mismatched, with_pins, checked = [], [], 0
        for rel, digest in sorted(want.items()):
            f = work / rel
            if not f.is_file():
                mismatched.append(rel)
                continue
            raw = f.read_text(encoding="utf-8", errors="replace")
            sem = strip_markers(raw, rel)          # **去钉后比语义层**（契约 §8 语法单源）
            if has_marker_line(raw, rel):          # 只按"真匹配到钉行"计数（二进制文件不误标）
                with_pins.append(rel)
            got = hashlib.sha1(sem.encode("utf-8")).hexdigest()
            if got == digest:
                checked += 1
            else:
                mismatched.append(rel)             # 含钉文件**不豁免**：篡改一样抓得到
        return {"ok": not mismatched, "checked": checked, "mismatched": mismatched[:10],
                "files_with_markers": with_pins[:10], "skipped_pin_files": [], "detail": ""}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def verify_bundle_local(bundle: Path, *, expect_input: str = "", require_closed: bool = True) -> dict:
    """k3dge 自己的验收（不调 k3dit）。返回 {ok, errors[], facts{}, report_rows, unclosed, hash{}, cross_check{}}。"""
    bundle = Path(bundle)
    errors: List[str] = []
    facts = _read_json(bundle / "manifest.json") or {}
    if not facts:
        return {"ok": False, "errors": ["manifest.json 缺失或不可解析"], "facts": {},
                "report_rows": 0, "unclosed": [], "hash": {}, "cross_check": {}}
    try:
        from k3dge.engine.audit_bundle import SUPPORTED_BUNDLE_VERSIONS
    except Exception:      # pragma: no cover - 防御
        SUPPORTED_BUNDLE_VERSIONS = (1,)
    ver = facts.get("bundle_version")
    if ver not in SUPPORTED_BUNDLE_VERSIONS:
        errors.append(f"bundle_version={ver!r} 不在白名单 {SUPPORTED_BUNDLE_VERSIONS}")
    if expect_input:
        try:
            if Path(str(facts.get("input") or "")).resolve() != Path(str(expect_input)).resolve():
                errors.append(f"输入身份不符：包为 {facts.get('input')!r}，目标是 {expect_input!r}")
        except OSError:      # pragma: no cover
            pass
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
    report_rows = 0
    if (bundle / "report.md").is_file():
        header, rows = _table_rows((bundle / "report.md").read_text(encoding="utf-8"))
        report_rows = len(rows)
        if tuple(header or ()) != REPORT_COLUMNS:
            errors.append(f"报告表头不是 12 列（或顺序不符）：{header!r}")
        ids: List[str] = []
        for cells in rows:
            if len(cells) != len(REPORT_COLUMNS):
                errors.append(f"报告行不是 {len(REPORT_COLUMNS)} 格：{cells[:3]!r}…")
                continue
            row = dict(zip(REPORT_COLUMNS, cells))
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
             "local_unclosed": len(unclosed), "agree": (claimed == "closed") == (not unclosed)}
    if not cross["agree"]:
        errors.append(f"闭环事实不一致：包自报 status={claimed!r}/unclosed={facts.get('unclosed')!r}，"
                      f"而消费侧从 findings 算出未关 {len(unclosed)} 项（以本地为准）")
    if require_closed and unclosed:
        errors.append(f"未闭环（消费侧算）：{unclosed[:5]}{'…' if len(unclosed) > 5 else ''}")

    # ---- 内容哈希链（反向重放） ----
    pins_in_code = bool((facts.get("pins") or {}).get("in_code"))
    hash_res = _replay_hashes(bundle, order, pins_in_code) if (bundle / "code").is_dir() else {
        "ok": True, "checked": 0, "mismatched": [], "skipped_pin_files": [], "detail": "包内无 code/（跳过）"}
    if not hash_res.get("ok"):
        errors.append("内容哈希链不通过：" + (hash_res.get("detail") or
                                             f"不匹配 {hash_res.get('mismatched')}"))

    return {"ok": not errors, "errors": errors, "facts": facts, "report_rows": report_rows,
            "unclosed": unclosed, "hash": hash_res, "cross_check": cross,
            "counts": {"findings": len(by_id), "report_rows": report_rows, "unclosed": len(unclosed)}}
