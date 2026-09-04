---
status: done
milestone: M7
priority: P3
date: 2026-09-03
---

# task create duplicate check via cache role

- **Status**: done
- **Milestone**: M7
- **Priority**: P3
- **可检索摘要**: `k3dge task create` 成功后经 cache 角色召回相似/历史条目（语料含 tasks/archive），只提示不裁决、永不阻断——k3che 在 k3dge 内第一个"不接就少一块"的真消费者
- **Date**: 2026-09-03

## 边界与拆分（规则 08）

- 事实归属：相似判定**不做**（那是人的）；召回=cache 角色；提示渲染=CLI/MCP 出口；创建本身仍 `milestone.create_task`，不依赖 H3 存活。
- 边界检查：k3dge 不解析 `.k3che/` 内容，只走 `cache.search` 信封；skip/坏信封 ⇒ 无提示（有测试锁死"哨兵 run_action 会炸"的反证）。
- 桩子先行：本消费者上线不依赖 k3dit/CAS；archive 已在 CacheIndex.rglob 覆盖内（实测首跑命中两条归档缺陷记录）。

## 改动

- `engine/milestone._similar_task_hints`（排除自身、top-3、service 降级）
- `cli/main.cmd_task` 创建成功后 `[DUP-CHECK]` 块（标注"不阻断、不裁决"）；`cli/mcp.k3dge_task_create` 返回 `similar` 字段（三出口同构）
- 契约 §0 消费者表 +1；`test_cache_consumer.TestDupCheck` 3 例（含降级两例）
- 实测首跑命中：`archive/M2/…create_task_milestone_escape`、`archive/M3/…P1_04_create_task_milestone` —— 与建档功能同域的历史缺陷簇被翻出。

## 副产物缺陷（本消费者首跑暴露，未修）

第三条命中的标题显示为 `Append-only after Accepted…`——**k3che 标题提取被 ADR front-matter 的注释块骗了**（取第一个 `# ` 行，而那是 `---` 内的说明注释）。全部 22 份 ADR 的索引标题都受影响，降低召回可读性。修法 ~5 行（解析跳过 front-matter）+1 测试，在 k3che 仓——**等授权**（§2.3.7）。

## 验收

- CLI：创建成功且 cache 可用 ⇒ `[DUP-CHECK]` 至多 3 条、排除自身、含 archive；cache 挂 ⇒ 静默、rc 不变。MCP：`similar` 字段同构。
- service 语义不破：本检查不进任何判定链（`check`/`seal` 零变化）。
- `pytest -q` 全绿（基线 225 passed / 1 skipped / 95 subtests）。

## Related

- 前两消费者：`docs/tasks/2026-09-02-M7-feat-peer_outbound_mcp_client.md`（接线批次）；契约 §0/§3
- 上游授权先例：`../k3che/docs/tasks/2026-09-03-fix-index_locks.md`
