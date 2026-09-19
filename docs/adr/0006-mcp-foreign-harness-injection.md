---
Status: Accepted
Supersedes: -
Amended-by:
  - 🅰1 | Core Maintainer | 2026-09-14 | §2.3 第 2、8 条加作用域声明，删「不得外溢成参数」
Landed-by: src/k3dge/cli/mcp.py
Date: 2026-08-24
Deciders: Core Maintainer
Note: 修订痕迹见 git 历史。
---

# ADR-0006: 对外注入面与并列 harness 编排（入向兼容层 + 出向通道）

> **Related**: ADR-0005（本地自用 / 职责切分）、ADR-0010（rules 切片）、ADR-0009（吸收纪律）、ADR-0022（doc-audit 非阻断）
>
> **现行口径（`Status: Accepted`，Note ⑦ 2026-09-12）**：
> - ① 入向 server 已在 mcp 2.x 复活（`docs/guides/mcp-bridge.md`「入向现状」）。
> - ② §2.4 的降级报告有执笔与署名席位：合并审计模块各窗执笔、席位署名、Hall 收钉（`ADR-0025` §2.7 / `peer_contract §8`）。
> - ③ `Accepted` 过早由封版 ADR 硬闸兜底（`engine/adr_gate.py`：`adrs_all_accepted` + `adr_landed`）；`check` 按文档 `Status` 分档的机验票裁决不做，见 `docs/tasks/archive/M9/2026-09-13-M7-feat-check_gate_by_doc_status.done.md`。

## 1. 上下文 (Context)

- k3dge 先在本仓自用（ADR-0009 自举）；下一步用它开发并列 harness（audit / cache；quality 后并入 audit，ADR-0025），不把它们长进 `src/k3dge`。
- 两者都涉及"k3dge 如何与外部 harness 对接"，易与"MCP 是给本仓终端用户的第二套界面"混淆。
- 拓扑约束＝**不对称的从属 + 对等的地位**：k3dge 只管一致性自治，peers 的功能由 k3dge 调用来完成（功能从属）；但各自独立成仓、各自发 MCP server、可被别的 harness 使用（地位对等）。
- 旧稿只把 MCP 定义成**入向**（外部 harness 注入 k3dge），出向（k3dge 连 peers）没有位置；`engine/pipeline_runner.py` 的 `mcp` 传输里只有 `shutil.which("k3dit")` 探针——"k3dge 使唤 peers"停在注释里。
- 同一探针把 `k3lity_score` / `k3che_search` 译成 `k3dit k3lity_score` 执行，与本 ADR §2.2「harness 身份不混用」相抵。
- `AGENTS.md` 常驻行要求**降级不可自证**，旧 §2 却写"编排失败走 fallback / skip 不改变判定"——两份权威文件两个说法，本 ADR 裁决。
- 本机 stdio 是唯一传输面（ADR-0005）：出向对端仍是同一 OS 用户 spawn 的子进程，不新增信任域。

## 2. 决策 (Decision)

### 2.1 两个入口，都是"传输"，都不判定

- **CLI**（`k3dge.cli.main`）：本仓人/脚本原生入口（shell、pre-commit、CI）。
- **MCP**（`k3dge.cli.mcp`）：对外兼容层，只委托 `engine` / `sync` / `milestone`，零漂移；消费者是外部 harness，不是第二套交互设计。仍放在 `cli` 域（都是传输，不判定）。

### 2.2 并列 harness 模型

k3dge 是**一致性元门禁**；下列 peer 是独立仓，各自挂 k3dge（`K3DGE_SOURCE` 指向本检出）：

| Harness | 守什么 | 不守什么 |
| --- | --- | --- |
| **k3dge**（本仓） | 契约哈希、spec 结构、milestone 证据 | 好不好、怎么审、记不记得住 |
| **audit**（audit+quality 合并模块，ADR-0025） | 五轮/8 维透镜、12 列报告（ADR-0017）；质量窗（圈复杂度、重复、类型/坏味道） | 不跑 `k3dge check` 的判定 |
| **cache** | 提高 Agent 命中率的检索/缓存 | 不进 engine、不做门禁出口码 |

- 禁止把 audit（含 quality）/cache 做成 k3dge 的域。
  - 审计种子＝`docs/protocols/audit_default.md` / `verify_default.md`；透镜与 `check-report` 在合并审计模块（ADR-0025）。
  - quality 不再是独立 peer / fallback。
- 新仓 init 后与自举 k3dge 同一套 Agent 协议（门控、§12 触发、MCP 固定剧本）；`k3dge check` 在该仓 pre-commit 硬拦。
  - 脚手架幂等不覆盖已有 `AGENTS.md` / `scripts/init.sh`——协议升级要再同步这两份，不是 init 回退。
- **透镜审计不在 `src/k3dge`**（ADR-0005 §2.6）：MCP prompt 只指路，不在桥里演进规程。
- **信任边界**：本机 stdio 信任边界＝调起该 MCP 的 OS 用户（S-13）；k3dge 作为出向客户端同样成立；网络化后再重开鉴权。
- **入向 `workspace_path` 收敛**：MCP 服务进程启动钉**服务根**（启动 CWD）为 `K3DGE_MCP_ROOT`；`workspace_path` 默认须在服务根之内，越界即拒（显式化，不静默旁路窗/仓物理隔离，ADR-0025 §2.7）；跨仓须显式 `K3DGE_ALLOW_EXTERNAL_WORKSPACE=1`。非 MCP 直调（CLI/测试）不设服务根 ⇒ 语义不变。
- **harness 身份不混用**：其它 harness 自定入口，禁止共用 `k3dge_*` 工具名装成一个进程；一个 peer 的传输只准命中它自己的 server / CLI（§2.3）。

### 2.3 MCP 的方向性不变量

MCP 有两个方向，**互不借道、互不背书**：

| 方向 | 谁实现 | 谁调用 | 唯一事实源 |
| --- | --- | --- | --- |
| **入向** | 各仓自己的 `<pkg>.mcp`（stdio server） | 外部 agent harness | `.mcp.json`（该 harness 读它决定 spawn 什么） |
| **出向** | **k3dge**（stdio MCP 客户端） | k3dge 的编排（`milestone audit` / `seal` / `doc-audit`） | 同一份 `.mcp.json`（endpoint）+ `pipeline.toml`（流程） |

1. **每个 harness 各发一个 MCP server**：工具名带自己前缀，签名不出现调用方私有概念。
   - peers 被第三方 harness 直连是正常态，不得为 k3dge 增设专用参数。
2. **`check` 是纯静态硬闸**[^🅰1.1]（作用域＝`check`，不泛化到其他命令）：只验盘上文件与结构（schema / 符号引用 / 协议文件存在），不调用 agent、透镜或 peer 进程——不连 MCP、不跑 peer CLI（T-01）。
   - 出向调用只在 `milestone audit` / `seal` / `doc-audit` / `audit`（ADR-0025 §2.9.2）。
3. **endpoint 单一事实源＝`.mcp.json`**（`command` / `args` / `env` / `cwd` 即全部连接配方）。
   - `pipeline.toml` 只声明流程（stage / tool / fallback 链 / 超时），不得重复写 endpoint。
4. **`pipeline.toml` 是第三根门禁支柱**：旧键 `[harnesses]` / `[hooks]` 必须 `PIPELINE_SCHEMA_INVALID`，不得当空 `peers` 放行。
5. **gate 角色 peer 双传输出面**：gate 类角色（audit）必须同时提供 MCP server 与本机 CLI；缺 CLI 即未完成接入。
   - service 类（cache）豁免：`mcp → skip` 是其正确终态（查询失败＝能力暂缺，永不阻断）。
   - 分类依据见 `peer_contract §0`；本条修正 v0.2 把 cache 并入 gate 的分类错误。
6. **双主体铁律**：两类 actor——**进程**（机械变换，可复算、可哈希验证）与**席位**（判断，必须署名）。
   - ① 进程永不判断；
   - ② 一切判断落到具名席位（`审计人` / `透镜来源` / `验收`）；
   - ③ 无席位署名、或署名席位＝修改者的内容，不得自动过闸——只能带 `WARN[DOWNGRADE]` 走 attest（§2.4）。
   - 出向调用不改变此律：报告正文与「待修/有意留」裁量属审计席位；k3dge 进程只做形式校验、计数与字节落盘。
7. **跨仓改动需被改仓授权**：动 peer 仓要该仓维护者本轮显式授权，并在该仓 `docs/tasks/` 留痕（改了什么、实测什么）。
   - 约定变了就改写有那条约定的地方，不留自相矛盾旧句。
8. **k3dge 调的是「动作」，不是「步骤」** [A-8]（作用域＝对 peer 的出向调用，不约束 k3dge 自身流程编排）：一次 `run_action`＝peer 侧一件完整的事。
   - k3dge 不拆解 peer 的内部轮次[^🅰1.2]；peer 暴露的参数即公共接口，消费方使用不算干涉内部。缺动作级入口就补 peer 入口。

### 2.4 编排失败语义：降级不可静默

1. **不可静默**：任何降级（`mcp`→`cli`、`mcp`/`cli`→`manual`、→`skip`）都要表述到四处：
   - stderr：`WARN[DOWNGRADE] <action> <reason> <后果>`；
   - `logs/k3dge.log`（机器可读，供事后复述）；
   - 当轮 12 列报告的 `透镜来源` + `审计人/验收人`；
   - **出总结必须高亮**：哪几项判定是降级产物、因此不是独立审计（k3dge 输出面 + agent 汇报面）。
2. **不设逐次放行开关**：`--allow-manual-audit` 不采纳；`manual` 是合法档位，机器只逼你说出来。
3. **降级产物不是独立审计**：干活的 agent 不得拿 `manual` 报告自证"审过了"。
   - `escalated` 只有一个含义：审计链整体落 `manual` 且人未确认时，`seal` 不放行。
4. `skip` 只用于不在必做链上的 peer（cache）：记 `HARNESS_SKIP` 即算通过该 stage。
5. `check` / `status` 可读取已落盘的降级事实并复述，但不得自行连 MCP 或跑 peer CLI（§2.3.2）。
   - 本轮取向是把流程调通，不是验证兜底；fallback 可用性由后续里程碑专测。

### 2.5 非目标 (Non-goals)

- 不做服务发现、不做注册中心、不做跨机传输（网络化重开 §2.2 信任边界）。
- 不在 k3dge 内实现任何透镜、评分或报告正文生成（含"顺手算个分"）。
- 不让 k3dge 的出向通道反向成为别人的门禁（peers 不得 import k3dge 判定核）。
- 不把 `Status: Draft` 的决策当作已生效——投递与生效分开（`ADR-0010`/`ADR-0012`）。

## 3. 产生后果 (Consequences)

- **Up**：`"k3dge 使唤 peers"` 从注释变成可判定的架构位置；endpoint 一处定义、两个读者；sidecar 边界因"证据来自进程外"变硬；`AGENTS.md` 常驻行与本 ADR 不再互相否定。
- **Down**：k3dge 开始持有子进程生命周期（spawn / 超时 / 清理 / stderr 归集）。
  - 出向调用冷启动实测 ≈0.81–1.01 s（可接受，CI 会慢）。
  - `escalated` 生效后未装 peers 的机器 `seal` 不可用（刻意）。
  - `.mcp.json` 成为 k3dge 输入（public 面，见 `docs/tasks/archive/M7/2026-09-02-M7-feat-peer_outbound_mcp_client.done.md`）。
- **Reopen when**：① 出向通道跑通一轮 audit/quality（届时转 `Accepted`）；② 需要跨机 / 多用户传输；③ 主流 harness 开始扫 `.agent/`；④ `check` 被要求按文档 `Status` 区分严格度（已登 task）。

---

[^🅰1.1]: 修改：为第 2 条补充作用域声明，明确此约束只针对 `check` 命令，不泛化到 k3dge 其他命令。
[^🅰1.2]: 修改：为第 8 条补充作用域声明（不约束 k3dge 自身流程编排），删除「不得外溢成 k3dge 参数」句（peer 暴露的参数即公共接口）。
