# 审计：k3dit 5-Pass 全量（pipeline/HUMAN_CHECKPOINT/mcp sync 增量，含 M0-M1 归档自包含回退）

- **Date**: 2026-08-26
- **基线**：`86 passed / 1 skipped / 49 subtests / k3dge check --force-full PASS / 4 域契约已同步`
- **审计人**：Agent 经 `k3dit_run_audit(1..5)` 取透镜（注意力隔离），`k3dit check-report` 校验 9 列
- **范围**：`e0de18d..M3` 全量增量（`pipeline.toml` + `HUMAN_CHECKPOINT` + `mcp sync` + `version` + `scaffold` + `M0/M1` 归档回填），不重提 `overview §5.1` 有意留

## 发现

| ID | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1-01 | 中 | P1 | 缺陷 | `bump_version` 三件套非原子写（`write_text` + 内存回滚），`kill -9` 半漂移 | `src/k3dge/engine/version.py:192` | 待修 | 转 M3 | 中途 kill 后 `VERSION_MISMATCH` |
| P4-01 | 高 | P1 | 规范 | `M0/M1` 19+14 条归档被批量截断致失 `可检索摘要`，违 `AGENTS.md §10` | `docs/tasks/archive/M0/*.done.md` `M1/*.done.md` | 待修 | 转 M3 | `git show HEAD` 原 30 行被截 15 行 |
| P2-01 | 中 | P1 | 规范 | `ADR 0019` 撞号重现（`downstream` vs `pattern-absorption`） | `docs/adr/0019-*.md:1` | 待修 | 转 M3 | `ls docs/adr/0019*` 2 文件 |
| P1-02 | 低 | P2 | 缺陷 | `_append_to_unreleased` 裸 `except pass` 致 `CHANGELOG` 未追加无告警 | `src/k3dge/engine/milestone.py:110` | 待修 | 转 M3 | `chmod a-w CHANGELOG.md` 后 `mark_task_done` 仍 ok |
| P1-03 | 低 | P2 | 缺陷 | `.mcp.json` 损坏/非 dict 时静默 `return` 无告警 | `src/k3dge/templates/scaffold.py:121` | 待修 | 转 M3 | `echo '[' > .mcp.json` 后 `mcp sync` 0 且无告警 |
| P1-04 | 低 | P2 | 缺陷 | `create_task` 未校验 `milestone` 致 `../` 逃逸 | `src/k3dge/engine/milestone.py:194` | 待修 | 转 M3 | `milestone="../x"` 落 `docs/escape` |
| P2-02 | 低 | P3 | 规范 | `cmd_mcp` 导入私有 `_ensure_mcp_config` 不在契约 | `src/k3dge/cli/main.py:245` | 待修 | 转 M3 | `spec` 无此符号 |
| P2-03 | 低 | P3 | 规范 | `pipeline.toml`  peer 细节写死并 `PAIRS` 锁，改名需 `k3dge` 发版追赶 | `.agent/pipeline.toml:8` | 有意留 | f987092 既遂 |追赶成本已知 |

> 其余 `P1-06/P1-09/P2-03` 等维持 `§5.1` 有意留，不重开。

## 结论

`18` 待修中 `3` 项 `P1`（`bump` 原子/`M0/M1` 自包含/`ADR 0019`）需 `M3` 优先，其余 `P2` 按 `M3` 已有 `5` 条 `docs/mcp` 等并行。

## 验证

- `k3dit_run_audit(1..5)` 逐轮取透镜
- `k3dit check-report` 本报告 9 列格式 OK
