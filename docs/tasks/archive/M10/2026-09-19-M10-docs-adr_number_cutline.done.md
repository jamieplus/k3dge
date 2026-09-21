---
status: done
milestone: M10
priority: P1
date: 2026-09-19
---

# ADR 编号截断：废物理删除、退役单一面 obsolete/、13 个永久退役号入表、分配=max+1、复用可机检

- **可检索摘要**: `Numbers are never reused` 是散文规则、闸瞄错靶，实测被违反 6 次（`0008 0009 0010 0022 0023 0026` 都是删后重发；本轮的 `0026-projection-contract` 是第 3 次占用 0026）。根因是规则自相打架：AUTHORING「先并入，后新建」明写被并者**物理删除**，而下游模板的分配规则是「本目录最大号 +1」⇒ 物理删除让退役号从目录消失，max+1 必然重发。修法（用户裁定 2026-09-19，方案 ①-⑥）：废物理删除、退役只走 `obsolete/`、13 个永久退役号一次性入 `obsolete/README.md` 的表（**不伪造墓碑文件**）、分配 = max over（`adr/` ∪ `obsolete/*.md` ∪ 该表）+1、`ADR_NUMBER_COLLISION` 扩到 obsolete/ + 读该表、**存量 6 个复用号不追**（口径同 ADR-0026 §2.5 不追溯存量）。

## Intent

编号的意义不是"连续"也不是"计数"，而是**一次分配、永久绑定一个决策**；空洞是特性（记录合并史），前提是空洞**有碑**。用户裁定：**之前没遵守的规则就此截断，之后按新规则**（baseline 语义），不重编号现役 ADR（那会打断全仓引用 + 下游仓继承的引用）。

## 证据（实测，git 全史）

```
曾被物理删除的 ADR 文件：24 个，涉及 19 个号
  0002 0003 0007 0008 0009 0010 0011 0013 0014 0015 0016 0019 0020 0021 0022 0023 0024 0026 0027
删后又被重新发出、现仍现役：0008 0009 0010 0022 0023 0026        ← 6 次违规
永久退役（删了没重发）：0002 0003 0007 0011 0013 0014 0015 0016 0019 0020 0021 0024 0027  ← 13 个
现存 14 条，最大号 0026；历史最大号 0027 ⇒ 下一个安全号 = 0028
0026 三次占用（git 实证）：
  4fe735c A 0026-audit-evidence-exchange-topology.md → 改名腾号 0024 → 并入 0025 §2.9
  11ecffd A 0026-mcp-workspace-root-confinement.md   → 并入 ADR-0006
  613288d A 0026-projection-contract.md              ← 本轮新增（现役，不迁号）
0027 亦退役：0027-hall-harness-topology.md 被删 → 即现役 0025
闸实况：ADR_NUMBER_COLLISION 只扫 docs/adr/*.md（glob 不递归，不含 obsolete/）
        AUTHORING 声称的机验码 ADR_FILENAME_MISMATCH 只查"文件名号 ↔ H1 号一致"
        ⇒ 「号是否被复用」目前无闸（已在 AUTHORING 明写，不假装有）
后果：docs/tasks/archive/M7/* 里的「ADR-0026（证据交换拓扑）」现指向另一条 ADR，
      而 DANGLING_ADR_REF 因"0026 文件存在"而放行 ⇒ 引用静默变错（比重号更常见）
```

## 方案（用户裁定 ①-⑥）

```
① baseline：以本次修订的 commit 为界，记在 AUTHORING 一行 + obsolete/README.md 表头
② baseline 之前的 13 个永久退役号：一次性写进 docs/adr/obsolete/README.md 的表
   （号 | 曾是 | 退役方式 | 去向）——**不重建 13 个墓碑文件**（那等于伪造正文内容）
③ baseline 之后：退役只有一条路 = 移入 obsolete/（frontmatter 写 merged-into / superseded-by）
   AUTHORING「被并者物理删除（git 留档）」改为「移入 obsolete/ 并记去向」
④ 分配：下一号 = max over (docs/adr/ ∪ obsolete/*.md ∪ ②的表) + 1；只增不减 ⇒ 天然不会重发
⑤ 闸：ADR_NUMBER_COLLISION 扫描面扩到 obsolete/ + 读②的表 ⇒ 复用从散文变机检；
   另加「引用指向退役号 ⇒ 提示去向」（治静默指错；pure_refs.check_dangling_adr 已会查
   obsolete/，所以老引用不会变悬空，缺的是"已退役 + 去向"这层提示）
⑥ 存量不追：6 个已复用号（含本轮 0026）保持现役、不迁号
```
配套：`docs/generated/docs-index.json` 加 `retired` 维度（`--include-retired`），**不新建第二个索引**；下游模板 `adr-readme.md.template` 的分配句已改（本轮 `8f75c04`），需与④同口径复核。

## 边界与拆分（规则 08）

- 事实归属：**退役事实**归 `docs/adr/obsolete/`（真文件 + README 表，单一面）；**分配规则**归 AUTHORING（散文）+ 闸（机检）；**索引**归 `docs-index.json`（投影，可重算）。
- 边界检查：不新建 `RETIRED.md` 之类第二账本（用户已指出与 `obsolete/` 冲突）；不换编码方案（随机/日期 id 治撞号不治老化，且迁移面含下游仓继承的引用）。
- 桩子先行：先落②的表 + ⑤的闸（表空/缺文件时闸必须绿，不误伤），再改 AUTHORING 与 reconcile 行为，最后补 docs-index 维度。

## 验收

退役号不得裸引（`DANGLING_ADR_REF` 会红），故验收命令放围栏内：

```
造一个复用号（如新建 docs/adr/0020-x.md）⇒ 闸红，且 message 指出去向（并入 0005 §2.7）
新建 0028-*.md                        ⇒ 绿（下一个安全号）
正文引用退役号 ADR-0020                ⇒ 提示“已退役，去向 0005 §2.7”，不再静默放行
```

- `obsolete/README.md` 表含 13 行 + baseline 行；
- 全量 pytest 绿；`k3dge check` 绿。
- **本票自己就踩了一次**（2026-09-19）：初稿在验收段裸引退役号，pre-commit 的 `DANGLING_ADR_REF` 当场拦下 ⇒ 证明现行闸能拦“指向不存在的号”，但拦不住“指向已退役但文件又存在的号”（如 0026）——后者正是⑤要补的。

## Notes

- 与 `adr_doc_normalize_strategy`（C1-C5）正交：那票管 doc 策略的 ADR 冲突，本票管编号系统本身。
- 与 `adr0026_d_line_and_downstream` 有交点：两票都要改 ADR 面，建议同轮落，避免 0026 被就地改两次。
- 本轮 0026 复用**不处置**（用户裁定"不管了，就此截断"）；本票的②表里如实记两次旧占用即可。

## 落地（2026-09-19，①-⑥ 全部执行）

| 项 | 落点 | 实测 |
| --- | --- | --- |
| ① baseline | `docs/adr/obsolete/README.md` 表头 + AUTHORING「编号分配」节 | baseline = 2026-09-19 / `f749e27` |
| ② 13 个永久退役号入表 | 同上（号 \| 曾是 \| 退役方式 \| 去向 \| 删除 commit），**未伪造墓碑文件** | `retired_adr_numbers()` 解析出 13 条，与 git 史一致 |
| ③ 废物理删除 | AUTHORING：退役只有一条路＝移入 `obsolete/` 并写去向；「先并入，后新建」里的"被并者物理删除"同步改口径（两处表述不得相抵） | 两份（仓 + 资产镜像）PAIRS ✓ |
| ④ 分配 = max+1 | AUTHORING 明写 max over（`adr/` ∪ `obsolete/*.md` ∪ 账本表）；下游模板句上一轮已改 | 历史最大号 0027 ⇒ 下一安全号 **0028** |
| ⑤ 闸 | 新码 `ADR_NUMBER_REUSE`（占用退役号）+ `ADR_REF_RETIRED`（引用退役号 ⇒ 给去向）；两码进 `gate_facts` 声明面（fact/options/pointers）；接线 hook + `doc_catalog.validate_docs` | 造 `0020-x.md` ⇒ 红并给出「去向 ADR-0005 §2.7」；`0028-y.md` ⇒ 绿 |
| ⑥ 存量不追 | 6 个已复用号（0008/0009/0010/0022/0023/0026）现役不迁号；「曾被复用的号」单独一张表记账，`_live_adr_numbers` 保证它们不被 `ADR_NUMBER_REUSE` 误伤 | `test_live_number_not_flagged_as_reuse` + 自举测试 |

### 边界裁定（实测后定的，不在原方案里）

`ADR_REF_RETIRED` **不扫 `docs/reviews/` 与 `archive/`**：那是 append-only 的审计/历史记录，引用的是"当时那条 ADR"，改写等于篡改当时的事实。实测依据：全仓非归档文档只有 2 处命中，都在 `docs/reviews/`（`2026-09-10-doc-audit-docs.md`、`2026-09-14-M10-audit.md`），且都是历史报告正文。

### 顺手修正 AUTHORING 的一处失准

旧文声称复用编号的机验码是 `ADR_FILENAME_MISMATCH`——它只查「文件名号 ↔ H1 号一致」，管不了复用。现已明写四个码各管什么（`ADR_NUMBER_REUSE` / `ADR_REF_RETIRED` / `ADR_FILENAME_MISMATCH` / `ADR_NUMBER_COLLISION`），并注明前者管不了复用是旧文的错。

## 验收（实测）

```
tests/unit/engine/test_pure_refs.py::TestAdrNumberRetirement（9 条）
  账本只读"永久退役号"段（"曾被复用"表的 0008 不混进来）
  占用退役号 ⇒ ADR_NUMBER_REUSE 且给去向 / 安全号 ⇒ 绿 / 现役号不误伤
  obsolete/ 里的真文件同样拦住复用（baseline 之后的退役路径）
  引用退役号 ⇒ ADR_REF_RETIRED 且给去向
  reviews/ 与 archive/ 不报（历史记录）
  自举：本仓账本 13 号、现役 14 条无一占用退役号
575 passed；k3dge check 绿；adr_landed / adrs_all_accepted 未退化
```

## 重开补漏（2026-09-19）：未做项已补

**漏项**：本票「方案」里的**配套**一句（`docs/generated/docs-index.json` 加 `retired` 维度 / `--include-retired`）在首次关票时**没做**。实测确认漏了：

```
docs/generated/docs-index.json 条目键 = [path, type, id, title, status, tokens]   ← 无 retired
obsolete/ 条目 0 条（账本 13 号没有墓碑文件）
$ k3dge doc where ADR-0020   →   [DOC] not found: ADR-0020
```

后果：退役 ADR 在**寻址面彻底隐身**——只有闸报错（`ADR_REF_RETIRED`）撞上时才知道它存在与去向。

**补法**（选择：可寻址优先，不动存盘投影）：

| 面 | 改法 | 实测 |
| --- | --- | --- |
| `iter_managed_files` | `obsolete/` 与 `archive/` 一样**默认排除**退役面；`include_retired=True` 时纳入 | — |
| `build_card` | `obsolete/` 里的文件标 `retired: True` + `dest`（读 frontmatter `merged-into`/`superseded_by`） | — |
| `retired_ledger_cards()` | 账本表 → 卡片（13 个无墓碑文件的号） | `doc where` 查原 0020 → 账本路径 + `（已退役）harness-responsibility-split` + 去向 `ADR-0005 §2.7` |
| `where_doc` | **默认含退役面**（可寻址优先）；现役命中则仍返现役 | 现役号 → 现役文件；退役号（如原 0013）→ 账本 |
| `list_docs` / CLI | 新增 `--include-retired`；默认列表**不含**退役面（现行视图不污染） | 默认 14 条，`--include-retired` 27 条（+13 账本） |
| **存盘投影** | `write_docs_index()` **保持现行视图**（不含退役面） | `DOC_INDEX_STALE` 语义不变；退役面按需查 |

**有意偏离票面**：票写的是"docs-index.json 加 retired 维度"，落地改为"**寻址面可查 + 存盘投影保持现行**"。理由：存盘投影是门禁的新鲜度判据（`DOC_INDEX_STALE` 比对其与重建结果），把退役面塞进去会让"现行视图"与"历史面"混在一份文件里；而"退役号不隐身"这个诉求由 `where`（默认含退役）+ `list --include-retired` 更直接地满足。

测试 5 条（`TestRetiredAdrVisibility`）：账本可解析到去向 / 现役 id 仍指向现役文件 / 默认列表不含退役而 `--include-retired` 多出 13 条 / **存盘投影保持现行** / `obsolete/` 文件标 `retired` 且带去向。
