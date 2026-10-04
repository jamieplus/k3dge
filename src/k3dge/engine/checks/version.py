"""版本一致性检查（pyproject ↔ manifest ↔ __init__）。自 `ConsistencyEngine` 拆出。"""

from pathlib import Path
from typing import List

from k3dge.engine.models import Violation


def check_version_consistency(workspace: Path) -> List[Violation]:
    """pyproject ↔ manifest ↔ __init__ 版本同值；异常即 VERSION_MISMATCH。"""
    try:
        from k3dge.engine.version import validate_versions

        return list(validate_versions(workspace))
    except Exception as exc:
        return [
            Violation(
                "VERSION_MISMATCH",
                f"validation failed: {exc}",
                file_path=str(workspace / "pyproject.toml"),
                detail={"drift": f"版本校验未能完成：{exc}"},
            )
        ]
