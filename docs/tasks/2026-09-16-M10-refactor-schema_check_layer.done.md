---
status: done
milestone: M10
priority: P2
date: 2026-09-16
---

# 抽取零依赖 schema 校验层：`scripts/lib/schema_check.py`

- **可检索摘要**: engine 的结构校验与 pre-commit 的存在性检查是不同 agent 各自补的坑，路线杂糅。抽取零依赖纯函数层 `scripts/lib/schema_check.py`（stdlib only），pre-commit 与 engine 共用；并新增 4 类 stdlib 新闸（悬空引用/文件名一致性/markdown 完整性/孤儿文件），补 engine 现有盲区。

## 意图

统一两条杂糅路线 + 补盲区。分两部分：

**A. 迁移（消灭重复）**：pre-commit 只会查文件在不在，engine 全套 schema 校验但要 venv 才能跑。抽一层零依赖纯函数，两边共用，pre-commit 从"存在性"升级到"全量结构"，engine 瘦身到只做语义检查。

**B. 新闸（补盲区）**：engine 现在完全不查的东西——悬空引用（M10 doc-1/2/3 前科）、文件名↔内容不一致、markdown 破损、孤儿文件。全部 stdlib 可做，毫秒级。

## 现状

| 层 | 会查什么 | 不会查什么 |
|---|---|---|
| `scripts/pre-commit`（stdlib only） | README/AUTHORING 在不在 | 文件名格式、frontmatter、章节顺序 |
| `engine/doc_catalog._validate_file` | 文件名/frontmatter/章节/跨文件引用 | 目录四件套在不在（假设结构是对的） |

两边查的是互补集——写 pre-commit 的 agent 没看 engine 覆盖了什么，只补了眼前坑。

## 方案

### A. 迁移：抽取 `scripts/lib/schema_check.py`

#### A1. 新建 `scripts/lib/schema_check.py`（零依赖）

纯函数，stdlib only（`json`/`re`/`pathlib`），不 import k3dge：

```python
def check_file(schema: dict, path: Path, text: str) -> list[tuple[bool, str, str]]:
    """返回 [(ok, code, message)]，不碰 Violation 对象。"""
```

覆盖：文件名正则、frontmatter 字段、章节存在、章节顺序。

#### A2. `scripts/pre-commit` 调用它

doc-gate 从"存在性"升级到"全量结构"：staged docs 逐个按 `docs/<type>/.schema.json` 校验。doc-only 提交也能被 schema 拦，不再等 CI。

#### A3. `engine/doc_catalog.py` 瘦身

`_validate_file` 改为：调 `schema_check.check_file()` 拿结构结果，包一层 `Violation`，再加跨文件语义检查（引用、索引）。删掉重复的结构校验逻辑。

### B. 新闸：4 类 stdlib 检查（engine 现有盲区）

全部进 `scripts/lib/`（零依赖），pre-commit 直接调，engine 按需复用。按"出过事优先"排序：

#### B1. 悬空引用（最高优，M10 doc-1/2/3 前科）

```python
def check_dangling_refs(workspace: Path, files: list[str]) -> list[tuple[bool, str, str]]:
```

| 检查 | 做法 |
| --- | --- |
| `ADR-XXXX` 引用 → `docs/adr/XXXX-*.md` 必须存在 | `re` + `glob` |
| task `report:` 指针 → 文件必须存在 | `re` + `path.exists` |
| memo 全路径引用 → 文件必须存在 | `re` + `path.exists` |
| footnote `[^X]` 有引用必须有定义 | `re` 配对 |

#### B2. 文件名 ↔ 内容一致性

```python
def check_name_content(workspace: Path, files: list[str]) -> list[tuple[bool, str, str]]:
```

| 检查 | 做法 |
| --- | --- |
| task `status: done` 但文件名非 `.done.md`（反之亦然） | frontmatter + 字符串 |
| task 文件名含里程碑但 frontmatter `milestone:` 不符 | 同上 |
| ADR 文件名编号 vs `# ADR-NNNN` 标题不一致 | 同上 |

#### B3. Markdown 完整性

```python
def check_markdown(text: str, path: str) -> list[tuple[bool, str, str]]:
```

| 检查 | 做法 |
| --- | --- |
| 未闭合 code fence | 行计数 |
| 冲突标记残留（`<<<<<<<` 等） | 字符串匹配 |
| 非 UTF-8 / CRLF / 行尾空格 / 缺文末换行 | 字节检查 |

#### B4. 孤儿文件（先 warn，转红待观察误报率）

```python
def check_orphans(workspace: Path) -> list[tuple[bool, str, str]]:
```

| 检查 | 做法 |
| --- | --- |
| spec 存在但 manifest 无域指向 | `json` + 集合差 |
| 测试文件存在但无 matrix 引用 | `re` 全仓扫 + 集合差 |
| ADR 存在但 README Topics 未列 | `re` + 集合差 |

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：`engine/pure_schema.py` + `engine/pure_refs.py` 拥有纯校验；engine 拥有 Violation 包装 + 语义检查；`.schema.json` 仍是单一事实源（两边都读它）
- 边界检查：pure 模块不得 import 任何 k3dge 功能模块（只允许 `pure_*` 互引；机验 `test_pure_imports_stdlib_only` 卡）；engine 不得绕过 pure 自己写正则
- 桩子先行：先写 pure + 单元测试（parity oracle 对照现有行为）→ 接 pre-commit → 再瘦 engine

## 位置偏差记录

task 原定 `scripts/lib/`，落地改为 `engine/pure_*.py`，原因：wheel/pyz 只打包 `src/k3dge`，`scripts/` 不随包走——canonical 放 `scripts/` 则安装版 engine 无法 import。两 `__init__.py` 均为 docstring-only，pre-commit 经 `src/` 路径 import 不触发重依赖。目标不变（单实现、零依赖、两边共用）。

## Notes

- 改动量：A 部分 pure 模块 ~350 行 + pre-commit 接入 ~150 行 + engine 删 ~120 行；B 部分 4 类新闸 + 测试
- 落地顺序：A1 → A2 → A3 → B1 → B2 → B3 → B4（B4 先 warn）——已全部完成，见下方收尾。
- 不碰：跨文件引用语义、hash 对比、AST 分析仍在 engine；`reconcile_supersedes` 等 seal 闸不动。

## 收尾（2026-09-16）

- ✅ A1：`engine/pure_schema.py`（check_filename/h1/sections/order/frontmatter/headers/index + check_file/check_content）+ `engine/pure_refs.py`（B1–B4）
- ✅ A2：pre-commit 接入（staged blob 校验 + B4 warn + pure 缺失时降级）；git 本地不可用，集成覆盖走 `tests/unit/scripts/test_precommit.py`（8 tests）
- ✅ A3：`doc_catalog._validate_file` 瘦身为 pure 委托 + seen/index；删 8 个旧 helper（留 `check_section_order` re-export）；parity oracle 全仓 doc 文件比对通过
- ✅ B1–B3：悬空引用/文件名一致性/markdown 完整性，pre-commit 阻断；B4 孤儿三件套 pre-commit WARN（engine 未接，避免双报）
- ✅ 机验：`test_pure_imports_stdlib_only`（AST 断言纯模块零 k3dge 功能 import）+ AUX 集合同步断言 + frontmatter 解析一致断言
- ✅ `k3dge sync` 已回写 engine 契约哈希
- 修顺手 bug：`pure_refs.check_footnotes` 的 `"\\n".join(str)` 拆字符；测试文件换行误合并
