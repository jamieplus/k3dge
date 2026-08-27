# 审计：Pass 2 架构与拓扑（依赖 DAG / ADR / 域纯度 / 文档边界）

- **Date**: 2026-08-25
- **基线**：`70 passed / 1 skipped / 44 subtests / k3dge check --with-tests PASS / 4 域契约已同步`
- **审计人**：Agent（Grok）Pass 2 单透镜 + 人复核
- **范围**：`.agent/manifest.json` `docs/architecture/overview.md` `docs/specs/*` `docs/adr/*` `src/k3dge/**` 导入
- **输入**：`docs/protocols/audit_default.md` 8 维「规范 + 架构」

## 发现

| ID | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P2-DAG-01 | 中 | P1 | 设计 | `engine` 运行时 `import templates.pairs`，与 overview「templates 孤岛」冲突。不是崩闸 | `evaluator.py:220` | 待修 | [tasks/2026-08-25-M1-audit-P2_DAG_01_engine_import_templates_DAG.md](../tasks/2026-08-25-M1-audit-P2_DAG_01_engine_import_templates_DAG.md)（并入 DAG-02、PUR-01/02、ADR-01、D-05、META-01） | `from k3dge.templates.pairs import PAIRS` |
| P2-DAG-02 | 低 | P2 | 规范 | overview 未写 version / TEMPLATE_DRIFT 两闸 | `overview.md` §2 | 待修 | 并入上条，改 overview 时补一句 | 文档落后 |
| P2-PUR-01 | 低 | P2 | 规范 | engine spec In Scope 未写 version/TEMPLATE_DRIFT | `docs/specs/engine/spec.md:9-15` | 待修 | 并入 P2-DAG-01 | 同 DAG |
| P2-PUR-02 | 低 | P2 | 规范 | 门禁读 templates 资产 vs Out of Scope | `engine/spec.md:16-19` | 待修 | 并入 P2-DAG-01 | 同 DAG |
| P2-PUR-03 | 低 | P2 | 规范 | sync spec 仍写 `architecture.md`，代码是 `domains.md` | `docs/specs/sync/spec.md` | 待修 | 并入 [P4-03](../tasks/2026-08-25-M1-audit-P4_03_TC_SYNC_02_generate_docs.md) | generator 写 domains.md |
| P2-PUR-04 | 低 | P3 | 冗余 | `render_readme_layout` 仍公开、sync_all 不再调用 | `sync/generator.py` | 有意留 | 有意留：generate-docs 仍调用。何时重开：该函数无任何调用方 | 公开符号；调用在 scripts |
| P2-PUR-05 | 低 | P2 | 规范 | cli spec In Scope 未列 task/doc/audit/version | `docs/specs/cli/spec.md` | 待修 | 并入 [P2-PUR-06](../tasks/2026-08-25-M1-audit-P2_PUR_06_k3dge_audit_triage_cli_ADR.md)：留/删 audit 时一并改 In Scope | 接口已含 cmd_* |
| P2-PUR-06 | 中 | P1 | 规范 | `k3dge audit triage` 违 ADR 0005 | `cli/main.py` `cmd_audit` | 待修 | [tasks/2026-08-25-M1-audit-P2_PUR_06_k3dge_audit_triage_cli_ADR.md](../tasks/2026-08-25-M1-audit-P2_PUR_06_k3dge_audit_triage_cli_ADR.md) | 命令存在 |
| P2-ADR-01 | 低 | P2 | 规范 | TEMPLATE_DRIFT 无独立 ADR | evaluator / pairs | 待修 | 并入 P2-DAG-01 | 锁已存在，缺 ADR |
| P2-META-01 | 低 | P3 | 规范 | manifest 引擎描述未写 milestone/version | `.agent/manifest.json` | 待修 | 并入 [P2-DAG-01](../tasks/2026-08-25-M1-audit-P2_DAG_01_engine_import_templates_DAG.md)：改 overview/spec 时顺手 | 描述字符串 |

> `DAG` 声明仅 `P2-DAG-01` 一处逆向，其余 `cli→engine` 等均验证通过；`templates` 零 `engine` 导入符合孤岛。

## 结论

Pass 2：2 条独立 M1 tasks（DAG-01 含文档/D-05/META-01 并入；PUR-06 含 PUR-05 In Scope）。其余并入或有意留（仅 PUR-04）。P2-DAG-01 降为 P1 设计债，不是 P0 崩闸。

## 验证

- `70 passed` 基线绿
- `grep -rn "from k3dge" src/k3dge` 验证 `DAG`
