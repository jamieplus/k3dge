"""`.agent/docs.toml` 的 `= true` 键必须被 `scripts/generate-docs.sh` 处理。自 `ConsistencyEngine` 拆出。"""

import re
from pathlib import Path
from typing import List

from k3dge.engine.models import Violation


def check_docs_toml(workspace: Path) -> List[Violation]:
    """`.agent/docs.toml` 的 `= true` 键必须真的会被 `scripts/generate-docs.sh` 处理，且目标文件在。

    键表**不在这里另造一份**：直接从写脚本自己的 `gen "<key>" "<file>" "<title>"` 行读
    （写侧是唯一声明处）；读不到任何 `gen` 行 ⇒ 跳过（脚本形态变了不误报）。
    """
    cfg = workspace / ".agent" / "docs.toml"
    script = workspace / "scripts" / "generate-docs.sh"
    if not cfg.is_file() or not script.is_file():
        return []
    try:
        table = dict(
            (k, f) for k, f, _t in re.findall(r'gen\s+"([a-z_]+)"\s+"([^"]+)"\s+"([^"]*)"', script.read_text(encoding="utf-8"))
        )
        enabled = re.findall(r"^\s*([a-z_]+)\s*=\s*true\b", cfg.read_text(encoding="utf-8"), re.MULTILINE)
    except (OSError, UnicodeDecodeError):
        return []
    if not table:
        return []
    out: List[Violation] = []
    for key in enabled:
        target = table.get(key)
        if key == "readme":
            target = "README.md"   # readme 走专门分支（刷新布局/基础版），不在 gen 表里
        if target is None:
            out.append(
                Violation(
                    "DOCS_TOML_KEY_UNKNOWN",
                    f"`.agent/docs.toml` 的 `{key} = true` 不会被 `scripts/generate-docs.sh` 处理（键表见该脚本的 gen 行）",
                    file_path=".agent/docs.toml",
                    detail={"path": ".agent/docs.toml", "key": key},
                )
            )
            continue
        # 只查"键脚本认不认识"：`= true` 而文件尚未生成是**收尾流程的常态**（`generate-docs.sh` 在
        # 工程收尾时才落桩），报它会把每个刚 init 的仓都打红。
    return out
