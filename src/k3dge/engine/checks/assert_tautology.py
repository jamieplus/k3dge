"""真值已写死的测试断言检查。自 `ConsistencyEngine` 拆出。"""

from pathlib import Path
from typing import List

from k3dge.engine import assert_tautology as _at
from k3dge.engine.models import Violation


def check_assert_tautology(workspace: Path, files, force_full: bool) -> List[Violation]:
    """真值已写死的测试断言。全量扫 `tests/`；增量只扫本批里的测试路径。"""
    if force_full:
        rels = _at.test_files(workspace)
    else:
        rels = [str(p).replace("\\", "/") for p in files if _at.is_test_path(str(p))]
    return _at.check(workspace, rels)
