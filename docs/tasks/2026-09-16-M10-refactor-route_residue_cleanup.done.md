---
status: done
milestone: M10
priority: P1
date: 2026-09-16
---

# 路线残留清理：frontmatter 三头 + doc_catalog 死代码 + parse_doc_schema 去重

- **可检索摘要**: 本轮做 pure_schema 抽取后 doc_catalog 瘦身不彻底，遗留三类路线残留：(1) frontmatter 解析存在三个入口（task_index / doc_catalog 代理层 / pure_schema 复制品）；(2) doc_catalog 中 check_section_order + _SECTION_NUM_RE 与 pure_schema 重复定义且无人调用；(3) parse_doc_schema 在 doc_catalog 和 pure_schema 各有一份逐字复制。合并为单一实现，~50 行改动。

## 意图

消灭本轮 pure_schema 抽取遗留的路线杂糅。三件事本质是同一个问题：doc_catalog 瘦身不彻底。

## 现状

### 1. frontmatter 三头怪

同一逻辑三个独立实现，测试 `test_frontmatter_pairs_match_task_index` 是唯一的漂移守卫：

| 位置 | 函数 | 角色 |
|---|---|---|
| `task_index.py:21` | `_frontmatter_pairs()` | 唯一源（engine 内部调用者都走这里） |
| `doc_catalog.py:87` | `_frontmatter()` | 无意义代理：`dict(_frontmatter_pairs(text))` |
| `pure_schema.py:53` | `parse_frontmatter_pairs()` | 逐字复制（pre-commit 零依赖需要） |

### 2. doc_catalog 死代码

`_validate_file` 已委托 pure_schema，但旧 helper 全留着：

| 函数 | 状态 |
|---|---|
| `check_section_order()` | doc_catalog 内有完整实现 + pure_schema 也有一份，doc_catalog 内无人调用 |
| `_SECTION_NUM_RE` | 两个文件各定义一份 |
| `parse_doc_schema()` | doc_catalog:42 + pure_schema:41 逐字复制 |

### 3. doc_catalog._frontmatter 代理层

`_frontmatter(text)` 只是 `dict(_frontmatter_pairs(text))` 的包装。`build_card()` 调它，但完全可以在调用处直接 `dict()`。

## 方案

### Step 1：删 doc_catalog 死代码

- 删 `_SECTION_NUM_RE`（doc_catalog 内定义）
- 删 `check_section_order()`（doc_catalog 内定义）
- `check_section_order` 的 re-export `from pure_schema import check_section_order` 已存在，保留

### Step 2：parse_doc_schema 去重

- 删 `doc_catalog.parse_doc_schema`
- `_load_schema` 改为 `from k3dge.engine.pure_schema import parse_doc_schema`
- 测试确认 `parse_doc_schema` 的外部引用（1 处）改指 pure_schema

### Step 3：frontmatter 统一

- 删 `doc_catalog._frontmatter()` 代理层
- `build_card()` 的 `fm = _frontmatter(text)` 改为 `fm = dict(_frontmatter_pairs(text))`
- 删 `from k3dge.engine.task_index import _frontmatter_pairs` 的函数内 import，提到模块顶部（doc_catalog 已经顶层 import 了 task_index 的其他符号，无循环风险）
- `pure_schema.parse_frontmatter_pairs` 保持独立复制（pre-commit 零依赖硬约束），测试守卫不变

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：`task_index._frontmatter_pairs` 是 engine 内唯一 frontmatter 解析源；`pure_schema.parse_frontmatter_pairs` 是 pre-commit 零依赖复制品（硬约束，不合并）
- 边界检查：`doc_catalog` 不保留任何与 pure_schema 重复的定义；`parse_doc_schema` 只在 pure_schema 定义
- 桩子先行：先改一个删一个跑测试

## Notes

- 改动量：~50 行删改，无新增
- 风险：低（测试覆盖 + parity oracle）
- 不做：datetime.now() 时区统一（P2）、函数内 import 整理（P3）

## 结案

- 关闭提交：`ebaff64`（2026-09-18）
- 落地记录：见该提交 message 与本文正文（回填于 2026-09-19，事实取自 `git log --diff-filter=AR -1 -- <path>`）。
