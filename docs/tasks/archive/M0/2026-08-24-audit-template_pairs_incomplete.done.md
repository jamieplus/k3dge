# 脚手架双轨文件未全部入锁；architecture 模板仍是 k3dge 四域假图

- **Status**: done
- **Milestone**: M0
- **Priority**: P1
- **Date**: 2026-08-24

## 已确认意图
审计 G-03 / G-04。PAIRS 漏了 pre-commit / branches / memo / reviews readme（后两对已 DIFF）。architecture 模板不锁，init 下游得到本仓四域表。

## 方案
- 凡 `scaffold()` `_write_if_missing` 且内容应与本仓某文件字节一致的，全部进同一份配对表（与 G-01 共用）。
- `architecture.md.template`：不要复制 k3dge 域表。空 `domains` 时生成空表 + 指向 `.agent/manifest.json`；或写与 overview 解耦的下游专用骨架。本仓 overview 继续人写，不进 PAIRS。

## 入口
- `tests/unit/templates/test_template_sync.py`
- `src/k3dge/templates/assets/architecture.md.template`
- `src/k3dge/templates/scaffold.py`

## 来源
[docs/reviews/2026-08-24-scaffold-gate-lock.md](../reviews/2026-08-24-scaffold-gate-lock.md) G-03 / G-04
