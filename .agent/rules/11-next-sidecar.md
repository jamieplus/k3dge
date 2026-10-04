## 11. Next-step sidecar

> Protocol slice for tools that look under `.agent/rules/` (ADR-0010).
> Live agent protocol is repo-root `AGENTS.md`. If this file disagrees, `AGENTS.md` wins; fix this file in the same task.

每次操作完（改代码/关票/写文档），读 `<workspace>/.k3dge/next.json`（路径以被审仓根为准，非 cwd），按 `state` 行事。

- `state=normal` 或文件不存在时静默（不输出、不提示；读失败/解析失败则出声，不静默）
- 有 `ask` 字段时向人确认，按 `if_y` / `if_n` 行事
- 只有 `note` 字段时直接执行对应动作

k3dge 命令完成时自动写 sidecar（fire-and-forget）。agent 读 sidecar，不需要记"哪个命令会打 `[NEXT]`"。
