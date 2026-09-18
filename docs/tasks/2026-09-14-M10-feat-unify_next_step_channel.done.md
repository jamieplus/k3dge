---
status: done
milestone: M10
priority: P2
date: 2026-09-14
---

# 统一 [NEXT] 通道：stdout + sidecar 双投递

- **可检索摘要**: 所有产生 `NextStep` 的命令（CLI 14 处 + MCP 8 处）统一在产出时落盘 `.k3dge/next.json`，agent 读 sidecar 即可知下一步，不再依赖 stdout 或主动调 status。

## 意图

k3dge 编排自己的流程（ADR-0006 §2.3 ⑧）：命令完成后写 next.json，agent 操作完读它即知下一步。stdout `[NEXT]` 保留给人，sidecar 是给 agent 的增量通道。

## 现状

`nextstep.py` 有完整的状态机（`STATE_OPTIONS`）和双渲染方法（`render_cli` / `render_mcp`），但落盘缺失：

| 层 | 现有调用点 | 现状 |
|---|---|---|
| CLI (`main.py`) | 6 处 `print(ns.render_cli())` | 只有 stdout，无 sidecar |
| Engine (`milestone_audit.py` / `seal_flow.py`) | 8 处 `return (state, msg + ns.render_cli())` | 嵌入 msg，调用方（CLI/MCP）打印后丢失 |
| MCP (`mcp.py`) | 8 处 `nxt.render_mcp()` | 已在 JSON 里返回（天然 sidecar） |
| Status (`status.py`) | 2 处 `lifecycle_next()` | `--json` 已有 `.next`，但纯 CLI 模式无 sidecar |

## 方案

### 1. `nextstep.py` 新增 `emit()`

一个函数同时完成双投递，所有调用点只调它：

```python
def emit(workspace: Path, ns: NextStep, *, stream=None) -> str:
    """stdout 打印 + sidecar 落盘，返回渲染后的 CLI 文本。"""
    _persist(workspace, ns)           # sidecar
    text = ns.render_cli()
    if stream is not None:
        print(text, file=stream)      # stdout
    return text

def _persist(workspace: Path, ns: NextStep) -> None:
    path = workspace / ".k3dge" / "next.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ns.render_mcp(), ensure_ascii=False) + "\n")
```

### 2. 改造调用点（按层）

**CLI 层**（6 处）— 替换 `print(ns.render_cli())` → `nextstep.emit(workspace, ns, stream=stream)`：

| 文件:行 | 场景 |
|---|---|
| `main.py:132` | cross-cutting hints 循环 |
| `main.py:144` | doc_audit 触发 |
| `main.py:222` | check 尾部 |
| `main.py:782` | seal rejection |
| `status.py` | status 命令输出 |
| MCP 侧不需要改（已有 `render_mcp()`） |

**Engine 层**（8 处）— 函数返回前调 `_persist`：

| 文件 | 场景 |
|---|---|
| `milestone_audit.py` ×4 | ratchet_open / audit_open / escalated / rejected / audited |
| `seal_flow.py` ×4 | audit_needed / deferred / rejected / sealed |

Engine 函数不持有 stream，只做 `_persist(workspace, ns)` 并把 `render_cli()` 文本拼进 msg。调用方（CLI/MCP）负责打印。

### 3. `.agent/rules/` 新增 `11-next-sidecar.md`

> 每次操作完（改代码/关票/写文档），读 `.k3dge/next.json`，按 `state` 行事。`state=normal` 或文件不存在时静默。

### 4. 测试

- `persist` 单元测试：写文件 → 读回 → 验证 JSON 结构
- 集成：跑 `k3dge check` → 验证 `.k3dge/next.json` 存在且 `state` 正确
- MCP 侧：现有测试已覆盖 `.next` 字段，不需要改

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：`engine/nextstep.py` 拥有 `emit()` / `_persist()` / `STATE_OPTIONS`；CLI 和 engine 只调 `emit()` / `_persist()`，不直接写 JSON
- 边界检查：fire-and-forget，CLI 不知道 agent 是否读了 sidecar；agent 不知道哪个命令写的（统一读文件）
- 桩子先行：先实现 `_persist()` + 测试 → 一个 CLI 命令调用 → 推广到全部 → 加规则

## Notes

- 改动量：`nextstep.py` ~15 行 + 14 处调用点各改 1 行 + 1 条规则 + 测试
- 不删 `[NEXT]` stdout 输出（CLI 用户依赖）
- events.jsonl 已拆为独立 task（`2026-09-14-M10-feat-event_log.md`）
