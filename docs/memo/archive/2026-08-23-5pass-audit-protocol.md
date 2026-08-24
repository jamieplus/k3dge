# Memo: 5-Pass 专项聚焦代码审计方法论

- **类型**：模糊概念（in-scope 但暂无独立落地载体，当前以 `AGENTS.md` 口头纪律 + 人工审计执行）
- **念头**：将 LLM 易"注意力漂移"的全量代码评审，拆为 5 轮独立透镜（Lens）顺序遍历，每轮仅激活单一认知维度，强制事实源驱动与 9 列闭环归档：
  1. **Pass 1 正确性与缺陷** — 边界/类型、正则转义与连字符、subprocess timeout/capture、文件移动事务回滚
  2. **Pass 2 架构与拓扑** — DAG 依赖方向、ADR 决策一致性、领域职责纯度、机器投影不作判据
  3. **Pass 3 设计与抽象** — 策略模式/开闭原则、@property 等修饰符契约感知、展示与哈希正交
  4. **Pass 4 契约一致性** — `k3dge check` 指纹 100% 吻合、多轨脚本同构、tasks 枚举合法、矩阵 TC 闭环、脚手架镜像同步
  5. **Pass 5 简洁与性能** — 死代码消除、AST/IO 缓存、循环临时对象、算法复杂度权衡（有意留需立档）
  交付：`docs/reviews/YYYY-MM-DD-<scope>.md`（9 列：ID/严重度/优先级/类型/问题描述/位置/状态/处置/验证）+ `SUMMARY.md`/`README.md` 索引同步；处置三选一（已修/转 tasks/有意留），严禁悬空
- **触发场景**：用户在 `k3dge` 一体化治理（docstring 投影 + 里程碑三闸机）与 5-Pass 全绿审计（F-01..F-14, 33 tests）完成后，显式指令"Directive: 5-Pass Focused Code Audit Protocol"要求将该方法论 memo 存档
- **关联度**：强相关 — 直接约束 `k3dge` 的审计执行范式，未来可晋升为 `AGENTS.md` 第 12 节纪律或 `docs/guides/audit-guide.md` / `docs/specs/reviews/spec.md` 的规范化载体
- **Date**: 2026-08-23
- **处置**：当前仅 memo 存档，不建 `tasks`；当下一次需对新领域或新里程碑执行审计时，由 Agent 按本 memo 的 5 轮清单逐轮执行，并在 `docs/reviews/` 落盘后视成熟度晋升为正式规范（`Status: idea → deferred`，原 memo 移入 `archive/`）
- **原文锚点**：用户指令全文见本 memo 创建时的对话快照（含 3 节：核心原则/逐轮清单/交付归档），未来晋升时以本文件 + 对话快照为唯一事实源补全细节
