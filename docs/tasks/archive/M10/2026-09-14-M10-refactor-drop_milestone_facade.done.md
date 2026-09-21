---
status: done
milestone: M10
priority: P2
date: 2026-09-14
---

# 删除 engine.milestone 兼容门面，调用方直连叶子

- **可检索摘要**: 删除 `engine/milestone.py` re-export 桶；cli/tests 改直 import 叶子

## 已确认意图
门面无实现、engine 内部已不走它。删文件，CLI 与测试改直连叶子。归档 ADR/incident 里的旧路径不动。

## 边界与拆分
- 事实归属：各叶子模块已拥有符号；本票只拆掉 re-export 层。
- 边界检查：不改行为；不重写历史报告。
- 桩子先行：改 import → 删文件 → 测试。

## 结案

- 关闭提交：`ebaff64`（2026-09-18）
- 落地记录：见该提交 message 与本文正文（回填于 2026-09-19，事实取自 `git log --diff-filter=AR -1 -- <path>`）。
