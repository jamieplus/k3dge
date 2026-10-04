# Third-Party Notices

k3dge 源码除本仓外的参考/吸收说明。若未来适配进入这些项目的代码，必须把对应许可与版权行保留进本文件或 `src/` 头部。

## 模式 / 判据参考（洁净室；不粘代码，仅征用思想/判据）

- **DeepTutor** — Apache-2.0, HKU lifelong tutoring
  - 仅带入 AST import 边表 / 检索失败税nomy / 窗口复核等模式与判据；仓内无其源码复制。
- **open-code-review** — Apache-2.0
  - 仅调研其审计透镜/工单语义；k3dge 走的是 ADR-0006 sidecar + seal 人认领审计，不含其代码。
- **plugins-main** — MIT（root 与各 plugin package 均核）
  - 仅 clean-room 模式参考；排除其 `third_party/` 20 厂商连接器与市场基建。
- **codegraph** / **worktrunk** — MIT / Apache-2.0
  - 模式暨判据评估；未携源码进库。
- **gap-trap** — 权属同属 clean-room skill 对照；未粘代码。
- **WikiSkill** — Google Research 预印本（arXiv:2608.27454）
  - 论文思想借鉴（提案接受史/四组件/隔离实证）；无代码可粘，不涉许可。

## 版本/仓储

k3dge 本身以 `LICENSE`（MIT, Copyright 2026 Jamie Cheng）发布。贡献以同一 MIT 授权"约"遵循见 `CONTRIBUTING.md`。
