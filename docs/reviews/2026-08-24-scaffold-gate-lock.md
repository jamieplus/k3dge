# 审计：脚手架与本仓对齐后「门控要能拦住」

- **Date**: 2026-08-24
- **基线**：`test_template_sync` 2 passed / 32 subtests；`k3dge check` 与 `k3dge check --with-tests` 均 PASS（touched: cli, engine, templates）
- **审计人**：Agent（Grok）按 `docs/protocols/audit_default.md`。只审这次为「下游脚手架 vs 本体未对齐而 check 不红」做的修改，不重开 §5.1。
- **改了什么（产物）**：
  - `tests/unit/templates/test_template_sync.py` `PAIRS` 增 `docs.toml` / `_template/spec.md` / `docs/tasks/README.md`
  - `scaffold.py` 不再创建 `docs/log/`（与 CLI 写 `logs/k3dge.log` 对齐）
  - 未改 `evaluator.py` 的域路由，未改 pre-commit 入口
- **结论**：pytest 锁加长了，**`k3dge check` 作为门控仍拦不住「只改本仓、不改 assets」**。原问题只修了一半。
- **回记**：G-03/G-04 已修。G-01/G-02 在**本仓**已进 `evaluate()`（`TEMPLATE_DRIFT`，不依赖 touched）。同一段逻辑在 **k3dit 误红**（比的是包装资产 vs 下游文件）。见 [tasks/2026-08-24-template-drift-self-host-only.md](../tasks/2026-08-24-template-drift-self-host-only.md)。

## 发现

| ID | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G-01 | 高 | P1 | 缺陷 | 对齐锁只在 pytest，check 不比 assets | `evaluator.py` 无 TEMPLATE 比对 | 部分修 | 本仓 `evaluate()` 总是跑 `TEMPLATE_DRIFT`。下游被误伤，转 [tasks/2026-08-24-template-drift-self-host-only.md](../tasks/2026-08-24-template-drift-self-host-only.md) | 本仓 check 绿；`cd k3dit && k3dge check` 5 条 TEMPLATE_DRIFT |
| G-02 | 高 | P1 | 缺陷 | 只改目标文件不标 templates，`--with-tests` 也不跑锁 | `evaluator.py` 域路由 | 已修 | 比对不依赖 touched | 代码注释「总是运行，不依赖 touched」 |
| G-03 | 中 | P1 | 规范 | PAIRS 漏 pre-commit/branches/memo/reviews | `pairs.py` | 已修 | 四对入 `k3dge.templates.pairs.PAIRS`，测试与 check 共用 | 本仓 21 对全部 SAME |
| G-04 | 中 | P1 | 设计 | architecture 模板是 k3dge 四域假图 | `architecture.md.template` | 已修 | 空表示例行 + 「不要复制四域」；不进 PAIRS | 模板域表为 `_示例_` / `src/<domain>` |

## 各轮

- **Pass 1**：无注入。删 `docs/log` 与写盘路径 `logs/k3dge.log` 一致，无半删除回滚问题。
- **Pass 2**：把「本仓 vs 脚手架」一致性放在 templates 的 **L2 测试**，而问题要的是 **门控**（engine `evaluate`）。层放错了。CI `pytest -q` 不是 `k3dge check`。
- **Pass 3**：PAIRS 与 scaffold 写出清单是两份手维护列表，无单一注册表，会再漏。
- **Pass 4**：没有「只改 AGENTS.md 则 check 必须红」的用例。现有测试只证明「当前工作区已经对齐」。
- **Pass 5**：比对是整文件字符串，资产少，无性能问题。

## 不重开

A-11 / S-13 / F-14 / F-15 / R3-1 / R3-4。architecture 三处域表（R3-1）是本仓 overview/README/reference，不是下游模板。
