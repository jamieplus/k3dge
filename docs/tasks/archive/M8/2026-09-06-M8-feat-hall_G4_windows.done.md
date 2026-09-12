---
status: done
milestone: M8
priority: P2
date: 2026-09-06
---

# G4: 窗版工单 + 工具事实注入 + 复核声明模型

- **Status**: done
- **Milestone**: M8
- **Priority**: P2
- **可检索摘要**: claim 按窗分版（代码窗=透镜对口、复核窗=对照面+账本、价值窗=注入 k3lity 扫描事实）；Hall 先跑确定性扫描/可达性、事实落窗目录（席不重算）；复核窗补机读声明模型（rounds 状态机+时序），否则 conformance 无从谈起
- **Date**: 2026-09-06

## Intent

窗口从"通用审计席"变成 4 种专业席；工具面从"按需跑"变成"Hall 预计算注入"。

## Notes

- claim 分版：4 窗各一版 instruction（对口 audit-method.md 窗口对口表）。
- 注入管线：Hall 在 claim 前跑 k3lity 扫描 + blocking 环/状态机可达性（stdlib graphlib），结果文件落窗目录；席只消费。
- 边表抽取器（DeepTutor 吸收条目 1）：import 图边表 `import_graph()`（洁净室自 DeepTutor `scripts/check_architecture.py`，Apache-2.0：ast.walk 全量扫含函数内 import + 相对导入解析，stdlib 零依赖），喂 SCC/拓扑序；是注入管线的前置事实源，随本 task 落地。
- 声明模型：`state-machine.yaml`（rounds 状态 + 允许跃迁 + 时序不可逆声明），复核窗 conformance 的对照物；放审计模块内，版本随账本盖章。
- 反例/边界击穿是代码审计窗方法选项，不单独立项。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：instruction 文本属审计模块；扫描事实属工具面；声明模型属审计模块（版本化）。
- 边界检查：席不重算工具事实（读目录即可）；Hall 不判事实含义。
- 桩子先行：声明模型先有 JSON schema + 单测（非法跃迁 fixture 被拒）；注入管线用 dummy 席验证"目录里有事实文件"。
- 承载 industry memo ②③的工具半：覆盖率/测试分层扩展 + RCA 留痕工具随本 task 工具面落地（判断半已在 protocol 方法论）。

## Related

- `docs/adr/0025-hall-harness-topology.md`（§2.2 四判读窗；复核窗对照物=声明模型）
- `docs/memo/2026-09-05-industry-benchmark-vs-4-harness.md`（§3.2 四缺项归属：②③工具半归本 task）
- `docs/memo/2026-09-06-deeptutor-absorption-eval.md`（条目 1 边表抽取器，随本 task 落地）
- `2026-09-06-M8-feat-hall_G1_merge.md`（前置：工具代码已搬入）
