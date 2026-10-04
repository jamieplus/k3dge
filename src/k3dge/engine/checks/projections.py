"""生成物新鲜度闸：符号索引 / `docs/generated/{api,domains}.md` / `.mcp.json`。自 `ConsistencyEngine` 拆出。"""

import json
from pathlib import Path
from typing import List

from k3dge.engine.checks.mcp_json import check_mcp_json
from k3dge.engine.manifest import Manifest
from k3dge.engine.models import Violation


def check_generated_projections(workspace: Path, manifest: Manifest) -> List[Violation]:
    """生成物的新鲜度闸：符号索引 / `docs/generated/{api,domains}.md` / `.mcp.json`。

    这三件（加上已被 `DOC_INDEX_STALE` 罩住的 `docs-index.json`）都是**可重算的投影**，
    但此前只有 docs-index 有闸 ⇒ 其余三件“写了就没人管旧”（本仓 2026-09-21 盘点：悬空）。
    与 `DOC_INDEX_STALE` 同形：重建与盘上比，不等即红，修法＝重生它的那条命令。
    纯静态、不写盘、不联网。
    """
    out: List[Violation] = []

    # ① 符号索引（`k3dge where` 的判据面：旧索引会静默返回错位置）
    try:
        from k3dge.engine import search

        idx_path = search.index_path(workspace)
        if idx_path.is_file():
            try:
                actual = json.loads(idx_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                actual = None
            if actual != search.build_symbol_index(workspace):
                rel = str(idx_path.relative_to(workspace)).replace("\\", "/")
                out.append(
                    Violation(
                        "SYMBOL_INDEX_STALE",
                        "symbol index is stale (rebuild differs)",
                        file_path=rel,
                        detail={"path": rel, "reason": "盘上内容与重建结果不同"},
                    )
                )
    except Exception as exc:  # 工具坏不得静默：报一次而非吞掉
        out.append(
            Violation(
                "SYMBOL_INDEX_STALE",
                f"symbol index check crashed: {exc}",
                file_path="docs/generated/symbol-index.json",
                detail={"path": "docs/generated/symbol-index.json", "reason": str(exc)},
            )
        )

    # ② docs/generated/{api,domains}.md（`k3dge sync` 的产物）
    try:
        from k3dge.engine.generated_docs import render_manual_docs_content

        for path, expected in render_manual_docs_content(workspace, manifest).items():
            if not path.is_file():
                continue  # 缺文件不是“陈旧”（与 `validate_docs_index` 同口径：缺 ⇒ 不报）
            rel = str(path.relative_to(workspace)).replace("\\", "/")
            if path.read_text(encoding="utf-8") != expected:
                out.append(
                    Violation(
                        "DOCS_GENERATED_STALE",
                        "generated doc is stale (re-render differs)",
                        file_path=rel,
                        detail={"path": rel, "reason": "与 `k3dge sync` 的重建结果不同"},
                    )
                )
    except Exception as exc:
        out.append(
            Violation(
                "DOCS_GENERATED_STALE",
                f"generated docs check crashed: {exc}",
                file_path="docs/generated",
                detail={"path": "docs/generated", "reason": str(exc)},
            )
        )

    # ③ .mcp.json：声明 enabled 的 peer（能探到 sibling MCP 模块的）必须在 mcpServers 里
    try:
        out.extend(check_mcp_json(workspace))
    except Exception as exc:
        out.append(
            Violation(
                "MCP_JSON_PEER_MISSING",
                f".mcp.json check crashed: {exc}",
                file_path=".mcp.json",
                detail={"path": ".mcp.json", "peer": "（校验崩溃，未定位）", "reason": str(exc)},
            )
        )
    return out
