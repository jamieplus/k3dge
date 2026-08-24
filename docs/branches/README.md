# Branches — 思维分支归档

与 `docs/tasks/`（后做）、`docs/memo/`（闪念）并列，专收**本任务内已证伪的尝试路径**，用于裁剪上下文与重置注意力。

## 写入时机

`k3dge check` 红灯且将重试前 → 先归档再 `git stash` 重读 `spec`。

## 单条模板（自包含，未来失忆的自己也能看懂）

```markdown
# 分支：<尝试标题>

- **尝试路径**：试了什么假设/改了哪域哪接口
- **为何失败**：`GateReport` 哪条 `CONTRACT_DRIFT / MISSING_TEST_FILE` 红
- **学到什么**：下次如何避坑
- **Date**: YYYY-MM-DD
```

## 读取时机

重试前必读 `docs/branches/` 全量，避免重踩同一失败路径；与 `tasks` 的"开工扫"互补。
