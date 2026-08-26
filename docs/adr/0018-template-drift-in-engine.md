# ADR 0018: TEMPLATE_DRIFT 锁在 engine，不 import templates

- **Status**: Accepted
- **Date**: 2026-08-25
- **Deciders**: Core Maintainer

## 1. 上下文 (Context)
自举仓要把 `templates/assets` 与本仓成对文件字节锁进 `k3dge check`（G-01）。实现曾在 `ConsistencyEngine.evaluate` 里 `from k3dge.templates.pairs import PAIRS`，与 overview「templates 孤岛、engine 不依赖 templates」冲突（P2-DAG-01）。下游仓必须跳过，否则包装资产会误拦（G-01 后半）。

## 2. 决策 (Decision)

1. **`PAIRS` 登记表属于 engine**（`src/k3dge/engine/pairs.py`）。`evaluate` 只从本域 import。禁止 `engine → k3dge.templates`。
2. **比对的是磁盘上的 `templates/assets` 文件**，不是 templates 包的运行时 API。自举判定仍是：assets 路径相对本 workspace，或 workspace 内存在 `src/k3dge/templates/assets`。下游（k3dit 等）跳过。
3. **templates 仍是脚手架孤岛**：`scaffold` 不读 `engine.pairs`。`tests/unit/templates/test_template_sync.py` 可以 import `k3dge.engine.pairs`（测试不是域运行时依赖）。
4. **不拆第五域**，不把 TEMPLATE_DRIFT 挪到仅 `cli.cmd_check`（MCP check 与 `milestone align` 都走 `evaluate`，必须同一把锁）。
5. **不加 `k3dge audit`**（ADR 0005 维持）。cli 已删 `audit` 子命令；透镜在 k3dit / memo。

## 3. 后果 (Consequences)

- **正**：DAG 与 overview 一致；自举锁仍在所有 `evaluate` 入口。
- **负**：`pairs.py` 从 templates 目录搬走后，改脚手架成对物的人要记得改 `engine/pairs.py`。
- **何时重开**：templates 需要在运行时读 PAIRS（例如 scaffold 按表拷贝）且不能依赖 engine 时，把登记表再抽到两边都能 import 的无依赖模块——仍禁止 engine import templates。
