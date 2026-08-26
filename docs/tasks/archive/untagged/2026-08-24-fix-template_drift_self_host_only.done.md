# TEMPLATE_DRIFT 只能锁自举仓，不能拿包装资产去卡下游

- **Status**: done
- **Priority**: P1
- **Date**: 2026-08-24
- **归档**: 2026-08-25 无 Milestone，人工迁入 `archive/untagged/`（不计入 align/seal）

## 已确认意图
G-01 要求 `k3dge check` 拦住本仓 assets↔文件漂移。实现用 `Path(__file__)` 取 **已安装 k3dge 包** 的 assets，去比 **当前 workspace** 的 `AGENTS.md` 等。自举仓（editable 同一份树）正确；下游 k3dit 会红。

实证：`cd k3dit && k3dge check` 现报 5 条 `TEMPLATE_DRIFT`（docs.toml / spec 模板 / tasks|memo|reviews README）。init 后改 AGENTS.md 也会永远红。这和 ADR 0008「用 k3dge 开发并列仓」相反。

## 方案
仅当 workspace 自己就是 k3dge 源树时比对，例如存在 `src/k3dge/templates/assets` 且与 `__file__` 指向同一棵树。下游仓跳过。`except Exception: pass` 改成记违规。补测：临时改 workspace `AGENTS.md` → 自举仓 check 红；无 `src/k3dge/templates` 的仓不红。

## 入口
- `src/k3dge/engine/evaluator.py` TEMPLATE_DRIFT 段
- `src/k3dge/templates/pairs.py`
- `tests/unit/engine/test_evaluator.py`

## 来源
核 G-01 修复时在 k3dit 复现。
