# 审计：k3dit 5-Pass 穿透（pipeline/HUMAN_CHECKPOINT/mcp sync 增量）

- **Date**: 2026-08-26
- **基线**：`86 passed / 1 skipped / 49 subtests / k3dge check --force-full PASS / 4 域契约已同步`；范围 `e0de18d..f987092`（`pipeline.toml` + `HUMAN_CHECKPOINT` + `mcp sync` + `changelog` 任务清单）
- **审计人**：Agent 经 `k3dit_run_audit` MCP 工具取透镜（5 轮注意力隔离），报告落盘后经 `k3dit_check_report` 校验 9 列
- **范围**：`.agent/pipeline.toml` `src/k3dge/cli/{main,mcp}.py` `engine/{milestone,version,diff,pairs}.py` `sync/generator.py` `templates/{scaffold.py,assets/pipeline.toml.template}` `.mcp.json`
- **输入**：`../k3dit/docs/guides/protocol.md`（5-Pass 骨架 + 8 维叠加）；不重提 §5.1 有意留与已修项

## 发现

| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| N1-01 | 2026-08-26 | 中 | P1 | 缺陷 | `.mcp.json` 损坏/非 dict 时静默覆盖丢 peer 条目，写入非原子 | `src/k3dge/templates/scaffold.py:115-137` | 待修 | 转 tasks | 预置损坏 JSON 后 peer 丢失复现 | 待复审 |  |
| N1-02 | 2026-08-26 | 中 | P1 | 缺陷 | `tomllib` py3.10 缺失被吞 + harness 循环体仅 `pass`，`mcp sync` 恒假成功 | `src/k3dge/cli/main.py:255-270` | 待修 | 转 tasks | py3.10 下静默 | 待复审 |  |
| N1-03 | 2026-08-26 | 中 | P1 | 缺陷 | `.mcp.json` 根为 list/int 时 `_ensure_mcp_config` 抛未捕 `TypeError` 崩 init | `src/k3dge/templates/scaffold.py:121-122` | 待修 | 转 tasks | `[1]`/`42` 复现崩栈 | 待复审 |  |
| P4-01 | 2026-08-26 | 中 | P1 | 一致性 | seal 的 CHANGELOG notes 双轨再漂移：CLI 列任务清单、MCP 仅一句，违 U-04 同语义不变量 | `cli/main.py:313` vs `cli/mcp.py:315` | 待修 | 转 tasks | MCP seal 后缺清单 | 待复审 |  |
| N1-04 | 2026-08-26 | 低 | P2 | 缺陷 | `create_task(milestone=...)` 未校验即拼文件名，`../` 可逃出 `docs/tasks/` | `engine/milestone.py:194-201` | 待修 | 转 tasks | `milestone="../x"` 落盘 `docs/escape-*` | 待复审 |  |
| P2-01 | 2026-08-26 | 中 | P2 | 架构 | overview §2 DAG 缺 `cli → templates` 边（`cmd_init/cmd_mcp` 已消费） | `docs/architecture/overview.md:38-44` | 待修 | 转 tasks | grep 有边图中无 | 待复审 |  |
| P4-02 | 2026-08-26 | 中 | P2 | 配置失真 | `python -m k3dit check-report` 断链：k3dit 无 `__main__.py`，降级第二级不可执行 | `.agent/pipeline.toml:11` | 待修 | 转 tasks | `No module named k3dit.__main__` | 待复审 |  |
| P4-03 | 2026-08-26 | 中 | P2 | 验证缺口 | 新公开面零测试零 TC 行：`mcp sync` 合并语义、align checkpoint payload 无用例 | `docs/specs/cli/spec.md:53-61` | 待修 | 转 tasks | tests 全目录无 `.mcp.json` | 待复审 |  |
| P3-01 | 2026-08-26 | 中 | P2 | 设计 | HUMAN_CHECKPOINT 四处双编码无单一事实源（engine 文案/MCP payload/AGENTS/assets），question 已漂移 | `milestone.py:343` `mcp.py:291` `AGENTS.md:108` | 待修 | 转 tasks | 四处文案形状不一致 | 待复审 |  |
| P2-02 | 2026-08-26 | 低 | P3 | 边界 | `cmd_mcp` 跨域导入私有 `_ensure_mcp_config`，不在契约哈希内 | `cli/main.py:245` → `scaffold.py:111` | 待修 | 转 tasks | templates spec 无此符号 | 待复审 |  |
| P2-03 | 2026-08-26 | 低 | P3 | 规范 | pipeline.toml 写死 peer 调用细节并经 PAIRS 字节锁，peer 改名需 k3dge 发版追赶（f987092 既遂） | `.agent/pipeline.toml:8,11` | 有意留 | 有意留: 并列仓自治张力已知，f987092 为既遂；peer 大改时再评估摘除 PAIRS（失效条件：第二次追赶修复发生） | f987092 为既遂案例 | 待复审 |  |
| P5-01 | 2026-08-26 | 低 | P2 | 死代码 | `cmd_mcp` 的 pipeline 解析块整体无效（循环体仅 `pass`、`_P` 未用），打印夸大成果；scaffold 注释虚假承诺 merge peers | `cli/main.py:251-269` | 待修 | 转 tasks | 实测 servers 仅 `['k3dge']` | 待复审 |  |
| N1-05 | 2026-08-26 | 低 | P3 | 缺陷 | `_init_path` 裸 `except Exception: pass` 吞 manifest 解析错误致版本闸静默失明 | `engine/version.py:27-44` | 待修 | 转 tasks | 注入坏 manifest 无日志 | 待复审 |  |
| N1-06 | 2026-08-26 | 低 | P3 | 缺陷 | `sync_domain` 裸 `read_text` 未捕 `UnicodeDecodeError`（P1-02 修复漏网残余） | `sync/generator.py:90` | 待修 | 转 tasks | spec 写坏字节 traceback | 待复审 |  |

> 通过项（不计表）：契约哈希 4 域同步、template↔.agent 字节相等、`.mcp.json` 与 mcp-bridge.md 块 A 同形、task 枚举合法、脚手架镜像登记完整、ADR 0005 audit 子命令净移除、ADR 0014 pipeline.toml 落位合规。

## 结论

14 项待修（4 中高优 P1：N1-01/02/03/P4-01）+ 1 有意留。核心主题：`pipeline.toml` 与 `mcp sync` 是**声明先行、执行未跟上**——钩子链无消费器、peer 不真合并、降级第二级断链；`HUMAN_CHECKPOINT` 四处双编码需收敛为单一事实源。

## 验证

- `k3dit_run_audit(1..5)` 取透镜逐轮隔离执行
- `k3dit check_report` 校验本报告 9 列格式（见下）
