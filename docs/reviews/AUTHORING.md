# Authoring

Do not keep a report catalog here — `k3dge doc list --type reviews`. 12 columns: `ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收`. Overturning a leftover = edit `LEFTOVERS.md`, not a new shadow list.

Filename `YYYY-MM-DD-<scope>.md` (include `M<n>` when the report is for that milestone). New reports stay at the top level. `k3dge milestone seal <id>` moves this-milestone files to `archive/<id>/` and rewrites leftover hrefs in `LEFTOVERS.md`. Do not hand-move the current milestone's living reports. Reports with no milestone token in this repo live in `archive/untagged/`.

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

<!-- k3dit:pending doc-4 sev=中 prio=P2 type=冲突 本行"处置三选一"含"转为 docs/tasks/ 条目"、下行"必须转 tasks，否则丢"，与 ADR-0022（不再逐条建 task）及 verify_default.md 处置枚举 {已修,有意留,转 sub-task} 相抵（M8 升级台账 doc-3 旧报，修席称已改但正文未动）；模板镜像 src/k3dge/templates/assets/reviews/AUTHORING.md 同病。 -->
- **处置三选一**：已修 / 转为 `docs/tasks/` 条目（链接回本文）/ 有意留（必须写否决理由）
- 未修且未否决的发现不得只留在报告里——必须转 tasks，否则丢
- 本目录不进 k3dge 门禁、不要求 Status/Priority（证据档案，不是工作项）。12 列由 k3dit `check-report` 闸。
