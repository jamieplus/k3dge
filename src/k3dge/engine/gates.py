"""硬闸契约（`.agent/gates.toml`）：声明式阈值/开关；执行器读契约，缺省在代码。

单一源：缺省值在 `DEFAULTS`，仓内 `.agent/gates.toml` 按段覆盖；解析失败回落缺省
（**闸不因配置坏而失效**）。契约只承载数据，不含逻辑/表达式。机制见 ADR-0001 §2 第 8 条。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

REL = ".agent/gates.toml"

#: 各闸的缺省阈值/开关（唯一源）。仓内 `.agent/gates.toml` 可覆盖。
DEFAULTS: Dict[str, Dict[str, Any]] = {
    "audit_trigger": {"c2_nesting_max": 5, "volume_max": 8},
}


def load(workspace: Path) -> Dict[str, Dict[str, Any]]:
    """缺省 ∪ `.agent/gates.toml`（段内覆盖）；文件缺失/坏 ⇒ 缺省。"""
    data: Dict[str, Dict[str, Any]] = {k: dict(v) for k, v in DEFAULTS.items()}
    p = Path(workspace) / REL
    if not p.is_file():
        return data
    try:
        raw = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception:  # 坏 TOML：回落缺省，不抛（闸继续可用）
        return data
    for section, vals in (raw or {}).items():
        if isinstance(vals, dict):
            data.setdefault(section, {}).update(vals)
        else:
            data[section] = vals  # type: ignore[assignment]
    return data


def get(workspace: Path, section: str, key: str) -> Any:
    """读某闸的某阈值（含缺省）。"""
    return load(workspace).get(section, {}).get(key, DEFAULTS.get(section, {}).get(key))
