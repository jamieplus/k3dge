# 下游仓与 k3dge 升级

> 给**已经 `k3dge-init` 过的工程仓**看：k3dge 源更新之后，什么会跟着变、什么不会、该怎么升。本仓自举另走 `TEMPLATE_DRIFT`，不要把那把锁套到下游。
>
> 设计依据：ADR 0008（脚手架幂等、协议升级不是 init 覆盖）、ADR 0005（`K3DGE_SOURCE` / editable）、ADR 0006（MCP 零漂移）、ADR 0019（下游至少一域）。

## 两层 harness

下游仓里的 k3dge 分成两层，升级方式不同。

| 层 | 是什么 | 升什么 |
| --- | --- | --- |
| **判定核** | `.venv` 里 `pip install -e "${K3DGE_SOURCE}[mcp]"` 装上的包 | `k3dge` CLI、`python -m k3dge.cli.mcp`、门禁/`task list`/`sync` 全部走这里 |
| **拷进仓的协议与包装** | `AGENTS.md`、`scripts/gate.*`、`scripts/init.sh`、`.pre-commit-config.yaml`、docs 模板 | init **不会覆盖**已有文件（`_write_if_missing`） |

Agent 用的索引工具（`k3dge task list`、MCP `k3dge_task_list` / `k3dge_sync` 等）属于**判定核**，不在下游仓里另存一份脚本。

## 再跑一次 init 会怎样

在已部署的下游仓再执行 `K3DGE_SOURCE=/path/to/k3dge ./k3dge-init.sh`（或仓内 `./k3dge-init.sh`）：

**会做**

- 再执行 `pip install -e "${K3DGE_SOURCE}[mcp]"` → 判定核换成当前源（含 MCP）
- scaffold 只**补当时还不存在的新模板文件**（例如后来才有的 `docs/guides/mcp-bridge.md`、`.gitignore`）
- `manifest.domains` 仍为空时，写入第一条域（ADR 0019）
- `k3dge sync`、`pre-commit install`（含 `--hook-type commit-msg`）

**不会做**

- 覆盖已有 `AGENTS.md`、`scripts/gate.*`、`scripts/init.sh`、overview、已有的 mcp-bridge 旧稿
- 把本仓的 `docs/adr/` 或 reviews 审计目录拷过来

这是刻意的：init 幂等，避免把项目改过的协议冲掉。协议升级要**另同步**，不是 init 行为回退（ADR 0008）。

## 推荐升级步骤

只想用新闸、新 `task list`、新 MCP 工具：

```bash
cd <downstream>
pip install -e "${K3DGE_SOURCE}[mcp]"
k3dge check --force-full
```

不必整段 init。装完重启 MCP 所在 harness。

协议口令也要跟上（例如 AGENTS.md 改成 `task list --json`、新的 §12 行）：

1. 打开 k3dge 检出里的 `src/k3dge/templates/assets/agents.md`（或本仓 `AGENTS.md`，二者字节锁）
2. **diff 后合并**进下游 `AGENTS.md`，不要整文件覆盖自己加过的项目说明
3. 对 `scripts/gate.*`、`mcp-bridge.md` 同样：缺文件再跑一次 init 会补上；已有文件用 diff 合

合完在下游跑 `k3dge check --force-full`。下游没有 `TEMPLATE_DRIFT`，协议文件停在上次手合的版本。

## 不要做的

- 不要用 `git checkout` 清下游仓来「对齐模板」
- 不要以为再 init 就会把 AGENTS.md 变成最新
- 不要在下游重实现哈希 / 私写 `k3dge check`（ADR 0006）
- 不要把 k3dge 检出的 `docs/reviews/` 索引当下游模板拷

## 何时重开

若经常要批量升多个下游仓的协议文件，再加一条显式的 `k3dge` 同步命令（只更新模板对、可 `--dry-run`）。在那之前，判定核用 pip，协议用 diff 合并。
