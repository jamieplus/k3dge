# engine 运行时依赖 templates.pairs，与 overview 孤岛声明冲突

- **Status**: done
- **Milestone**: M1
- **Priority**: P1
- **Date**: 2026-08-25

## 已确认意图
`ConsistencyEngine.evaluate` 为 `TEMPLATE_DRIFT` 执行 `from k3dge.templates.pairs import PAIRS`。overview 写 `templates` 孤岛、engine 不依赖 templates。这是把脚手架锁放进门禁的代价，不是崩溃。不要拆第五域；二选一即可。

并入同一任务（不另开单）：
- P2-PUR-01 / P2-PUR-02：engine spec In/Out of Scope 与 TEMPLATE_DRIFT 对齐
- P2-DAG-02：overview 写明版本镜像 + 仅自举的脚手架漂移
- D-05：evaluate 四责合一，处理 DAG 时顺手把 PAIRS 检查放到不逆依赖的位置
- P2-ADR-01：若锁留在 engine，补 ADR；若锁挪到 cli 仅自举，也写进该 ADR
- P2-META-01：`.agent/manifest.json` engine 描述补 milestone/version

## 方案
优先：`PAIRS` 迁到 `engine`（或 `cli` 仅自举仓 `cmd_check` 调用），`templates` 再从那里引用，禁止 `engine → templates`。下游跳过逻辑保持。改公开符号则 `k3dge sync`。补测：`engine` 模块不 `import k3dge.templates`。

不采纳：为这个逆边做大重构拆 VersionGate 家族。

## 入口
- `src/k3dge/engine/evaluator.py`
- `src/k3dge/templates/pairs.py`
- `docs/architecture/overview.md` §2
- `docs/specs/engine/spec.md` In/Out of Scope

## 来源
[docs/reviews/2026-08-25-pass2-architecture-dag.md](../reviews/2026-08-25-pass2-architecture-dag.md) P2-DAG-01；Pass 3 D-05 并入
