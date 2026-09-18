---
status: done
milestone: M10
priority: P2
date: 2026-09-16
---

# 补测试：4 个零覆盖/浅覆盖的关键 engine 模块

- **Status**: done
- **Milestone**: M10
- **Priority**: P2
- **可检索摘要**: 用函数级引用分析（非文件名猜测）找出 tests/ 中从未被调用的关键函数，为 4 个高风险模块补 78 个单元测试：`milestone_files`（零覆盖）、`milestone_pointer`（安全函数 `_validate_milestone_id` 防路径穿越）、`markers`（审计钉写源 + code-11 行号口径回归守卫）、`changelog`（Unreleased 越界写入不变量）。395 → 473 passed。
- **Date**: 2026-09-16

## 意图

原先按"有无同名 test 文件"判断覆盖，得出 18 个模块缺测试——这个信号是错的（多数经集成测试间接覆盖）。改用**函数级引用分析**：解析每个 engine 模块的顶层函数，grep 其名字是否在任何 test 文件中出现，得到精确差距。

## 分析方法

```python
# 对每个模块的每个顶层函数，检查是否在 tests/ 全文中出现
funcs = [n.name for n in tree.body if isinstance(n, FunctionDef)]
untested = [fn for fn in funcs if not re.search(rf"\b{fn}\b", test_blob)]
```

按此筛出真正零覆盖且高风险的三个模块 + 一个完全零覆盖模块。

## 补的测试（78 个）

### `test_milestone_files.py`（15）— 原零覆盖

核心不变量：**`M1` 不得匹配 `M10`**（token 边界）。历史上出过跨里程碑误判事故。

- `_has_milestone_token`：M1/M10 区分、分隔符集（`- _ . /` 空白 行首尾）、无分隔符子串不匹配、空 id
- `_is_doc_aux` / `_is_review_aux`：结构文件 vs 内容文件、点文件、LEFTOVERS 只在 review 语境算 aux
- `_filename_milestone`：提取、大小写、边界分隔要求（`XM10Y` 不算）

### `test_milestone_pointer.py`（22）— 安全函数零覆盖

`_validate_milestone_id` 防路径穿越（id 会拼进 `archive/M10`、报告文件名），边界从未被断言：

- 拒绝 `../evil`、`..`、`M1/../x`、`M1/sub`、`M1\sub`、`/abs`、`M1/`、`sub/M1`
- 拒绝空/空白、非字母数字开头（`-M1`、`.M1`、`_M1`）
- 接受 `M1`/`M10`/`M1.2`/`M1-x`/`M1_x`/`adhoc`/`0`/`a1`
- 游标：默认 M0、set/get 往返、set 拒绝不安全 id、**坏内容回落 M0 不崩**（写 `../../etc/passwd` 进游标文件）
- bump：M0→M1、连续、**M9→M10（数值非字典序）**、非 M 形状回落 `-next` 后缀、落盘持久

### `test_markers_deep.py`（26）— 审计钉写源

ADR-0025 §2.7 规定钉是 findings 的写源，`parse_sidecar`/`open_samples` 是审计闭环核心：

- **`_line_index` code-11 回归守卫**：行号必须与 `str.splitlines()` 同口径。splitlines 除 `\n` 外还切 `\x0b \x0c \x1c-\x1e \x85 \u2028 \u2029`；若只认 `\n`，`worktree.strip_pins` 按 splitlines 索引会**删错行**。测试覆盖 `\x0b`、`\u2028`、`\r\n`
- `head_block_end`：shebang/encoding/空行允许；**docstring 终止头部块**（`_COMMENT_LINE_RE` 只认 `# // <!--`）→ 后果是 `@file` 钉必须写在 docstring 之前
- `parse_text`：py 行尾钉 + 判读四格（sev/prio/type）、md 只认 `<!-- -->`、**反引号示例不自触发**、note 超限截断并报问题、pending 放宽到 500、`@file` 在正文里报问题
- `parse_sidecar`：`@repo` 条目、缺 `@repo` 报问题、`- files:` 追加进 note、非钉标题忽略
- `open_samples`/`counts`/`closure_ok`：open = pending+disputed+fixnote（**fixed/leftover 不算 open**）、blockers 判定、只有 leftover+fixed 可结项
- `validate`：`@repo` 只准住 AUDIT.md、同 ID 多 kind 报问题、多主锚报问题、**leftover 例外可跨文件**

### `test_changelog_deep.py`（15）— CHANGELOG 手术

`_insert_entry` 出错会静默毁发布说明：

- `_title_and_section`：H1 提取、无 H1 回落 stem、6 种 type→section 映射（feat→Added / fix,audit→Fixed / docs,chore,refactor→Changed）、**路径不含 `docs/tasks/` 时类型正则不匹配 → 默认 Fixed**
- `_insert_entry`：无 subsection 时新建、已有则尾插且不重复建、**核心不变量：绝不越界写进已发布版本段**、插到下一个 `###` 之前、无 `## [` 尾标记时正常插
- `_append_to_unreleased`：无 CHANGELOG 文件 no-op 返 True、无 Unreleased 段 no-op、正常追加、**幂等不重复**、**去重只在 Unreleased 段内判定**（旧版本有同名条目不阻止新增）

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：测试只断言现有行为，不改产品代码（唯一例外见下）
- 边界检查：4 个测试文件各自独立，不引入 fixture 共享
- 桩子先行：先写测试跑一遍，用失败暴露我对语义的错误假设，再修正断言（不是改产品代码迁就测试）

## 测试写错→修正的两处（都是我的假设错，非代码 bug）

1. `head_block_end` 我以为 docstring 算头部块 → 实际 `_COMMENT_LINE_RE` 只认 `# // <!--`，docstring 终止块。改为断言真实行为并注释说明后果
2. `_title_and_section` 对 `/nonexistent/...feat-y.md` 我以为得 `Added` → 实际类型正则要求路径含 `docs/tasks/`，不匹配则默认 `fix`→`Fixed`
3. `_insert_entry` 我断言 `- first\n- second\n` 相邻 → 实际插入点在下一 section 标记前，中间隔空行。改为断言顺序 + 边界而非相邻

## 验证

- 新增 78 tests 全过
- 全量 473 passed, 2 skipped, 99 subtests passed（原 395）
- 零产品代码改动 → 无需 `k3dge sync`（确认 "Contracts already up to date"）

## Notes

- 剩余浅覆盖（间接覆盖为主，本票不做）：`seal._seal_archive`/`_seal_review_gate`、`review_archive._rewrite_leftover_links`、`audit_checklist._snapshot`/`_tasks_hash`、`task_index._scan_task_dir`、`audit_report._report_kind`
- 这些均由集成测试（`test_seal_flow.py`、`test_milestone.py`）间接执行，风险低于本票补的四个
