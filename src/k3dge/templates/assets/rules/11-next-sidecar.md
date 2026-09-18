## 11. Next-step sidecar

每次操作完（改代码/关票/写文档），读 `.k3dge/next.json`，按 `state` 行事。

- `state=normal` 或文件不存在时静默（不输出、不提示）
- 有 `ask` 字段时向人确认，按 `if_y` / `if_n` 行事
- 只有 `note` 字段时直接执行对应动作

k3dge 命令完成时自动写 sidecar（fire-and-forget）。agent 读 sidecar，不需要记"哪个命令会打 `[NEXT]`"。
