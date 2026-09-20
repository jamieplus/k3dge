---
status: done
milestone: M10
priority: P2
date: 2026-09-16
---

# P2: 7 处时间戳加时区偏移

- **可检索摘要**: 7 处 `datetime.now()` 产出无时区偏移的时间戳字符串（如 `2026-09-16T15:30:00`），消费者无法判断是 UTC 还是本地时间。改为 `datetime.now().astimezone()` 产出带偏移格式（如 `2026-09-16T15:30:00+09:00`），保持本地时间但显式标记。唯一的时间戳解析点（`cli/main.py:_attest_utc_minute`）已兼容两种格式，无破坏风险。

## 意图

让所有 k3dge 产出的时间戳字符串**显式携带时区信息**，消除"不知道是哪个时区"的歧义。

## 现状

### 7 处产出无偏移时间戳

| 文件 | 行 | 字段 |
|---|---|---|
| `audit_flow.py` | 152 | `audit_jobs.json:submitted_at` |
| `audit_flow.py` | 274 | `audit_jobs.json:collected_at` |
| `audit_flow.py` | 359 | `audit_jobs.json:advances[].at` |
| `pipeline_runner.py` | 151 | `logs/k3dge.log` 时间戳 |
| `pipeline_runner.py` | 416 | HARNESS_SKIP 日志 |
| `audit_checklist.py` | 73 | `audit_checklist.json:generated_at` |
| `audit_checklist.py` | 110 | `audit_checklist.json:audit_started_at` |

产出格式：`2026-09-16T15:30:00`（无偏移，消费者无法判断时区）。

### 1 处产出 UTC 时间戳（已显式）

| 文件 | 行 | 字段 |
|---|---|---|
| `events.py` | 26 | `events.jsonl:ts` |

产出格式：`2026-09-16T06:30:00+00:00`（带偏移，明确 UTC）。

### 解析点

只有 `cli/main.py:925` 的 `_attest_utc_minute()` 解析时间戳：

```python
dt = datetime.fromisoformat(ts.replace("Z", "+00:00").replace("z", "+00:00"))
if dt.tzinfo is None:
    dt = dt.replace(tzinfo=timezone.utc)
return dt.astimezone(timezone.utc)
```

**已兼容两种格式**：
- 带偏移（`+09:00`）→ `fromisoformat()` 直接解析成 aware datetime
- 不带偏移（naive）→ `replace(tzinfo=timezone.utc)` 假设 UTC

## 方案

### 改动

把 7 处 `datetime.now()` 改成 `datetime.now().astimezone()`：

```python
# 之前
datetime.now().isoformat(timespec="seconds")
# 产出：2026-09-16T15:30:00

# 之后
datetime.now().astimezone().isoformat(timespec="seconds")
# 产出：2026-09-16T15:30:00+09:00（东京）
```

### 不变量

**每个时间戳字符串必须携带时区偏移**，不强制哪个时区。

### 风险

- **现有 JSON 文件**：已有的 `audit_jobs.json` / `audit_checklist.json` 里的旧时间戳是 naive 格式，新数据是 aware 格式。但解析代码 `_attest_utc_minute` 两种都能处理，混在一起不会报错。
- **`fromisoformat()` 兼容性**：Python 3.10+ 完全支持 ISO 8601 带时区偏移。
- **无时间比较**：k3dge 没有跨文件时间比较的代码（`submitted_at` vs `events.jsonl:ts`），所以不会触发 "can't compare offset-naive and offset-aware datetimes" 错误。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：每个文件独立改自己的时间戳产出，无共享函数（保持现状）
- 边界检查：改完后 `grep -rn 'datetime.now().isoformat'` 应为空（或只剩 `events.py` 的 UTC 版本）
- 桩子先行：改一个跑测试，确认无回归

## Notes

- 改动量：~10 行（7 处改动 + 3 处测试断言更新）
- 不统一时区（保持本地时间），只加显式偏移
- 不引入共享函数（7 处分散在不同模块，抽函数反而增加耦合）

## 结案

- 关闭提交：`ebaff64`（2026-09-18）
- 落地记录：见该提交 message 与本文正文（回填于 2026-09-19，事实取自 `git log --diff-filter=AR -1 -- <path>`）。
