---
status: done
milestone: M10
priority: P1
date: 2026-09-16
---

# 业务逻辑闸：task 元数据 frontmatter ↔ body 分歧检测

- **可检索摘要**: task 的 5 个元数据字段（status/milestone/priority/date/report）在 frontmatter 与 body 各存一份。frontmatter 是权威（`_scan_task_dir` 优先读），body 是「人类可读副本」，但副本可漂移且**无任何闸发现**（E19 实测）。后果：人读 body 见 `idea`、工具读 frontmatter 见 `done`，同一任务两种事实。扩展 `pure_refs` 加双源对照闸。

## 意图

补上「副本漂移」这个业务逻辑盲区。保持双写设计（body 副本为人类可读性刻意保留），只加分歧检测。

## 证据链

### E19 — 分歧不被任何闸发现（产物）

```
构造：frontmatter status='done' + body '- **Status**: idea'
      frontmatter milestone='M10' + body '- **Milestone**: M99'
结果：check_task_consistency 报告 []
     即：分歧存在且无闸报告
```

### E20 — 权威源与消费端分裂（消费者）

```
task_index._scan_task_dir:120-135   fm 存在 → 读 frontmatter；否则读 body 正则
   （里程碑/封板判定走此路径）
task_index.MILESTONE_RE             → 读 body
pure_refs._STATUS_RE                → 读 body
evaluator / task_dag                → parse_frontmatter（frontmatter）
```

⇒ **frontmatter 权威，body 为副本**；但读取端分裂到两个源。

### E23 — milestone 有三个源（产物）

```
frontmatter  milestone:                     权威
body         - **Milestone**:               MILESTONE_RE
文件名        2026-09-16-M10-fix-x.md        _FILENAME_MILESTONE_RE
```

现有闸只查 frontmatter ↔ 文件名，**不查 frontmatter ↔ body**。

### 已验证非问题（不属本票）

| 项 | 判定 |
|---|---|
| `audit_closed` 两处调用 | 两处调同一函数 ⇒ 规则单源，仅检查点重复 |
| 报告待修计数 | `_parse_audit_stats` 单源、6 消费者 ⇒ code-13 修复成立 |
| 版本三文件 | 有 `VERSION_MISMATCH` 闸 |

## 方案

### 实现

在 `pure_refs` 内加双源对照。**复用 `pure_schema.parse_headers()`**（已有的通用 body 字段解析器）——不新写正则，避免制造新的重复事实源。

```python
_BODY_FIELD_MAP = {          # frontmatter 键 → body 粗体标签
    "status": "Status", "milestone": "Milestone", "priority": "Priority",
    "date": "Date", "report": "Report",
}


def check_task_meta_agreement(rel: str, text: str) -> List[Ref]:
    """frontmatter ↔ body 双源对照（tasks only）。

    frontmatter 权威、body 为人类可读副本；副本漂移此前无闸发现。
    无 frontmatter 的遗留任务跳过（body 即唯一源，无从对照）。
    """
```

由 `check_task_consistency` 调用 ⇒ 现有 pre-commit 接线自动生效。

字段值归一：body 的 `Report` 带反引号（`- **Report**: \`docs/...\``），对照前 strip 反引号。

### 单侧缺失不报

写入端不保证全字段（`milestone`/`report` 可缺），故任一侧为空即跳过，只报**两侧都有且不等**。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：双源对照判据归 `pure_refs`；body 字段解析复用 `pure_schema.parse_headers`（不另立）
- 边界检查：零依赖约束不变（只 import `pure_schema`）；无 frontmatter 的遗留任务不误伤
- 桩子先行：先写 4 条测试（一致/status 分歧/milestone 分歧/单侧缺失）→ 实现 → 接 pre-commit

## 实施

新增 `pure_refs.check_task_meta_agreement()`，由 `check_task_consistency` 调用⇒pre-commit 接线自动生效。

**复用 `pure_schema.parse_headers()`**（已有的通用 body 字段解析器）而非新写正则——避免在修复重复的同时制造新的重复。

字段映射：`status→Status`、`milestone→Milestone`、`priority→Priority`、`date→Date`、`report→Report`（body 侧带反引号，对照前 strip）。单侧缺失不报。

## 验证

### 单元（+8 条）

`TestTaskMetaAgreement`：一致通过 / status 分歧 / milestone 分歧 / report 反引号归一 / 单侧缺失不报 / 无 frontmatter 遗留不误伤 / 非 task 跳过 / 接线断言。

### 全仓复扫（关键）

上线前扫现有活跃 task：

```
扫描 21 个活跃 task 文件
双源分歧: 8 条
  2026-09-14-M10-feat-event_log.done.md              frontmatter='done' body='idea'
  2026-09-14-M10-feat-unify_next_step_channel.done.md frontmatter='done' body='idea'
  2026-09-16-M10-chore-timestamp_tz_offset.done.md    frontmatter='done' body='idea'
  2026-09-16-M10-feat-extractor_gen.done.md           frontmatter='done' body='idea'
  2026-09-16-M10-refactor-rename_audit_mode_scaffold.done.md  frontmatter='done' body='in-progress'
  …（共 8 个）
```

**全部是本会话新建的文件**，成因一致：改状态时只改了 frontmatter `status:`，未同步 body `- **Status**:`。

⇒ 闸上线即抓到 8 处真实漂移，且实例均由**本 agent 在正常作业中无意识造成**——直接坐实了「副本会漂移」这一断言，比我构造的分歧用例更有说服力。

已按「frontmatter 权威」把 8 个文件的 body Status 同步；复扫剩余分歧 **0**。

### 全量

**487 passed, 2 skipped**（原 479，+8）。`k3dge sync`：engine 契约已回写（`pure_refs` 增公开函数）。

## 为何不删 body 副本

删除可根除漂移，但要：动 `task_write.create_task` 模板 + 迁移遗留 body-only 任务 + 改 `tasks/.schema.json` 的 `headers` 校验。代价远大于收益，且 body 副本是刻意的可读性设计（渲染后 frontmatter 未必可见）。加闸保持设计同时抓住漂移，相称。

## Notes

- 改动量：`pure_refs` ~30 行 + 8 条测试 + 8 个既有文件修正
- 工具路径本就双写（`_finalize_task_done` 同时改 frontmatter 与 body）⇒ 只有**手工编辑**会漂移，闸正好补这个口
- 本票副产品：清理了本会话遗留的 8 处自身漂移
