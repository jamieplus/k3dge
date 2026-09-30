"""封版 ADR 硬闸（ADR-0001 §2 第 8 条「硬闸契约」的一族）：

- `adrs_all_accepted`：范围内 ADR 不得停留在 `Draft`/`Proposed`（封版要求决策已定稿）。
- `adr_landed`：`Accepted` 的 ADR 必带**可解析的落地指针** `Landed-by: <路径> [§节]`，
  使 ADR 成为“已实现现实”的事实源。
- `reconcile_supersedes`：`Supersedes` 声明→自动标记旧 ADR 并移入 `obsolete/`；
  `Rejected` ADR 自动移入 `obsolete/`。

只读**结构事实**（`Status:`/`Landed-by:` 与指针解析），不判决策内容对错（归 k3dit）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

from k3dge.engine.milestone_files import _DOC_AUX_NAMES  # 单源：doc 辅助文件名集（不另存副本）

_FM_STATUS = re.compile(r"^Status:\s*(\S+)", re.M)
_FM_LANDED = re.compile(r"^Landed-by:\s*(.+)$", re.M)
_FM_SUPERSEDES = re.compile(r"^Supersedes:\s*(.+)$", re.M)
_UNDECIDED = {"Draft", "Proposed"}


def _adr_files(workspace: Path) -> List[Path]:
    d = Path(workspace) / "docs" / "adr"
    if not d.is_dir():
        return []
    return [p for p in sorted(d.glob("*.md")) if p.name not in _DOC_AUX_NAMES]


def _status(text: str) -> str:
    m = _FM_STATUS.search(text)
    return (m.group(1) if m else "").strip()


def adrs_all_accepted(workspace: Path) -> Optional[str]:
    """未 Accepted 的 ADR 汇总；全 Accepted/Superseded（或无 ADR）⇒ None。"""
    bad = []
    for p in _adr_files(workspace):
        try:
            st = _status(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            st = ""
        if st in _UNDECIDED or not st:
            bad.append(f"{p.name}({st or '无 Status'})")
    if bad:
        return f"[SEAL REJECTED] ADR 未 Accepted（封版要求全部 Accepted）：{bad}"
    return None


def _pointer_resolves(workspace: Path, ptr: str) -> bool:
    first = ptr.strip().split()[0].strip() if ptr.strip() else ""
    if not first:
        return False
    root = Path(workspace).resolve()
    cand = (root / first).resolve()
    # 绝对路径或 `..` 会丢弃 workspace 前缀 ⇒ 必须 containment 校验；且只认**文件**（目录不算"已落地"，
    # 否则 `Landed-by: /etc` 或仓外路径可把这道 seal 硬闸骗绿，ocr-033）。
    if cand != root and root not in cand.parents:
        return False
    return cand.is_file()


def adr_landed(workspace: Path) -> Optional[str]:
    """Accepted ADR 须带可解析 `Landed-by:`；否则汇总；全满足 ⇒ None。"""
    bad = []
    for p in _adr_files(workspace):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            # seal 硬闸 ⇒ 读不出 = **无法取证**，计入 bad（与 `adrs_all_accepted` 同口径，不静默旁路，ocr-191）。
            bad.append(f"{p.name}(不可读:{type(exc).__name__})")
            continue
        if _status(text) != "Accepted":
            continue
        m = _FM_LANDED.search(text)
        if not m:
            bad.append(f"{p.name}(缺 Landed-by)")
            continue
        ptr = m.group(1).strip()
        if not _pointer_resolves(workspace, ptr):
            bad.append(f"{p.name}->{ptr}(指针不可解析)")
    if bad:
        return f"[SEAL REJECTED] Accepted ADR 缺可解析落地指针（或不可取证）：{bad}"
    return None


def reconcile_supersedes(workspace: Path) -> Optional[str]:
    """归档不再活跃的 ADR 到 `obsolete/`。

    两类：
    1. `Supersedes: ADR-Y` 声明 → 自动标记 ADR-Y `Status: Superseded`
       + `superseded_by: ADR-X`，移入 `obsolete/`。
    2. `Status: Rejected` → 直接移入 `obsolete/`（从未生效，不占活跃目录）。

    返回修复报告或 None（无需修复）。
    """
    d = Path(workspace) / "docs" / "adr"
    if not d.is_dir():
        return None
    obsolete = d / "obsolete"
    fixed: list[str] = []

    # 1. Supersedes 声明 → 标记旧 ADR + 移入 obsolete/
    #    **两遍**：先只读校验全部声明（缺目标 / 自取代），全通过才动盘——否则前半已落盘、后半 `return`
    #    会把工作区停在"部分生效"（ocr-034）。
    plan: list[Tuple[Path, Path, str]] = []   # (声明件, 目标件, my_id)
    for p in _adr_files(workspace):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = _FM_SUPERSEDES.search(text)
        if not m or m.group(1).strip() == "-":
            continue
        ref = m.group(1).strip()
        target_id = ref.replace("ADR-", "").replace("adr-", "")
        my_id = p.stem[:4]
        target = _find_adr_by_id(d, target_id)
        if target is None:
            return f"[SEAL REJECTED] {p.name} Supersedes: {ref} 但找不到对应 ADR 文件"
        # 自取代守卫：误填自己会把"正在取代别人的一方"自己归档掉，活跃目录少一条审查对象（ocr-035）。
        if target_id == my_id or target == p:
            return (f"[SEAL REJECTED] {p.name} Supersedes 指向自身（ADR-{my_id}）"
                    "——拒绝自取代（会让生效决策从活跃目录消失）")
        plan.append((p, target, my_id))
    for _p, target, my_id in plan:
        try:
            old_text = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _is_superseded(old_text, my_id) and target.parent.name == "obsolete":
            continue
        old_text = _mark_superseded(old_text, my_id)
        obsolete.mkdir(parents=True, exist_ok=True)
        (obsolete / target.name).write_text(old_text, encoding="utf-8")
        if target.parent != obsolete:
            target.unlink()
        fixed.append(f"{target.name} → obsolete/ (Superseded by ADR-{my_id})")

    # 2. Rejected ADR → 直接移入 obsolete/
    for p in _adr_files(workspace):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _status(text) != "Rejected":
            continue
        obsolete.mkdir(parents=True, exist_ok=True)
        dest = obsolete / p.name
        dest.write_text(text, encoding="utf-8")
        p.unlink()
        fixed.append(f"{p.name} → obsolete/ (Rejected)")

    if fixed:
        return "[ADR RECONCILED] " + "; ".join(fixed)
    return None


def _find_adr_by_id(d: Path, target_id: str) -> Optional[Path]:
    """Find ADR by number prefix, searching both `docs/adr/` and `docs/adr/obsolete/`."""
    prefix = target_id.zfill(4)
    for search_dir in (d, d / "obsolete"):
        if not search_dir.is_dir():
            continue
        for p in sorted(search_dir.glob(f"{prefix}-*.md")):
            if p.name not in _DOC_AUX_NAMES:
                return p
    return None


def _is_superseded(text: str, by_id: str) -> bool:
    st = _status(text)
    if st.lower() != "superseded":
        return False
    return f"superseded_by:" in text and f"ADR-{by_id}" in text


def _mark_superseded(text: str, by_id: str) -> str:
    """Replace Status line with Superseded + inject superseded_by field."""
    text = re.sub(r"^Status:\s*\S+", "Status: Superseded", text, count=1, flags=re.M)
    # Inject superseded_by after Supersedes line (or after Status if no Supersedes)
    # 旧写法 `"^superseded_by:" not in text` 把正则锚当纯文本找，永远找不到 ⇒ 守卫恒真，
    # 对已有该字段的旧 ADR 再注入一行（frontmatter 重复键）。
    if not re.search(r"^superseded_by:", text, re.M):
        if re.search(r"^Supersedes:", text, re.M):
            text = re.sub(
                r"(^Supersedes:.+$)",
                r"\1\nsuperseded_by: ADR-" + by_id,
                text, count=1, flags=re.M,
            )
        else:
            text = re.sub(
                r"(^Status:\s*Superseded)",
                r"\1\nsuperseded_by: ADR-" + by_id,
                text, count=1, flags=re.M,
            )
    return text


def amend_format(workspace: Path) -> Optional[str]:
    """seal 预审入口：**委托** `pure_schema.check_amend`（与 `k3dge check` 同一实现，避免两套判据）。

    判据与动因见 `pure_schema.check_amend` 的 docstring；此处只做"扫 ADR 目录 + 汇总一句话"。
    **fail-closed**：schema 缺失/损坏/顶层非对象 ⇒ 报错（此前 `schema={}` 让 `check_amend` 首行直接
    return [] ⇒ 该 seal 前置闸静默全绿，且与 schema 装配链「缺文件硬报错」口径不一致，ocr-194）。
    """
    from k3dge.engine.pure_schema import check_amend

    adrs = _adr_files(workspace)
    if not adrs:
        return None
    schema_path = Path(workspace) / "docs" / "adr" / ".schema.json"
    if not schema_path.is_file():
        return ("[SEAL REJECTED] docs/adr/.schema.json 缺失：adr_amend_format 无法取证"
                "——建表或跑 `k3dge sync`")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"[SEAL REJECTED] docs/adr/.schema.json 不可读/损坏：{exc}"
    if not isinstance(schema, dict):
        return f"[SEAL REJECTED] docs/adr/.schema.json 顶层不是对象（{type(schema).__name__}）"
    probs: List[str] = []
    for f in adrs:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            probs.append(f"{f.name}: 不可读（{type(exc).__name__}）")
            continue
        for code, msg, _scope in check_amend(schema.get("amend"), schema.get("codes") or {},
                                             f.name, text):
            probs.append(f"{f.name}: {msg}")
    return None if not probs else "ADR amend 形态不合规：" + "；".join(probs[:4])
