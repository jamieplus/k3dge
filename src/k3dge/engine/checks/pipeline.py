"""pipeline.toml 语义硬门控（纯静态）。自 `ConsistencyEngine` 拆出。"""

from pathlib import Path
from typing import List

from k3dge.engine.models import Violation


def check_pipeline(workspace: Path) -> List[Violation]:
    """pipeline.toml 语义硬门控（纯静态；文件不存在则优雅跳过）。"""
    out: List[Violation] = []
    try:
        from k3dge.engine.pipeline_schema import validate_pipeline_config

        for code, msg in validate_pipeline_config(workspace):
            out.append(
                Violation(code, msg, domain="pipelines", file_path=".agent/pipeline.toml")
            )
    except Exception as exc:
        out.append(
            Violation(
                "PIPELINE_SCHEMA_INVALID",
                f"pipeline validation crashed: {exc}",
                domain="pipelines",
                file_path=".agent/pipeline.toml",
                detail={"path": ".agent/pipeline.toml", "reason": str(exc)},
            )
        )
    return out
