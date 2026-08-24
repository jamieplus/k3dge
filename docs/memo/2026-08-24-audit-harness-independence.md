# Memo: 审计规程独立于 k3dge，方案不再改设计

> **现行透镜在本文件（顶层）。** 归档当时有原因：同日把 8 维规程写成 `harnesses/audit/PROTOCOL.md`（ADR 0005），memo 按「已晋升」移入 archive。随后 ADR 0008 把 audit 迁出本仓，删掉 PROTOCOL，只留指针去 k3dit；k3dit 又被删后空 init，protocol 没接上。晋升目标没了却没把 memo 搬回顶层，扫描视界空了。k3dit 真正落下 `docs/guides/protocol.md` 之前，本文件留在 `docs/memo/`。08-23 短五轮仍在 archive。

- **类型**：暂无法落地（方向与规程已定；不做成 k3dge 域/子命令；跨仓复用时再抽独立 skill/harness）
- **念头**：审计与质量闸一样，必须和 k3dge 并联，不能进一致性门禁。现行方案已经够用，不再为「审计」改 k3dge 架构。
- **触发场景**：问「审计是不是也应该提为另一个 harness 保持独立性」之后，再问「目前的审计那套方案还需要改进吗，不需要就 memo 一下」
- **关联度**：强相关 — 约束以后还要不要把透镜写进 `engine` / `cli/mcp.py` / `k3dge check`
- **Date**: 2026-08-24
- **处置**：只 memo，不建 `tasks`，不加门禁。下一次对本仓或下游做审计时，按本文「唯一规程」执行并写入 `docs/reviews/`。抽成独立发行物的触发见文末。

## 结论（已定，勿重开设计讨论）

1. **k3dge 不管怎么想，只管证据在不在。** 一致性门禁必须确定性、零 LLM。审计是带透镜的判断，同一份代码可以有不同表；塞进 `k3dge check` 会变软、变慢、被 `--no-verify` 一起绕过。与「质量不进本 harness」（`docs/memo/2026-08-21-code-quality-discussion.md`）同一条线。
2. **三层分开，不要合成一个全能闸。**
   - L1 一致性 = k3dge（契约哈希、结构、矩阵文件是否存在）
   - L2 质量 = 另 harness（ruff/mypy 等，尚未建）
   - 审计 = 规程包（五轮透镜），不是第三套 `check` 二进制
3. **k3dge 里只留文件系统契约与 seal 硬拦**，不留透镜实现：
   - 报告：`docs/reviews/YYYY-MM-DD-<scope>.md`（9 列）
   - 索引：`docs/reviews/SUMMARY.md`、`README.md`
   - 有意留常驻否决：`docs/architecture/overview.md` §5.1
   - `k3dge milestone seal`：有报告、SUMMARY 已登记、guides 无 TODO
4. **不新建 `src/k3dge/audit`，不加 `k3dge audit` 子命令。** 4 个域、人工/Agent 按规程写 reviews 已经够。`k3dge_5pass_audit_prompt` 只是 MCP 便利拷贝，**不是事实源**；与本文冲突时以本文为准，不要在 engine 里演进透镜。MCP 若仍指向缺失的 k3dit protocol，执行时改读本文。
5. **5-Pass 与 8 维不是两套互斥规程。** 用户给出的 8 维 + Vibe 特检是现行唯一清单；2026-08-23 的五轮透镜是骨架，8 维叠在对应轮上。旧 memo `docs/memo/archive/2026-08-23-5pass-audit-protocol.md` 已归档，勿再按那份较短清单单独审计。

## 唯一规程（执行时只开一轮透镜）

交付：`docs/reviews/YYYY-MM-DD-<scope>.md`，表头必须 9 列：

`ID | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证`

- **严重度**：高 / 中 / 低
- **优先级**：P0 / P1 / P2 / P3
- **类型**：缺陷 / 规范 / 冗余 / 设计
- **状态**：已修 / 待修 / 有意留
- **处置** 三选一：已修 / 转 `docs/tasks/` / 有意留（必须写否决理由 + 失效条件）。悬空发现禁止只留在报告里。
- 开审前先读 `docs/reviews/SUMMARY.md` 与 overview §5.1，不重提已修或有意留。

### Pass 1 — 健壮性与安全

8 维「安全性 + 数据输入」+ 原第 1 轮。

- 边界、索引、Null/None、正则 ReDoS
- 子进程/网络 IO 超时、异常粒度、事务回滚是否真回滚
- 越权/污点、注入（XSS/SQL/命令/SSRF）、JWT、硬编码密钥
- Vibe：SQL 拼接、eval/pickle、过时不安全 API

### Pass 2 — 架构与边界

8 维「规范 + 架构」。

- 依赖严格 DAG、内聚/耦合、分层
- 是否违背 ADR、是否重复造轮子
- Vibe：违背本仓分层/命名/错误码（上下文割裂）

### Pass 3 — 设计与契约

8 维「规范 + 架构」。

- 策略/多态是否合理，入参/出参/错误码是否完整
- 展示/传输与核心逻辑是否解开
- Vibe：过度设计 vs 逻辑全堆在传输层

### Pass 4 — 一致性与验证

8 维「业务逻辑 + 时序状态 + 工程测试」+ 原第 4 轮。

- 状态/缓存、跨平台对等、配置元数据
- 流程能否绕过/重放、状态机非法跃迁
- Vibe：幻觉 API、try/pass/TODO 假实现、仅 Happy Path
- **无测试即缺陷**；边界与异常路径要闭环
- 原第 4 轮仍要：`k3dge check` 指纹、多轨脚本同构、tasks 枚举、矩阵 TC、脚手架镜像

### Pass 5 — 性能与简洁

8 维「性能 + 规范」。

- 死代码、重复计算/IO
- 热循环分配、N+1、无分页、复杂度权衡
- Vibe：循环内 IO、大文件全量读内存、前端全量引入重库
- 有意留必须写进报告并回写 overview §5.1（若是新的常驻否决）

## 何时才升级为独立发行物

满足任一再抽 skill / 独立 harness（仍不进 `k3dge check`）：

1. 同一套规程要在 **两个以上下游仓** 复用
2. MCP 从本机 stdio 变成 **网络可达**（届时 S-13 有意留同时失效，见 overview §5.1）
3. 需要版本化透镜、与质量 harness 并列安装

升级形态：独立文档或 skill（`audit-guide`），MCP 只继续读 k3dge 事实（manifest / spec / `k3dge_check`），不在 k3dge 包里维护透镜正文。

## 原文锚点

- 独立性判断：本对话「审计是不是也应该提为另一个 harness 保持独立性」
- 8 维清单：本对话用户给出的五轮全文
- 祖先五轮：`docs/memo/archive/2026-08-23-5pass-audit-protocol.md`
- 质量闸先例：`docs/memo/2026-08-21-code-quality-discussion.md`
