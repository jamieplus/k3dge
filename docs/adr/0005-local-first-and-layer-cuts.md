---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-08-24
Deciders: Core Maintainer
Note: ① 就地修订（补 VCS 源形态）2026-09-05，经 Core Maintainer 本轮显式授权（「resource 指向 GitHub」指令），依 `docs/adr/AUTHORING.md`。
      ② 就地修订（L2 矩阵语义对齐 ADR-0001：矩阵行可解析到具体测试，原"只保证文件存在"句作废）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径 = manual fallback（实测 `command -v k3dit`/`k3dge` 无输出，no live lens）。
      ③ 正交去重（seal 闸/L2/审计 harness 复述改指 0001/0004/0006/0017/0019）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径同上。
      ④ 就地修订（`k3dge audit` 口径：透镜不进 k3dge ≠ 审计线消费侧 CLI；原句作废）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径同上。
      ⑤ 去 changelog 化（删「（2026-09-05 就地补记）」与「原句作废」元叙述）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径同上。
      ⑥ 人读化改写（按 AUTHORING「人读优先」：决策先行、一行一点、长条拆子项；不变量与编号不变）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径同上。
---

# ADR-0005: 本地自用、职责切分、审计独立 harness

## 1. 上下文 (Context)
k3dge 先在本仓自用，不按 PyPI 发行假设设计；自举开发的阶段定义见 ADR-0007。
同时定下六处未定设计：安装源、engine/cli 职责、契约覆盖面、封板证据、guides 桩与 seal 互打、审计透镜位置。

## 2. 决策 (Decision)

### 2.1 本地自用（原 tasks/0001）
`k3dge-init` 的 **TARGET 永远是当前工作目录**（pwd）；脚手架目录由 `scaffold` 生成，不要手建 `docs/` / `.agent/`。

- 在 k3dge 仓内执行 `./k3dge-init.sh`（cwd 为本仓）：自举，`pip install -e ".[dev]"`。
  - **默认 `k3dge check` 行为未改**：仍要 git、仍只验触及域；`force_full` 仅 align / 显式旗标。
- 在空项目目录里执行 **k3dge 仓里的** init：`cd k3dit && /path/to/k3dge/k3dge-init.sh`。
  - 脚本在 k3dge 检出里，能发现 `src/k3dge`。
- 项目里已有拷贝的 `./k3dge-init.sh` 且不是 k3dge 仓：必须 `K3DGE_SOURCE=/path/to/k3dge`。
- `K3DGE_SOURCE` 亦接受 VCS 直引（`git+https://…`，非 editable）与保留词 `pypi`；本地路径仍是开发默认。
不依赖 PyPI。

### 2.2 职责（有完整方案，本轮落地）
- **engine 双责写死，不拆第五域**。
  - `ConsistencyEngine` = 纯判定（`GateReport`）；`milestone` = 生命周期副作用（写 reviews、搬 tasks）。
  - align 的 Full Matrix **调用** `evaluate(run_tests=True, force_full=True)`，禁止再复制一套 L2。
- **cli = 传输层**，细化见 ADR-0006。
  - `main` = 本仓终端/CI；`mcp` = 外部 harness（DSH / Codex / Claude Code / OpenCode）注入面。
  - 不新建 mcp 域。
- **L2 执行集 = `manifest.domains.*.tests` 目录**；check 与 align 同一收集规则。
- 矩阵语义（行可解析到具体测试、文件在场景不在即红）见 ADR-0001 §2.2。

### 2.3 契约范围
L1 锁的是 **Python 模块顶层公开函数/类签名**（含白名单装饰器）。
明确不覆盖：`__init__.py`、嵌套 class、动态 `__all__`、函数体/注释。
TypeScript 是可选 extra、尽力而为，与 Python 不同严格度。

### 2.4 封板证据
- Status 只校验枚举 `{idea, deferred, in-progress, done}` 与终态 `done`，**不验状态边**（`idea → done` 合法）。
- align 写入 `<!-- k3dge:align-stub -->` 与 `<!-- k3dge:align-pass:<id> -->`。
- seal 闸条件：拒 stub、必须对应 id 的 align-pass；见 ADR-0004 §2.1.3。
- 填验收 = 去掉 stub、保留 align-pass、勾选/改结论由人（维护者）负责，机器不解析勾选语义。

### 2.5 guides 桩
`generate-docs` 写 `<!-- k3dge:guide-stub -->`，不再写通用 `<!-- TODO -->`；正文 TODO 不挡封板。
seal 只拦该标记，闸条件见 ADR-0004 §2.1.3。

### 2.6 审计独立 harness
**透镜规程不进 `src/k3dge`**：不做审计判断、不发透镜。
`k3dge audit` 子命令指**审计线在消费侧的线管理**（submit/status/show/advance/materialize/close），不是透镜。
细则见 ADR-0024 §2.2。
协议兜底与传输细节见 ADR-0006 §2.2/§2.3、ADR-0019 §2.3；报告 schema 见 ADR-0017。
k3dge 只留 `docs/reviews/` 槽位与 seal 证据；MCP `k3dge_5pass_audit_prompt` 只指路，不演进规程。

## 3. 产生后果 (Consequences)
- **正**：本仓可直接 `./k3dge-init.sh`；align/check 测集不再分叉；封板无法用任意 md 冒充 align 产物；审计与一致性门禁解耦。
- **负**：下游未设 `K3DGE_SOURCE` 时 editable 装的是下游自己；拆第五域的诉求被否决直到里程碑副作用再膨胀。
