---
Status: Accepted
Date: 2026-08-25
Deciders: Core Maintainer
---

# ADR 0020: 外部模式与资产吸收纪律（洁净室 + License 分级）

- **Related**: `docs/memo/2026-08-25-prompt-as-neural-net.md`（稀疏门控隐喻）、`AGENTS.md` 微内核、`ADR 0008` 并列 harness

## 1. 上下文 (Context)
`k3dge/k3dit/k3che/k3lity` 已连吸 `cursor/plugins` 的 `continual-learning`/`verify-this`/`thermos` 等 5 模式，若无统一纪律，外部优秀思想易被生搬硬套、带毒 `License` 或破坏分层。

## 2. 决策 (Decision)

1. **四不**：不增域（靶向喂既有四孤岛）、不抢 `AGENTS` 常驻、不引重包、不直接贴代码
2. **洁净室**：只吸模型/状态机/思想，`Python` 独立重写，剥离商标/Logo/`PNG`
3. **分级**：`MIT/Apache` 宽松可重写（大段提示词附署名）、`GPL` 零代码仅思想、`Proprietary` 仅通用人机工效
4. **固化**：吸收后当轮 `k3dge sync` 锁 `spec` 哈希 + 单测 + `k3dit` 无版权遗留

## 3. 产生后果 (Consequences)
- **正**：`AGENTS.md` 保持 `51` 行微内核，`09-absorption` 按需激活
- **负**：每吸一次需 `k3dge sync` + `k3dit` 复核
- **何时重开**：`License` 出现 `AGPL` 等强传染或需引入 `Node` 运行时
