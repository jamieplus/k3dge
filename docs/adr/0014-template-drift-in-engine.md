---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-08-25
Deciders: Core Maintainer
Note: ① 就地修订（`k3dge audit` 口径：原"不加 k3dge audit / 已删子命令"句作废，改指 ADR-0024 §2.2 审计线 CLI）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径 = manual fallback（实测 `command -v k3dit` 无输出，no live lens）。
      ② 去 changelog 化（删「原句作废」元叙述）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径同上。
      ③ 人读化改写（按 AUTHORING「人读优先」：决策先行、一行一点、长条拆子项；不变量与编号不变）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径同上。
---

# ADR-0014: TEMPLATE_DRIFT 锁在 engine，不 import templates

## 1. 上下文 (Context)
自举仓要把 `templates/assets` 与本仓成对文件字节锁进 `k3dge check`（G-01）。
实现曾在 `ConsistencyEngine.evaluate` 里 `from k3dge.templates.pairs import PAIRS`。
该写法与 overview「templates 孤岛、engine 不依赖 templates」冲突（P2-DAG-01）。
下游仓必须跳过，否则包装资产会误拦（G-01 后半）。

## 2. 决策 (Decision)

1. **`PAIRS` 登记表属于 engine**（`src/k3dge/engine/pairs.py`）。
   - `evaluate` 只从本域 import。
   - 禁止 `engine → k3dge.templates`。
2. **比对的是磁盘上的 `templates/assets` 文件**，不是 templates 包的运行时 API。
   - 自举判定仍是：assets 路径相对本 workspace，或 workspace 内存在 `src/k3dge/templates/assets`。
   - 下游（k3dit 等）跳过。
3. **templates 仍是脚手架孤岛**：`scaffold` 不读 `engine.pairs`。
   - `tests/unit/templates/test_template_sync.py` 可以 import `k3dge.engine.pairs`；测试不是域运行时依赖。
4. **不拆第五域**，不把 TEMPLATE_DRIFT 挪到仅 `cli.cmd_check`。
   - MCP check 与 `milestone align` 都走 `evaluate`，必须同一把锁。
5. **不加审计透镜**（ADR-0005 维持）。
   - `k3dge audit` 是审计线消费侧 CLI，不是透镜，不改变本条的 engine 锁；见 ADR-0024 §2.2。

## 3. 产生后果 (Consequences)

- **正**：DAG 与 overview 一致；自举锁仍在所有 `evaluate` 入口。
- **负**：`pairs.py` 从 templates 目录搬走后，改脚手架成对物的维护者要记得改 `engine/pairs.py`。
- **何时重开**：templates 需要在运行时读 PAIRS（例如 scaffold 按表拷贝）且不能依赖 engine 时，把登记表再抽到两边都能 import 的无依赖模块。
  - 仍禁止 engine import templates。
