"""docs 目录结构/索引校验（force_full 或本批触 docs 时）。自 `ConsistencyEngine` 拆出。"""

from pathlib import Path
from typing import List

from k3dge.engine.models import Violation


def check_docs(workspace: Path, files, force_full: bool) -> List[Violation]:
    """docs 目录结构/索引校验（force_full 或本批触 docs 时）。"""
    docs_touched = any(str(p).replace("\\", "/").startswith("docs/") for p in files)
    if not (force_full or docs_touched):
        return []
    try:
        from k3dge.engine.doc_catalog import validate_docs, validate_docs_index

        types = None
        if not force_full:
            types = sorted(
                {
                    Path(p).parts[1]
                    for p in files
                    if str(p).replace("\\", "/").startswith("docs/")
                    and len(Path(p).parts) > 1
                }
            )
        return list(validate_docs(workspace, types=types)) + list(
            validate_docs_index(workspace)
        )
    except Exception as extra:
        return [
            Violation(
                "DOC_SCHEMA_INVALID",
                f"docs catalog check crashed: {extra}",
                file_path="docs",
                detail={"path": "docs"},
            )
        ]
