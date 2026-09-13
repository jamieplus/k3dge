---
status: done
milestone: M9
priority: P2
date: 2026-09-12
---

# 硬闸/next 钩子/阈值 盘点与配置化

- **Status**: done
- **Milestone**: M9
- **Priority**: P2
- **可检索摘要**: 盘点散在代码里的闸/阈值/next 文案/钩子，区分"声明式数据"与"执行逻辑"，把前者收敛为配置文件。
- **Date**: 2026-09-12

## Intent

把可声明的阈值/开关/文案抽成配置，逻辑留代码；消除"改个阈值/文案要改源码"。

**本票即「硬闸契约」的落点**：所有 gate rule（含 `2026-09-12-M9-feat-seal_adr_gate` 的"封版 ADR 须 Accepted 且落地"）声明在**同一份契约**里，执行器按契约跑——**不再一条规则一个 ADR**（Core Maintainer 2026-09-11 定）。

## 上下文/切入点（初始盘点）

- `scripts/pre-commit:37-38`：`_CHECK_PREFIXES` / `_CHECK_SUFFIXES`（触发 check 的路径面）。
- `engine/audit_trigger.py:28-29`：`_C2_THRESHOLD=5`、`_VOLUME_THRESHOLD=8`。
- `engine/markers.py:51-52`：`_MAX_NOTE=80`、`_MAX_NOTE_PENDING=500`。
- `engine/search.py:20`：`_MAX_CONTEXT=3`。
- `.agent/pipeline.toml`：roles/peers/actions/transports（已是配置）+ `pipelines.on_seal_enter`/`on_pre_seal`。
- `engine/nextstep.py`：各 state 的 `ask`/`if_y`/`if_n`/`note` 文案（硬编码）。
- `engine/milestone.py`：seal 条件/动作（与 `seal_policy_config` 重叠，见该票）。
- `engine/evaluator.py`：gate 规则码（`MANIFEST_INVALID` 等）。
- 命令 stdout **默认上限**（渐进披露预算；来自 `next_hook_progressive_disclosure` 残余①）：各命令输出面的默认行/字节上限。
- 目标：新增/并入配置（拟 `.agent/gates.toml` 或并入 `pipeline.toml`），代码只做执行。

## 边界与拆分

- 事实归属：配置＝阈值/开关/文案的声明；引擎＝执行与判定逻辑。
- 边界检查：配置不承载逻辑（无脚本/表达式），避免长出第二套判定语言。
- 桩子先行：先出"清单 + 拟 schema"供评审，再分小步迁移；每步行为不变 + 测试。

## 收尾（2026-09-13 已落）
- 契约新增 `[markers]`（`max_note`/`max_note_pending`）与 `[output]`（`default_lines`）→ `gates.DEFAULTS` + `.agent/gates.toml`；`markers.parse_text` 增可选 caps，`extract` / `worktree.strip_pins` 从契约读；`status` 默认行数改读 `output.default_lines`。
- 修 `search` 二次 clamp：`_snippet_window` 改按调用方 cap（`search.context_max`）而非硬编 3，否则自定义阈值失效。
- **已配置盘点**：`audit_trigger`(c2/volume)、`search.context_max`、`markers.*`、`output.default_lines`、`[checks.seal|align]`。**仍留代码（有意）**：`nextstep` 各 state 文案（引导文本非阈值）、CLI argparse 派形状。
- 测试：`test_gates`（markers/output 缺省+覆盖）、`test_markers`（note cap 可配）。306 passed；check 绿。
- 注：本票并入了 stdout 预算（`next_hook` 残项），以 `[output].default_lines` 作最小落点；**全体命令**统一 stdout 预算仍属 `context_budget_metrics`。
