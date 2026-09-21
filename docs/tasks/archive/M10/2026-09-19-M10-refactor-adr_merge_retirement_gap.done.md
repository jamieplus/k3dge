---
status: done
milestone: M10
priority: P3
date: 2026-09-19
---

# ADR 合并退役：reconcile 不覆盖合并路径 + obsolete/ 去向字段无闸（merged-into 无人写无人验）

- **可检索摘要**: AUTHORING 现在规定「退役只有一条路＝移入 `obsolete/` 并**写清去向**（`merged-into` / `superseded-by`）」，但机制只覆盖一半：`adr_gate.reconcile_supersedes` 自动处理 `Supersedes: ADR-Y`（标记 + `superseded_by` + 移入）与 `Status: Rejected`（直接移入），**唯独不覆盖"合并"**——而 13 个永久退役号里 **12 个是合并**（0002/0003/0007/0011/0013/0014/0015/0016/0019/0020/0021/0024），唯一非合并的是 0027（改名）。更关键的是：`merged-into` 字段**全仓只有读、没有写方，也没有闸验其存在**（`doc_catalog.build_card` 读它填 `dest`）⇒ baseline 之后的合并若忘了写去向，退役卡片会显示 `retired` 但 `dest` 为空，读者仍找不到"这条去哪了"——正是退役账本要修的那个失效模式。

## Intent

把"退役必带去向"从散文变成可检事实（AGENTS.md §12 末行：新增可机检规则须同轮配闸）。

## 证据（实测）

```
adr_gate.reconcile_supersedes 的 docstring（只两类）：
  1. `Supersedes: ADR-Y` → 标 Status: Superseded + superseded_by: ADR-X + 移入 obsolete/
  2. `Status: Rejected`  → 直接移入 obsolete/
  ⇒ 未提"合并"

13 个永久退役号的退役方式（账本表 docs/adr/obsolete/README.md）：
  合并 12 个：0002 0003 0007 0011 0013 0014 0015 0016 0019 0020 0021 0024
  改名腾号 1 个：0027

merged-into 的读写面（grep）：
  读：doc_catalog.py:146（build_card 填 retired 卡片的 dest）
  写：无（reconcile 只写 superseded_by）
  验：无（.schema.json 无该字段规则；无 code）
```

## 方案（两步，先闸后（可选）自动化）

```
① 闸 ADR_RETIRED_NO_DEST（本票必做）
   obsolete/*.md（**非** README、非 _template）必须能解析出去向，闭集三选一：
     merged-into: <宿主 ADR 与小节>       （合并）
     superseded_by: ADR-XXXX              （被取代）
     Status: Superseded + superseded_by   （同上，reconcile 的产物）
   解析不到 ⇒ 红，提示"退役必须写清去向（AUTHORING「编号分配/删除/改名」）"
   - 位置：pure_refs（零依赖，hook 与 doc_catalog 共用）+ 进 gate_facts 声明面
   - 例外：账本表（`obsolete/README.md`）本身不报——它承载的是 baseline 之前无墓碑文件
     的 13 个号，其去向在表里
② （可选）自动化合并路径：**暂不做**。合并的声明面不明确（历史上写在宿主 ADR 的 Note +
   commit message 里），造一个 `Absorbs: ADR-XX` 字段属新基建且无第二个消费者
   （规则 12：不单独扩基建）。若将来合并频繁到需要自动化，再按那时的事实设计。
```

## 边界与拆分（规则 08）

- 事实归属：**去向**归被并者文件的 frontmatter（写一次、随文件走）；**判定**（该不该合并）归 agent/人；闸只验"写了没写"。
- 边界检查：闸不判去向对不对（那要么读懂 ADR 内容，要么查引用；都不属形式层）；不引入新渲染面（复用 `gate_facts`）。
- 桩子先行：先落闸 + 3 条测试（缺去向红 / 三选一各绿 / 只有账本时绿），再考虑是否要迁移工具。

## 验收

- 临时仓造一个 `obsolete/` 里缺去向的 ADR 文件 ⇒ 红；三种写法各一 ⇒ 绿；
- 本仓现状（`obsolete/` 只有 README.md）⇒ 绿（无文件可验，不误伤）；
- 新码进 `gate_facts` 声明面（fact/options/pointers/fix=judgment）；
- 全量 pytest 绿；`k3dge check` 绿。

## Notes

- 来源：本轮「还剩哪些没做完」清单里我列的 D 项之一（"ADR 合并退役路径：既不自动移入 obsolete/，也没有闸验去向"）。
- 与 `adr_number_cutline`（已关）的关系：那票把"退役面"建起来了（账本 + 两个编号码），本票补"去向字段"这一格。
- 优先级 P3：baseline 之后还没有实际发生过合并退役（无存量受害）；它是**防未来**的闸。

## 落地（2026-09-19）

| 项 | 落点 | 说明 |
| --- | --- | --- |
| ① 闸 `ADR_RETIRED_NO_DEST` | `pure_refs.check_retired_adr_dest(rel, text)` + `gate_facts` 声明（fix=judgment, severity=block, 三条 options） | 零依赖层，hook 与 `doc_catalog` 共用 |
| 合法形态（闭集） | `merged-into:` / `superseded_by:` / `Status: Rejected` | 加 `Rejected` 的理由：提议被否＝"从未生效"即其去向，无需指针（否则它会永远红）。**空值不算写了**（`merged-into:` 空 ⇒ 仍红） |
| 接线 hook | `scripts/pre-commit` 与其它 ADR 检查同处 `_add()` | staged 文件 |
| 接线仓库级 | `doc_catalog.validate_docs` | 退役面不在 `iter_managed_files` 默认视图里 ⇒ **显式扫 `obsolete/*.md`** |
| AUTHORING（两份，PAIRS） | 「编号分配/删除/改名」枚举补 `Status: Rejected` + 记闸码；并写明"合并没有自动化，故用闸兜住" | — |
| ② 自动化合并路径 | **不做**（票内已记理由：合并的声明面不明确，造 `Absorbs:` 属新基建且无第二消费者，规则 12） | — |

### 途中被自家测试抓到一处真缺陷（已修）

初版把 obsolete 扫描放在 `validate_docs` 的 schema 检查**之后** ⇒ 该类型缺 `.schema.json` 时
`if not schema: continue` 会**把闸一起跳过**。测试 `TestRetiredDestRepoWideWiring` 用无 schema 的
临时仓复现，据此把扫描移出 schema 依赖路径（放在类型循环之外）。教训：**闸不该因为同类型的
其它配置缺失而静默失效**。

## 验收（实测）

```
tests/unit/engine/test_pure_refs.py::TestRetiredAdrDest（5 条）
  缺去向 ⇒ 红且提示里列出合法形态 / 三选一各绿 / 空值不算写了 / 账本与模板不报 /
  非 obsolete 不报 / 自举：本仓 obsolete/ 现状绿
tests/…::TestRetiredDestRepoWideWiring（1 条）
  仓库级 `validate_docs(types=["adr"])` 真报 obsolete 缺去向；补上后绿（**接线证明**）

600 passed；`k3dge check` 绿；adr 面（adr_landed / 编号闸）未退化
```
