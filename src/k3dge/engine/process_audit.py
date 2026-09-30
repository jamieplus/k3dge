"""过程审计面（SQA，ADR-0001 §2 第 8 条「硬闸契约」的一族）：里程碑证据链的完整性/可追溯。

k3dge 只持本仓工件，故此处只判**报告自身的可确定子集**：
- `_SIGN_KEYS`：`审计人` / `透镜来源` / `基线` 署名**已填且非模板占位**（判据单源 `sign_missing()`）
  ——报告被署名＝有来源、有可验的内容锚点（占位值不算锚点）。

**不是封板前置**（ADR-0004 §2.1.3/§2.1.10 🅰1）：报告降为**可选产物**——存在则须合格，
不存在不卡流程；"报告已入库（git 跟踪）"这类**可追溯**要求也一并退出闸位（原
`evidence_chain_error` 因此删除：它曾把"缺报告 / 未入库"当封板拒绝理由，而那是旧模型的判据）。
封板资格由 `seal` 相位 2 的**审计正常返回** + 边界 `tag <M>=<B>` 决定。

**不在本模块**（归 k3dit，待 peer 落地后扩展）：审计线的强时序事实
（`provenance.baseline` == 线头、`lens_version` == 当前、审计发生在 `fix_base` 之后）。
"""

from __future__ import annotations

import re

#: 报告必填的署名/来源/锚点。`基线` 是**可验的内容锚点**：它让"报告对应当前内容"
#: 有 durable 依据（随报告入库；`audit_jobs.json` 是 gitignored 的本地状态，不能依赖）。
_SIGN_KEYS = ("审计人", "透镜来源", "基线")
# 模板未填的占位值：`基线` 被 docstring 称作"可验的内容锚点"，只做"非空"判就允许
# AUTHORING 模板原句（`commit/tests 状态快照`）过闸 ⇒ 锚点是空的（ocr-288）。
_SIGN_PLACEHOLDER_MARKS = ("状态快照", "待填", "TBD", "<", "{{", "…")


def sign_missing(text: str) -> list:
    """`_SIGN_KEYS` 的**唯一判定**：缺失或仍是模板占位 ⇒ 记为缺。"""
    out = []
    for key in _SIGN_KEYS:
        val = _field(text, key)
        if not val or any(m in val for m in _SIGN_PLACEHOLDER_MARKS):
            out.append(key)
    return out


def _field(text: str, key: str) -> str:
    # `\s` 含 `\n`：原来 `[:：]\s*(.+)` 在值为空时会跨行捕获**下一行**（假"值非空"，fail-open）。
    # 改成冒号后只许行内空白 + 值必须同行且以非空白起头（ocr-097）。
    m = re.search(rf"^-[ \t]*\*\*{re.escape(key)}\*\*[ \t]*[:：][ \t]*(\S.*?)[ \t]*$", text, re.M)
    return m.group(1).strip() if m else ""
