"""硬闸契约（`.agent/gates.toml`）：声明式阈值/开关；执行器读契约，缺省在代码。

单一源：缺省值在 `DEFAULTS`，仓内 `.agent/gates.toml` 按段覆盖；解析失败回落缺省
（**闸不因配置坏而失效**）。契约只承载数据，不含逻辑/表达式。机制见 ADR-0001 §2 第 8 条。
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

REL = ".agent/gates.toml"

#: 各闸的缺省阈值/开关（唯一源）。仓内 `.agent/gates.toml` 可覆盖。
DEFAULTS: Dict[str, Any] = {
    "audit_trigger": {"c2_nesting_max": 5, "volume_max": 8},
    "search": {"context_max": 3},
    "markers": {"max_note": 80, "max_note_pending": 500},
    "output": {"default_lines": 10},
    # 编排单元：preconditions（闸 id，全绿才继续）+ actions（动作 id）。见 ADR-0001 §2 第 8 条。
    "checks": {
        "seal": {"preconditions": ["tasks_all_done", "audit_closed", "evidence_chain", "align_pass", "guides_filled",
                                   "adrs_all_accepted", "adr_landed"],
                 "actions": ["full_matrix", "archive", "closure_note", "prune"]},
        "align": {"preconditions": ["tasks_all_done"], "actions": ["full_matrix"]},
    },
}


def load(workspace: Path) -> Dict[str, Any]:
    """缺省 ∪ `.agent/gates.toml`（段内覆盖；`checks.<kind>` 逐键覆盖）；文件缺失/坏 ⇒ 缺省。"""
    data: Dict[str, Any] = copy.deepcopy(DEFAULTS)  # 深拷贝：覆盖不得回写 DEFAULTS
    p = Path(workspace) / REL
    if not p.is_file():
        return data
    try:
        raw = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception:  # 坏 TOML：回落缺省，不抛（闸继续可用）
        return data
    for section, vals in (raw or {}).items():
        if not isinstance(vals, dict):
            data[section] = vals
            continue
        if section == "checks":
            for kind, decl in vals.items():
                if isinstance(decl, dict):
                    data.setdefault("checks", {}).setdefault(kind, {}).update(decl)
        else:
            data.setdefault(section, {}).update(vals)
    return data


def get(workspace: Path, section: str, key: str) -> Any:
    """读某闸的某阈值（含缺省）。"""
    return load(workspace).get(section, {}).get(key, DEFAULTS.get(section, {}).get(key))


def preconditions(workspace: Path, kind: str) -> list:
    """某编排单元（`check`/`align`/`seal`）的前置闸 id 列表。"""
    return list(load(workspace).get("checks", {}).get(kind, {}).get("preconditions", []))


def actions(workspace: Path, kind: str) -> list:
    """某编排单元的动作 id 列表。"""
    return list(load(workspace).get("checks", {}).get(kind, {}).get("actions", []))
