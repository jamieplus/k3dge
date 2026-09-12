---
status: done
milestone: M8
priority: P1
date: 2026-09-10
---

# 判读席禁止重提已 leftover

- **Status**: done
- **Milestone**: M8
- **Priority**: P1
- **可检索摘要**: 活体 a950ab294b34：判读在已有 `k3dit:leftover Q-1/Q-8` 的同一函数上再钉 pending（code-1/value-6 等），违协议「不重提已修或有意留」
- **Date**: 2026-09-10

## Intent

判读窗不得把主干上已裁 `leftover` 的复杂度债当新发现再钉。指令 + 注入清单 + harvest 拒收，三层里至少机检一层。

## Notes

- 实证：`evaluator.py` 已有 `# k3dit:leftover Q-1 CC61 evaluate…` / `Q-8 CC23 _run_batch_tests…`；窗拷贝里 leftover 仍在，席在其上一行加了 `k3dit:pending code-1` / `value-6`（sev=高 prio=P1 type=复杂度）。
- `WINDOW_INSTRUCTIONS` 未提 leftover；`inject_facts` 不收树上已有 leftover 清单给判读窗。
- 建议：物化后 `harvest_pins` 把 kind=leftover 写入 `facts/leftovers.json`；instruction 写「这些位置禁止再钉 pending」；`step_judges` harvest 若 pending 落在已有 leftover 的同一 file+邻近行 → 该钉 FORMAT/丢弃并记 bulletin，不进账本。
- 同单附带：code 与 value 对同一 11 个函数各钉一遍（合线按 id 不去重位置）。价值窗应对「该不该阻断」，不要把 CC 数当新缺陷重报——instruction 分域，合线可按 file:line 去重（后窗让先窗）。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：树上已有 leftover 属消费仓正文；「可否再钉」属 Hall harvest 机检；「该不该阻断」仍属价值窗判断。
- 边界检查：Hall 只比 file+行/已有 kind，不读 leftover 注释当判断。
- 桩子先行：fixture 树先埋 leftover，再落同函数 pending → harvest 拒收；instruction 含 leftovers.json 文件名即可测注入。

## 原话备查

「重提有意留（违 §3 不重提已修或有意留）— 最严重。」活体 a950ab294b34 已 retire，不合主干。
