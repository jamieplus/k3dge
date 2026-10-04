---
status: done
milestone: M12
priority: P3
date: 2026-09-30
---

# pipeline.toml 声明面收敛：一套路由词表、声明形状数量、规范语义的权威载体


## 已确认意图
pipeline.toml 声明面收敛：一套路由词表、声明形状数量、规范语义的权威载体

## 可检索摘要
pipeline.toml 声明面收敛：一套路由词表、声明形状数量、规范语义的权威载体

## 关闭理由（2026-10-04，核验后判定不需按原票执行）

来源：M11 审计 `value-2` + `value-4`（`docs/reviews/archive/M11/2026-09-29-M11-k3dit-bundle-audit.md`）转票。核验后**具体目标已落地**：

- **value-2 的核心不一致已消**：legacy 直名顶层表 `["audit.actions.audit"]` 已删（`.agent/pipeline.toml:97` 记"悬空顶层表已删，见 ADR-0025"）；不再有「legacy 直名 vs 角色名」两套词表并立。
- **声明面收一处的语义已写死并有 schema**：`pipeline.toml:68-71` 明确「编排声明面只有一处＝`[checks.*]`；外部 peer 步走 `stages_produce`/`stages_verify`，内部动作走 `actions`，两类 id 不混一张词表（ADR-0026 §2.1）」。
- value-4 的"161 行/7 种形状 → 拆 4 份或下沉 DEFAULTS"：现文件 163 行，但其中**约半数是承担规范正文的注释**（L5-16/L18-21/L68-77 等），真正覆盖项已只留必要者；继续拆文件只会增坐标。判为**可选软收敛，不构成待办**。

**重开条件**：出现第二种声明形状与 `[checks.*]` 语义重叠、或 `pipeline.toml` 非注释配置行数翻倍时，重立票。
