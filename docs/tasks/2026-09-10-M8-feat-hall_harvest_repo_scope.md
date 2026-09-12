---
status: idea
milestone: M9
priority: P2
date: 2026-09-10
---

# Hall 收成接入 AUDIT.md 侧车 + @file/@repo v2 钉

- **Status**: idea
- **Milestone**: M9
- **Priority**: P2
- **可检索摘要**: ADR-0025 §2.7 非目标已承认：Hall 窗收成只认窗内 `@line` 钉（`@file` 头部块同语法可收）；`@repo`/`AUDIT.md` 侧车条目不进 Hall 流程。peer_contract §8 的 `scope ∈ line|file|repo` 与执行面不等价，多文件发现会漏进账本。
- **Date**: 2026-09-10

## Intent

把 `peer_contract §8` 声明的三种 scope 钉接进 Hall 判读收成，使多文件/仓级发现能进账本：

- `@file`：头部注释块内的 v2 钉（`pins.harvest_pins` 已能扫到行首注释钉，缺"头部块归属"校验）。
- `@repo`：仓根 `AUDIT.md` 的侧车条目（`## k3dit:<kind> <id>@repo <note>` + `- files:`）——`markers.parse_sidecar` 有解析器，但 Hall 从不调用；且侧车无 `sev/prio/type` 属性段，`_pin_to_item` 会拒。

## Notes

- 现状：`hall._harvest_to_artifact` → `pins.harvest_pins(window_root/src)`，只走 `_PIN_RE` 行内匹配；`AUDIT.md` 的 `##` 侧车格式不匹配。
- `_pin_to_item` 要求 `sev/prio/type/desc` 俱全；侧车条目需补 v2 属性段语法（或在 harvest 时按窗补默认+标记 FORMAT）。
- 物化裁剪才是根因：窗按 `scope`（如 `src`）拷，仓根 `AUDIT.md` 可能根本没进窗；要么物化时随带 `AUDIT.md`，要么声明 repo 钉只在 k3dge/markers 侧。
- 与 `k3dge/engine/markers.py` 的 `parse_sidecar`/`validate` 对齐；语法单源仍是 §8。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：钉语法/scope 语义属 peer_contract §8；"什么该进窗"属 Hall 物化（ADR-0025 §2.4）；"是哪类发现"仍归判读窗。
- 边界检查：Hall 只机械收、不判断；`@repo` 归属校验（必须住 AUDIT.md）在 markers 侧，Hall 复用不复刻。
- 桩子先行：fixture 窗先埋 `@file` 头部钉与 `AUDIT.md @repo` 条目 → 断言进账本；越 `@repo` 位置（非 AUDIT.md）→ 拒。

## Related

- `docs/adr/0025-hall-harness-topology.md` §2.7（非目标：scope 面不等价）
- `docs/protocols/peer_contract.md` §8（钉语法 v2；scope 枚举）
- k3dit `src/k3dit/hall.py` `_harvest_to_artifact` / `_pin_to_item`；`src/k3dit/pins.py` `harvest_pins`
- k3dge `src/k3dge/engine/markers.py` `parse_sidecar` / `validate`
