# Obsolete ADRs

不再活跃的决策记录归档于此，由 `adr_gate.reconcile_supersedes` 闸自动移入：

- **Superseded**：被新 ADR 替换（自动改 frontmatter + 移入）
- **Rejected**：提议后被否决，从未生效（直接移入）

规则：
- **不进门禁**：`adr_gate` 只扫 `docs/adr/*.md`（不递归子目录），本目录内文件自动跳过。
- **不改名**：文件名保留原编号，git 历史可追溯。
- **只读**：归档后不再修改；如需澄清，在新 ADR 中说明。
