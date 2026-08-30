# Protocol Meta — Default (协议自身契约)

> **事实源**：本文件是"协议之协议"，约束 `docs/protocols/**` 下各默认协议的写法；`k3dge check` 仅验注册一致。

## 交付

`docs/protocols/<type>_default.md`，含 `## Constraints` 机检段与事实源注脚。

## Constraints

L2 入场券须逐条确认：

- 含 `## Constraints` 段，且仅承载机检项（叙事质量项作 advisory 散文，不伪装成机检）
- 含 `> **事实源**` 注脚，明确 `k3dge check` 与该协议的职责边界
- 文件名满足 `^[\w]+_default\.md$`
- `## Constraints` 下每条机检项以 `- ` 列表项呈现，供 `expected_constraints` 抽取
