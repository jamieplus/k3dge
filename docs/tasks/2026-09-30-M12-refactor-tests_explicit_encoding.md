---
status: idea
milestone: M12
priority: P3
date: 2026-09-30
---

# 测试面的显式编码：read_text/write_text 缺 encoding 的 271 处统一收口（连同一次性 helper）


## 已确认意图
测试面的显式编码：read_text/write_text 缺 encoding 的 271 处统一收口（连同一次性 helper）

## 可检索摘要
测试面的显式编码：read_text/write_text 缺 encoding 的 271 处统一收口（连同一次性 helper）

## 上下文/切入点
测试面的显式编码：read_text/write_text 缺 encoding 的 271 处统一收口（连同一次性 helper）

## 事实（本轮实测，非估算）

- `tests/**.py`：`read_text()` / `write_text(...)` 未带 `encoding=` 的站点 **271 处**。
- `src/**.py`：同形 **23 处**（生产侧并未收干净；先例见已归档票 `docs/tasks/archive/M2/2026-08-26-M2-audit-N1_06_sync_domain_unicode.done.md`）。
- 后果只在**非 UTF-8 locale** 上显形：夹具里的中文/破折号（`布局`、`— do not edit`）按 locale 解码 ⇒ 跨环境假失败或假通过。本轮已按 OCR 测试扫描逐条收掉 4 处（t-139/303/326/331；报告里同类还有若干条待同一批收），剩下的属批量收口（含生产侧 23 处：那 23 处是**运行时真会读用户仓文件**的，优先级高于测试面），不该混在判读批次里做。

## 切入点

1. 一次性收口：`tests/**` 全部 `read_text()` / `write_text()` 补 `encoding="utf-8"`（**逐文件**改，多行调用要人工确认括号边界，不能一把 sed）。
2. 若嫌 271 处重复：给测试侧一个 `tests/helpers.py::write_ws(path, text)` / `read_ws(path)` helper，夹具统一走它——但 helper 本身要配"不得裸 read_text"的反向机检，否则只是把约定换个地方漂。
3. 反退化机检归 `k3dge check` 的 `test_pure_*` 同族守卫（AST 扫 `tests/**`，发现 `.read_text()/.write_text()` 无 `encoding` 关键字即 warn 档起步），别用散文叮嘱。

