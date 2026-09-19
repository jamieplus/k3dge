---
status: idea
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
