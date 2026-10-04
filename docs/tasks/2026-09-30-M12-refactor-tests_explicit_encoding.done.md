---
status: done
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


## 事实更正（本轮自查，AST 实测）

先前登记的两个数是**错的**：`271`（tests）与 `23`（src）来自一条按行粗扫的正则——它对
`write_text(json.dumps(...), encoding="utf-8")` 这类"编码关键字出现在第一个右括号之后"的写法
误判成缺 encoding。AST 复核后的真值：

- `tests/**.py`：**75 处** 真缺 `encoding`；
- `src/**.py`：**0 处**（生产侧本来就是干净的，先前那条"更正"把 0 改成了 23 反而是我把错数坐实了）。

## 本轮进展

- 已收口 **36/75**（AST 定位到调用自身的右括号后插 `encoding="utf-8"`；逐文件语法自校验＋全量 pytest 绿）。
- 剩 **39 处**（test_evaluator 30 / test_generator 6 / test_scaffold 3）：这几处的插入点会撞已有尾逗号或链式调用，脚本改坏语法即被自校验挡下 ⇒ 留人工。
- 已落防退化闸 `tests/unit/templates/test_test_explicit_encoding.py`：**棘轮**式（DEBT 记当前 3 文件的数量，只许降不许升；降了不改 DEBT 就红）。全部收口后删 DEBT ⇒ 零容忍。

## 事实（首版登记，含错数，见上「事实更正」）

- `tests/**.py`：`read_text()` / `write_text(...)` 未带 `encoding=` 的站点 **271 处**。
- `src/**.py`：同形 **23 处**（生产侧并未收干净；先例见已归档票 `docs/tasks/archive/M2/2026-08-26-M2-audit-N1_06_sync_domain_unicode.done.md`）。
- 后果只在**非 UTF-8 locale** 上显形：夹具里的中文/破折号（`布局`、`— do not edit`）按 locale 解码 ⇒ 跨环境假失败或假通过。本轮已按 OCR 测试扫描逐条收掉 4 处（t-139/303/326/331；报告里同类还有若干条待同一批收），剩下的属批量收口（含生产侧 23 处：那 23 处是**运行时真会读用户仓文件**的，优先级高于测试面），不该混在判读批次里做。

## 切入点

1. 一次性收口：`tests/**` 全部 `read_text()` / `write_text()` 补 `encoding="utf-8"`（**逐文件**改，多行调用要人工确认括号边界，不能一把 sed）。
2. 若嫌 271 处重复：给测试侧一个 `tests/helpers.py::write_ws(path, text)` / `read_ws(path)` helper，夹具统一走它——但 helper 本身要配"不得裸 read_text"的反向机检，否则只是把约定换个地方漂。
3. 反退化机检归 `k3dge check` 的 `test_pure_*` 同族守卫（AST 扫 `tests/**`，发现 `.read_text()/.write_text()` 无 `encoding` 关键字即 warn 档起步），别用散文叮嘱。

## 结案

- 落地：75 处全部收口（AST 定位每个调用**自身**的右括号后插 `encoding="utf-8"`；三种形状分别处理——
  有参/无参 `read_text()`、前一行已是尾逗号的多行调用）。反向机检以**测试内棘轮**落地
  （`tests/unit/templates/test_test_explicit_encoding.py`，DEBT 清空后为零容忍），没有新增 `check` 违规码：
  这条只约束测试树，进硬闸会把"新增违规码需三件套"的规矩用在没有消费者的地方。
- 验证：AST 复扫 `tests/**`＋`src/**` 隐式编码读写均为 **0**；`pytest -q` 922 passed, 2 skipped。
- 有意不做：切入点 2 的 `tests/helpers.py` 包一层——helper 只是把同一约定挪个地方漂，零容忍守卫已经覆盖。

## 回填（2026-10-04）

复验：`tests/unit/templates/test_test_explicit_encoding.py` 仍 `DEBT = {}`（零容忍）且 3 passed；
`## 本轮进展` 里的"剩 39 处"是过程快照，已被 `## 结案` 的"75/75 收口"取代，票面无需再动。

