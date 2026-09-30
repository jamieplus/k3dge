# Authoring

Do not keep a report catalog here — `k3dge doc list --type reviews`. 12 columns: `ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收`. Overturning a leftover = edit `LEFTOVERS.md`, not a new shadow list.

Filename `YYYY-MM-DD-<scope>.md` (include `M<n>` when the report is for that milestone).
**类名按后缀认**：`-audit.md`＝本轮里程碑审计（k3dit 或 seal 相位 2 产出的那份，`audit_closed`/`Audit-seat`
只读它）；`-quality.md`＝legacy 质量窗；`-scan.md`＝**外部全文件扫描**（如 open-code-review）——
扫描件是补充证据，**不得**冒充审计报告被审计面消费，所以文件名必须以 `-scan.md` 收尾。 New reports stay at the top level. `k3dge milestone seal <id>` moves this-milestone files to `archive/<id>/` and rewrites leftover hrefs in `LEFTOVERS.md`. Do not hand-move the current milestone's living reports. Reports with no milestone token in this repo live in `archive/untagged/`.

```markdown
# 审计：<范围>

- **Date**: YYYY-MM-DD
- **基线**：commit/tests 状态快照
- **审计人**：...

## 发现

| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1-1 | 2026-08-27 | 高 | P0 | 缺陷 | ... | `file:line` | 已修 | ... | `gate PASS` | 待复审 |  |
```

- **处置三选一（ADR-0022）**：已修 / 有意留（必须写否决理由 + 失效条件）/ 转 `sub-task <id>`（仅特别大的单条例外，默认不拆）
- 未修且未否决的发现留在报告行本身（配 `位置` 的 `k3dit:pending` 钉）；报告对应一个带 `report:` 指针的 task，`待修==0` 才可关单——不再逐条建 task
- 本目录不进 k3dge 门禁、不要求 Status/Priority（证据档案，不是工作项）。12 列由 k3dit `check-report` 闸。
