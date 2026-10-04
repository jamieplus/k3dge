"""`overview.md` 状态闭集覆盖检查。自 `ConsistencyEngine` 拆出。"""

import re
from pathlib import Path
from typing import List

from k3dge.engine.models import Violation


def check_state_doc_coverage(workspace: Path) -> List[Violation]:
    """`docs/architecture/overview.md` 必须列全两个**闭集**：`[NEXT]` 态与 task 态。

    2026-09-21 盘点：这两个闭集是代码里的唯一源，文档里此前只零星出现几个名字 ⇒ 新增/改名
    状态时文档静默过时。只做**标识符级出现性**检查（要求反引号形式，避免撞普通英文词），
    不解析表格格式。
    """
    rel = "docs/architecture/overview.md"
    path = workspace / rel
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    from k3dge.engine import nextstep, state_machine

    states = sorted(nextstep.STATE_OPTIONS) + [s.value for s in state_machine.TaskState]
    # 「要么不写、要么写全」：一个状态名都没列 ⇒ 本文件没打算做状态总览（下游骨架即如此），
    # 不报；列了一部分 ⇒ 那才是会误导人的半张表（漏项＝新状态在总览里不存在）。
    if not any(f"`{s}`" in text for s in states):
        return []
    missing = [s for s in states if f"`{s}`" not in text]
    out: List[Violation] = []
    if missing:
        out.append(
            Violation(
                "ARCH_STATE_DOC_DRIFT",
                f"{rel} 未列全状态闭集（缺 {missing}）——状态源在 `engine/nextstep.STATE_OPTIONS` / "
                f"`engine/state_machine.TaskState`，文档缺项等于静默过时",
                file_path=rel,
                detail={"path": rel, "missing": missing},
            )
        )
    # 表里写了 priority 就要与代码一致（**数字**也漂移过：2026-09-21 发现旧文写反了 ratchet_open）
    for prio, state in re.findall(r"^\|\s*(\d+)\s*\|\s*`([a-z_]+)`\s*\|", text, re.MULTILINE):
        want = nextstep.STATE_OPTIONS.get(state, {}).get("priority")
        if want is not None and int(prio) != int(want):
            out.append(
                Violation(
                    "ARCH_STATE_DOC_DRIFT",
                    f"{rel} 的 `{state}` priority 写成 {prio}，代码是 {want}",
                    file_path=rel,
                    detail={"path": rel, "missing": f"{state}.priority（文档 {prio}，代码 {want}）",
                            "state": state, "got": int(prio), "want": int(want)},
                )
            )
    return out
