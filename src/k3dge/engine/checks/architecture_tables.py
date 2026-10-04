"""设计文档域表 vs manifest 对齐。自 `ConsistencyEngine` 拆出（含域表解析辅助）。"""

import re
from pathlib import Path
from typing import List, Optional

from k3dge.engine.manifest import Manifest
from k3dge.engine.models import Violation

#: 域表列名（两种写法）→ 归一列键。**只认事实列**；description/一句话 是散文，不比对。
_TABLE_COL_KEYS = {
    "domain": "domain",
    "source": "src", "源码": "src",
    "spec": "spec", "契约 spec": "spec",
    "tests": "tests", "测试": "tests",
    "depends_on": "depends_on",
}


def _norm_cell(value: object) -> str:
    """表格单元归一：去反引号/空白、空占位（—/-）归空、逗号列表排序（顺序不敏感）。"""
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        value = ", ".join(str(x) for x in value)
    s = str(value).strip().strip("`").strip()
    if s in {"—", "–", "-", "/", ""}:
        return ""
    if "," in s:
        s = ", ".join(sorted(p.strip() for p in s.split(",") if p.strip()))
    return re.sub(r"\s+", " ", s)


def _domain_table_rows(text: str) -> Optional[dict]:
    """抽出文档里的**域表**（表头含 Domain 且至少含一个事实列）→ {domain: {col: cell}}。

    找不到 ⇒ None（格式变了不当违例报：那是文档评审的事，不是这个闸的判据）。
    """
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            current.append(line.strip())
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)

    for block in blocks:
        header = [c.strip() for c in block[0].strip("|").split("|")]
        keys = [_TABLE_COL_KEYS.get(h.lower().strip("`")) for h in header]
        if "domain" not in keys or not {"src", "spec"} & set(k for k in keys if k):
            continue
        rows: dict = {}
        for raw in block[1:]:
            cells = [c.strip() for c in raw.strip("|").split("|")]
            if not cells or set("".join(cells)) <= set("-: "):
                continue
            name = _norm_cell(cells[0])
            if not name:
                continue
            rows[name] = {
                keys[i]: cells[i] for i in range(min(len(keys), len(cells))) if keys[i]
            }
        if rows:
            return rows
    return None


def check_architecture_tables(workspace: Path, manifest: Manifest) -> List[Violation]:
    """设计文档里的**域表**必须与 manifest 对齐（表行是事实，不是散文）。

    `docs/architecture/overview.md` 头部自称“人写常驻 + `k3dge sync` 聚合校验”——
    但那道“聚合校验”此前**不存在**（2026-09-21 盘点：`grep architecture evaluator|pure_refs` 零命中）：
    改 manifest 的域/源码/spec/tests/depends_on 时，两张表可以静静地说着旧话。
    实质：Diátaxis 里 architecture＝解释（人写），**故意不把它变成生成物**；
    可机检的只是表里那几列事实 ⇒ 只比事实列，不比 description（散文）。
    """
    out: List[Violation] = []
    for rel, cols in (
        ("docs/architecture/overview.md", ("src", "spec")),
        ("docs/architecture/encyclopedia.md", ("src", "spec", "tests", "depends_on")),
    ):
        path = workspace / rel
        if not path.is_file():
            continue
        try:
            rows = _domain_table_rows(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if rows is None:
            continue  # 没找到域表（格式变了也不在这里报，归文档评审）
        missing = sorted(set(manifest.domains) - set(rows))
        extra = sorted(set(rows) - set(manifest.domains))
        detail: dict = {"path": rel}
        if missing or extra:
            out.append(
                Violation(
                    "ARCH_TABLE_DRIFT",
                    f"{rel} 域表与 manifest 的域集不一致“missing={missing} extra={extra}” ",
                    file_path=rel,
                    detail={**detail, "missing": missing, "extra": extra},
                )
            )
        for domain in sorted(set(rows) & set(manifest.domains)):
            cfg = manifest.domains[domain]
            for col in cols:
                want = _norm_cell(cfg.get(col))
                got = _norm_cell(rows[domain].get(col))
                if want != got:
                    out.append(
                        Violation(
                            "ARCH_TABLE_DRIFT",
                            f"{rel} 域表 {domain} 的 {col} 与 manifest 不一致“{got} ≠ {want}” ",
                            domain=domain,
                            file_path=rel,
                            detail={**detail, "domain": domain, "col": col,
                                    "got": got, "want": want},
                        )
                    )
    return out
