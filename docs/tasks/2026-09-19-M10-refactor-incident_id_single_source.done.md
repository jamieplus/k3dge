---
status: done
milestone: M10
priority: P3
date: 2026-09-19
---

# incidents frontmatter id 双写收成单一源（文件名）

- **可检索摘要**: `docs/incidents/*.md` 同时把身份写在两处：文件名 `INC-YYYYMMDD-TYPE-slug.md` 与 frontmatter `id: INC-YYYYMMDD-TYPE-slug`。实测**没有任何消费者读 frontmatter 的 id**——`doc_catalog._card_id()` 对 incidents 直接用 `path.stem`；`docs/incidents/.schema.json` 的 `frontmatter` 段根本没有 `id` 规则（只查 filename/h1/sections）⇒ 两处漂移**无人发现**。与 tasks 的正文 `- **Status**:` 副本同类（那批已收：`TASK_BODY_META_REDUNDANT` + 31 张票迁移）。修法：移除 frontmatter `id`（单一源＝文件名）+ 冗余即红的棘轮；存量 12 份机械迁移。

## Intent

单一源原则的一致性：一个事实只在一处写。tasks 收了、ADR 编号收了（`ADR_NUMBER_REUSE`），incidents 这一对留着就是例外。

## 证据（实测）

```
文件数：docs/incidents/ 12 份真文件（另有 _template.md / AUTHORING.md 两个 aux）
消费者：grep -rn "incidents" doc_catalog.py → 只有 _card_id：
          if typ == "incidents": return path.stem        ← 用文件名，不读 frontmatter id
        .schema.json（docs/incidents/）键 = [filename, h1, sections, codes]
          → frontmatter 无 id 规则 ⇒ id 写错/漂移不会被任何闸发现
反例对照（已收）：tasks 的正文 Status 行 ⇒ TASK_BODY_META_REDUNDANT（commit f6ddaca），
        31 张存量票一次性迁移（幂等脚本，第二遍零 diff）
判断：这是"第二源只能漂移且无人验"，与本轮刚立的单一源原则不一致 ⇒ 收
```

## 方案（与 tasks 那次同构）

```
① 模板/schema/authoring：docs/incidents/_template.md（+ 资产镜像，PAIRS）去掉 frontmatter id；
   AUTHORING 写明「身份＝文件名；frontmatter 不放复写字段」
② 存量迁移：12 份文件的 frontmatter id 行删掉（一次性脚本，确定性 + 幂等，放 /tmp/ 弹壳区）
③ 棘轮：新码 INCIDENT_ID_REDUNDANT（或并入现有冗余检查的家族）——
   frontmatter 出现 id ⇒ 红，提示"单一源＝文件名"
④ 反向守卫：文件名必须匹配 ^INC-\d{8}-[\w-]+\.md$（schema 已有，不动）
```

## 边界与拆分（规则 08）

- 事实归属：**身份**归文件名（唯一源）；**内容**归正文；frontmatter 只放不能被文件名表达的字段（`type`/`severity`/`status` 这类仍保留——它们不是文件名的复写）。
  注：`type` 与文件名里的 TYPE 段**看似**重复，但 `type` 是受控枚举（REG/…），文件名段是自由串 ⇒ **不同事实**，不属双写，保留。
- 边界检查：不碰 `severity`/`status`（无副本）；不改文件名规则（引用面靠它）。
- 桩子先行：先落检测码 + 3 份文件迁移，跑通；再迁余下 9 份。每步 `pytest` + `k3dge check` 绿。

## 验收

- `grep -c "^id:" docs/incidents/*.md` 全为 0（aux 除外）；
- 造一份带 frontmatter `id` 的 incident ⇒ 新码红；
- `k3dge doc where INC-20260910-CON-audit-merge-doc-drift` 仍能解析（身份走文件名）；
- 全量 pytest 绿；`k3dge check` 绿；模板资产 PAIRS 字节锁一致。

## Notes

- 来源：本轮我对「其它文档是否也有 frontmatter↔正文双写」的横展发现；用户答"感觉没必要改，你怎么看，按你的想法"⇒ 我的结论是**改**（同类缺陷、单一源原则、且实测无人读该字段），但**优先级 P3、不插队**。
- 拒绝的替代方案："保留 id 字段 + 加一致性闸"——那等于留着第二源，与刚立的单一源原则相抵（tasks 那次也没走这条路）。
- 与 `gate_facts_pure_structured` 的交点：新码进 `gate_facts` 声明面（fact/options/pointers/fix）。

## 落地（2026-09-19）

| 项 | 落点 | 实测 |
| --- | --- | --- |
| 棘轮 | `pure_refs.check_incident_id_redundant` + `gate_facts` 新码 `INCIDENT_ID_REDUNDANT`（block，`fix=deterministic`、hint＝删 `id:` 行） | 造 `id:` ⇒ 红；无 `id` ⇒ 绿；aux/非 incidents 不报 |
| 接线 | `scripts/pre-commit`（staged）+ `doc_catalog._validate_file`（typ=="incidents"，仓库级改动时评估） | — |
| 存量迁移 | 10 份文件的 `id:` 行删掉（一次性脚本，幂等，第二遍 0 改动） | `grep -c '^id:' docs/incidents/INC-*.md` 全 0 |
| 模板/作者规约 | `docs/incidents/_template.md`（**不配对**，只需改仓内）去掉 `id` + 写清「身份＝文件名」；`docs/incidents/AUTHORING.md`（两份 PAIRS）同口径 + 记机验码 | PAIRS ✓ |

### 实证（本票的病灶在迁移前当场复现）

```
$ 逐份核对 id ↔ 文件名
  ❌ INC-20260826-REG-m3-task-truncate.md   id: INC-20260826-REG-01     ← 不一致，从没人发现
  ❌ INC-20260904-AUD-case-file-crossover.md  （无 frontmatter，Legacy 形态）
  ✅ 其余 9 份一致（纯副本）
```
11 份里 1 份真漂移、9 份纯副本、1 份 legacy 无 frontmatter ⇒ 复核了"第二源只能漂移且无人验"的判断。

### 顺带核对（不是缺陷）

- `check_h1` 用 `re.IGNORECASE` ⇒ `# INCIDENT REPORT:` 合法通过 `^#\s+Incident`（我一度以为是闸的盲点，实测否）。
- `INC-20260904-AUD-case-file-crossover.md` 无 frontmatter 属 legacy 形态：incidents 的 `.schema.json` **不要求** frontmatter ⇒ 通过。**有意留**：若要收它（补 type/severity/status），属另一决策（部分卡片因此 `status` 为空）；本票只做"id 单一源"。
- `docs/specs/*/spec.md` 里仍有 `STATE_OPTIONS` 的旧快照（含已退休的 `doc_audit`）——那是 `sync` 生成的契约快照，已由上一票的 sync 刷新。

## 验收（实测）

```
629 passed；k3dge check 绿
tests/unit/engine/test_pure_refs.py::TestIncidentIdSingleSource（4 条）
  有 id ⇒ 红 / 无 id ⇒ 绿 / aux 与非 incidents 不报 / 自举：本仓 incident 全部单一源
迁移幂等（第二遍 0 改动）；模板与 AUTHORING 口径一致（PAIRS ✓）
```
