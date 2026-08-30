---
Status: Accepted
Date: 2026-08-19
Deciders: Core Maintainer
---

# ADR 0001: k3dge 架构设计与工程治理基线

## 1. 上下文 (Context)
在基于 LLM 的自主编码与 Vibe Coding 流程中，Agent 容易出现跨会话语义漂移、随意修改
底层抽象以及"代码与文档脱节"的问题。现存方案多依赖 Soft Prompting 约束，缺乏机器
层面的确定性硬门禁。

## 2. 决策 (Decision)
构建 `k3dge`——一套基于 Python 3.10+ 标准库（核心零依赖，tree-sitter 为可选 extra）、
支持"目录契约 + 双向一致性校验 + Git 门禁拦截"的轻量级工程治理 Harness。

### 核心架构约束：
1. **标准源码布局**：采用 `src/k3dge/` 布局，按 `engine`、`cli`、`sync`、`templates`
   严格划分模块子域。
2. **分层门禁**：
   - L0 结构门禁：spec 章节完整性（正则/结构校验，非字符串匹配）。
   - L1 契约门禁：公开接口签名归一化哈希（内容寻址绑定），Python 用 stdlib `ast`，
     TypeScript 用 tree-sitter（可选依赖）。
   - L2 行为门禁（后续）：Verification Matrix 关联真实测试。
3. **确定性双向绑定**：任何对 `src/k3dge/<domain>/` 公开接口的改动，必须使
   `docs/specs/<domain>/spec.md` 的 Contract Hash 与代码派生的哈希一致。
4. **按 branch 门禁**：校验基准为 `merge-base(main, HEAD)`，code 可先落地，spec 在
   分支内收敛即可；不做"同 commit 强制绑定"。
5. **确定性自愈**：`k3dge sync` 从代码生成 spec 接口块与哈希，Agent 只审阅不发明。

目的语言（减少漂移、幻觉、修局部坏整体等，不必穷举）见 ADR 0011；本 ADR 只定实现。

## 3. 产生后果 (Consequences)
- **正面影响**：阻断 LLM 的无意识抽象破坏；跨会话状态下 100% 可追溯的规格说明书。
- **负面影响 / 权衡**：变更公开接口需额外跑一次 `k3dge sync`；跨语言契约校验依赖
  可选 tree-sitter 依赖。
