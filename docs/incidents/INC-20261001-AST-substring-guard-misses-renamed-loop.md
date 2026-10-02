---
type: AST
severity: P2
status: closed
---

# Incident: 子串式结构守卫被变量名绕过——docstring 宣称"循环只在 nodes.run_phase"，而 seal.py 的分派循环一直绿着

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为 (Baseline)**：`tests/unit/engine/test_nodes.py::TestRepoRegistriesUseTheSingleExecutor`
  的 docstring 宣称 `for … in gates.preconditions/actions` 的循环"只出现在 nodes.run_phase"，
  守卫的职责就是逼这条成立（ADR-0012：守卫是判据，不是散文）。
- **现存破损 (Treatment)**：守卫用**三个写死的子串**（`for _gid in gates.preconditions`、
  `for aid in gates.actions`、`for _aid in gates.actions`）比对三个写死的文件。真实代码是
  `src/k3dge/engine/seal.py:286` 的 `for gid in gates.preconditions(workspace, "seal")`
  （变量名 `gid`，非 `_gid`）⇒ 模式不匹配，守卫恒绿。本仓扫描报告 t-200 指出该宣称"already
  false"，复算坐实：旧模式集合对当前主干命中 0，而 AST 走全仓命中 3 个站点
  （`nodes.run_phase`、`nodes.satisfied_ids`、`seal.seal_checklist`）。
- **复现路径**：
  ```bash
  grep -rn 'for gid in gates.preconditions\|for aid in gates.actions\|for _aid in gates.actions' src/k3dge
  # 旧守卫的任一模式对 seal.py:286 都不命中（变量名/下划线前缀一变即绕过）
  ```

## 2. 根因剖析 (5 Whys)

1. 为什么漏？守卫按"我当年写下这三行时的原文"匹配，不是按"迭代的**来源**是 gates.preconditions/actions"匹配。
2. 为什么会写成子串？先有退役动作（seal 执行器改走 run_phase），守卫是"证明改动完成"的一次性快照，被当作长期不变量留下来。
3. 为什么恒绿没人发现？子串守卫**正向不验证**：它只断言"没搜到"，不检查任何东西真的存在；`seal_checklist` 的循环是只读全量投影，语义不同所以从不打算被删——但守卫没登记这个豁免，读的人只能信 docstring 的假话。
4. 为什么文件列表也危险？写死 3 个文件 ⇒ 把循环**搬去第 4 个文件**即静默缩掉覆盖面；文件改名则守卫以 `FileNotFoundError` 报错（error 不是 failure）。
5. 深层：同一类错误本仓已记过一笔（INC-20260930-DOCS：恒真的取证命令）——"外壳像验证、判据与被验事实无关"。

## 3. 防退化动作清单

- 守卫改为 **AST 走 `src/k3dge` 全包**：For 与 comprehension 的迭代对象是 `gates.preconditions/actions`
  的直接调用、或绑过其返回值的变量 ⇒ 都算站点；变量改名/折行/换文件不再绕过。
- 豁免以 **(模块, 函数) 白名单**显式登记（含 `seal.seal_checklist` 及其"全量投影、非执行"理由），
  新增站点必须过审写进白名单，不再是"没搜到＝对"。
- 加**正向检查**：`("engine/nodes.py", "run_phase")` 必须仍在站点集里——守卫瞎了先红。
- 落点：`tests/unit/engine/test_nodes.py::TestRepoRegistriesUseTheSingleExecutor`；
  报告回填：`docs/reviews/2026-09-30-M11-ocr-tests-scan.md` t-194..t-205（11 行）。

## 4. 经验灌入

- 结构守卫的判据必须与被验事实**同形**（这里＝"谁在迭代闸列表"），与写下守卫那天的排版无关；
  用 AST/词法判据代替当年那行的子串。
- 凡"负向断言 + 固定文件清单"的守卫，配一条正向存在性检查；豁免要成为**声明**（白名单+理由），
  不靠模式碰巧搜不到。
