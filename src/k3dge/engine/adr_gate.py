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
_ACCEPTED_STATES = {"Accepted", "Superseded"}


def _adr_files(workspace: Path) -> List[Path]:
    d = Path(workspace) / "docs" / "adr"
    if not d.is_dir():
        return []
    return [p for p in sorted(d.glob("*.md")) if p.name not in _DOC_AUX_NAMES]


def _status(text: str) -> str:
    m = _FM_STATUS.search(_frontmatter(text))   # 字段语法只在 fm 内成立（t-062 同族）
    return (m.group(1) if m else "").strip()


def adrs_all_accepted(workspace: Path) -> Optional[str]:
    """未 Accepted 的 ADR 汇总；全 Accepted/Superseded（或无 ADR）⇒ None。"""
    bad = []
    for p in _adr_files(workspace):
        try:
            st = _status(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            st = ""
        # 白名单（Accepted/Superseded）而非黑名单：`Rejected` 未及时归档、大小写/尾点变体
        # （`draft`、`Accepted.`）都不得过闸（同一串在 reconcile 侧是大小写敏感的，黑名单必漏，ocr-190）。
        if st not in _ACCEPTED_STATES:
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
    #    **两遍**：计划相做**全部只读校验并算好落盘文本**（缺目标/自取代/不可标记/归档撞名），
    #    写相只剩 tmp+replace——"全通过才动盘"若只覆盖前半截校验，一条晚发现的坏声明仍会把
    #    工作区停在"部分生效"（ocr-034；t-063 要求校验面与承诺同宽）。
    plan: list[Tuple[Path, Path, str, str]] = []   # (声明件, 目标件, my_id, 已算好的落盘文本)
    for p in _adr_files(workspace):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = _FM_SUPERSEDES.search(text)
        if not m or m.group(1).strip() == "-":
            continue
        ref = m.group(1).strip()
        # `ref.replace("ADR-","")` 会把**整行任意位置**的 `ADR-` 抹掉（`ADR-0001 §2.3` → `0001 §2.3`、
        # 逗号串 → `0001, 0004`），glob 必落空；一条声明也只认了一个目标（ocr-192）。
        target_ids = re.findall(r"ADR-(\d{1,4})\b", ref, re.I)
        if not target_ids:
            return f"[SEAL REJECTED] {p.name} Supersedes 解析不出 ADR 号：{ref!r}"
        mm = re.match(r"(\d+)", p.stem)
        my_id = (mm.group(1).zfill(4) if mm else p.stem[:4])
        for raw_id in target_ids:
            tid = raw_id.zfill(4)
            target = _find_adr_by_id(d, tid)
            if target is None:
                return f"[SEAL REJECTED] {p.name} Supersedes: ADR-{tid} 找不到对应 ADR 文件"
            # 自取代守卫：误填自己会把"正在取代别人的一方"自己归档掉，活跃目录少一条审查对象（ocr-035）。
            if tid == my_id or target == p:
                return (f"[SEAL REJECTED] {p.name} Supersedes 指向自身（ADR-{my_id}）"
                        "——拒绝自取代（会让生效决策从活跃目录消失）")
            try:
                old_text = target.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if _is_superseded(old_text, my_id) and target.parent.name == "obsolete":
                continue
            marked = _mark_superseded(old_text, my_id)
            if marked is None:
                return (f"[SEAL REJECTED] {target.name} 没有可改的 `Status:` 行（缺/小写/全角冒号）"
                        "——不能把它当'已 Superseded'归档，请先补规范的 Status 头")
            dest = obsolete / target.name
            if dest.is_file() and dest.resolve() != target.resolve():
                # 无条件覆盖 ⇒ 归档件被静默销毁（编号重用/从备份恢复都会撞上），且 glob 不递归根本看不见（ocr-193）。
                return (f"[SEAL REJECTED] obsolete/{target.name} 已存在且非本次移动产物"
                        "——拒绝覆盖归档事实源，请人工裁决")
            plan.append((p, target, my_id, marked))

    # 2. Rejected ADR → 移入 obsolete/。**校验也在计划相做完**（撞名拒覆盖与 Supersedes 同规则，
    #    此前这条分支裸 `write_text` 直写，静默销毁同名归档件——t-064 的不对称）。
    rej_plan: list[Tuple[Path, str]] = []
    for p in _adr_files(workspace):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _status(text) != "Rejected":
            continue
        dest = obsolete / p.name
        if dest.is_file() and dest.resolve() != p.resolve():
            return (f"[SEAL REJECTED] obsolete/{p.name} 已存在——拒绝覆盖归档事实源"
                    "（Rejected 归档与 Supersedes 同规则，请人工裁决）")
        rej_plan.append((p, text))

    # 3. 写相：只剩 tmp+replace（计划相把可预见的失败全部拦在动盘之前）。
    if plan or rej_plan:
        obsolete.mkdir(parents=True, exist_ok=True)
    for _p, target, my_id, marked in plan:
        dest = obsolete / target.name
        # 原子移动：先写 tmp 再 replace，中断不留"两边都没有/只有一半"的状态
        tmp = dest.with_name(dest.name + ".tmp")
        tmp.write_text(marked, encoding="utf-8")
        tmp.replace(dest)
        if target.parent != obsolete:
            target.unlink()
        fixed.append(f"{target.name} → obsolete/ (Superseded by ADR-{my_id})")
    for p, text in rej_plan:
        dest = obsolete / p.name
        tmp = dest.with_name(dest.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(dest)
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


def _frontmatter(text: str) -> str:
    """frontmatter 区（首行 `---` 到下一条 `---` 之间）；无闭合界时取余文（宁严勿宽）。

    字段判据只许在这里找：行锚定的全文搜索仍会命中**正文顶格**的示例/引用行
    （`superseded_by: ADR-0026` 单独成行贴进文档就是合法 Markdown），假"已标记"⇒
    reconcile 幂等早退、真字段永不写入（ocr-390 同族；t-062）。
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return "\n".join(lines[1:])


def _is_superseded(text: str, by_id: str) -> bool:
    st = _status(text)
    if st.lower() != "superseded":
        return False
    # 全文子串判据会把正文里"讨论/示例"提到的 `superseded_by:` 与 `ADR-xxxx` 当"已标记"
    # ⇒ 幂等早退，真字段永不写入（390）。锚到 frontmatter 行。
    return bool(re.search(rf"^superseded_by:[ \t]*ADR-0*{int(by_id)}[ \t]*$",
                          _frontmatter(text), re.M))


def _mark_superseded(text: str, by_id: str) -> "str | None":
    """只在 frontmatter 区内改写：`Status:` 行换成 Superseded，缺则注入 `superseded_by`。

    返回 `None` ＝ **fm 区内没有可改的 `Status:` 行**（整件无 fm/缺失/小写/全角冒号）：
    调用方必须**拒**，不能把没标记的文件当"已 Superseded"移进 obsolete（391）。
    正文顶格的示例行既不作判据、也不是写入靶（t-062 同族：字段语法只在 fm 内成立）。
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None
    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), len(lines))
    idx = next((i for i in range(1, close)
                if re.match(r"^Status[ \t]*[:：]\s*\S+", lines[i])), None)
    if idx is None:
        return None
    lines[idx] = "Status: Superseded\n"
    if not any(re.match(r"^superseded_by:", l) for l in lines[1:close]):
        anchor = next((i for i in range(1, close)
                       if re.match(r"^Supersedes:", lines[i])), idx)
        lines.insert(anchor + 1, "superseded_by: ADR-" + by_id + "\n")
    return "".join(lines)


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
