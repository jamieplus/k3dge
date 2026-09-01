---
Status: Accepted
Date: 2026-08-24
Deciders: Core Maintainer
---

# ADR-0005: 本地自用、职责切分、审计独立 harness

## 1. 上下文 (Context)
k3dge 先在本仓自用，不按 PyPI 发行假设设计（阶段定义见 ADR-0007：自举开发）。同时收口六处未定设计：安装源、engine/cli 职责、契约覆盖面、封板证据、guides 桩与 seal 互打、审计透镜位置。

## 2. 决策 (Decision)

### 2.1 本地自用（原 tasks/0001）
`k3dge-init` 的 **TARGET 永远是当前工作目录**（pwd），脚手架目录由 `scaffold` 生成，不要手建 `docs/` / `.agent/`。

- 在 k3dge 仓内 `./k3dge-init.sh`（cwd 为本仓）：自举，`pip install -e ".[dev]"`。**默认 `k3dge check` 行为未改**（仍要 git、仍只验触及域；`force_full` 仅 align / 显式旗标）。
- 在空项目目录里执行 **k3dge 仓里的** init：`cd k3dit && /path/to/k3dge/k3dge-init.sh`（脚本在 k3dge 检出里，能发现 `src/k3dge`）。
- 项目里已有拷贝的 `./k3dge-init.sh` 且不是 k3dge 仓：必须 `K3DGE_SOURCE=/path/to/k3dge`。
不依赖 PyPI。

### 2.2 职责（有完整方案，本轮落地）
- **engine 双责写死，不拆第五域**：`ConsistencyEngine` = 纯判定（`GateReport`）；`milestone` = 生命周期副作用（写 reviews、搬 tasks）。align 的 Full Matrix **调用** `evaluate(run_tests=True, force_full=True)`，禁止再复制一套 L2。
- **cli = 传输层**（细化见 ADR-0006）：`main` = 本仓终端/CI；`mcp` = 外部 harness（DSH / Codex / Claude Code / OpenCode）注入面。不新建 mcp 域。
- **L2 执行集 = `manifest.domains.*.tests` 目录**。Verification Matrix 只保证所列 `tests/...` 文件存在（及跨域标注）；不单独当 pytest 路径清单。check 与 align 同一收集规则。

### 2.3 契约范围
L1 锁的是 **Python 模块顶层公开函数/类签名**（含白名单装饰器）。明确不覆盖：`__init__.py`、嵌套 class、动态 `__all__`、函数体/注释。TypeScript 是可选 extra、尽力而为，与 Python 不同严格度。

### 2.4 封板证据
- Status 只校验枚举 `{idea, deferred, in-progress, done}` 与终态 `done`，**不验状态边**（`idea → done` 合法）。
- align 写入 `<!-- k3dge:align-stub -->` 与 `<!-- k3dge:align-pass:<id> -->`。seal 拒绝仍含 stub 的文件；**必须**含对应 id 的 align-pass（证明文件由 align 产出，不是手写空壳）。
- 填验收 = 去掉 stub、保留 align-pass、勾选/改结论由人负责，机器不解析勾选语义。

### 2.5 guides 桩
seal 只拦 `docs/guides/*.md` 里的 `<!-- k3dge:guide-stub -->`。`generate-docs` 写该标记，不再写通用 `<!-- TODO -->`。正文里的 TODO 不挡封板。

### 2.6 审计独立 harness
透镜规程不进 `src/k3dge`、不加 `k3dge audit`。`docs/protocols/audit_default.md` 与 `verify_default.md` 只作 `.agent/pipeline.toml` 的 manual fallback（存在性由 `PIPELINE_PROTOCOL_NOT_FOUND` 校验，ADR-0019）。12 列报告与 `check-report` 在 k3dit。k3dge 只留 `docs/reviews/` 槽位与 seal 证据。MCP `k3dge_5pass_audit_prompt` 只指路，优先 `../k3dit/docs/guides/protocol.md`。

## 3. 产生后果 (Consequences)
- **正**：本仓可直接 `./k3dge-init.sh`；align/check 测集不再分叉；封板无法用任意 md 冒充 align 产物；审计与一致性门禁解耦。
- **负**：下游未设 `K3DGE_SOURCE` 时 editable 装的是下游自己；拆第五域的诉求被否决直到里程碑副作用再膨胀。
