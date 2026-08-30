---
Status: Accepted
Date: 2026-08-27
Deciders: Core Maintainer
---

# ADR 0022: 协议调度 — 路径路由的确定性装载

## 1. 上下文 (Context)

长会话 Agent 的两类退化已被反复观察：**Context Dilution**（规则淹没在噪声中）与 **Self-Rationalization**（为上一轮推演做合理化辩解）。将规则抽离为独立协议、在每次动作前重置注意力，方向正确，但落点有分叉：

- **模式 A（Agent-Pull）**：Agent 自觉调工具拉协议。优点是不越权；缺点是"调不调"仍是概率事件。
- **模式 B（Harness-Push + Ephemeral）**：k3dge 拉起无状态子会话、物理清空历史。此路违反 **ADR 0006**——k3dge 是 sidecar gate，不拥有、不重实现 agent runtime；会话上下文归宿主 harness（OpenCode / Claude Code / DSH / Codex）。

结论：k3dge 只做"协议解析 + 事后门禁"，会话生命周期归宿主 harness（ADR 0006 边界）。

此外，单纯"拉协议"只证明*检索到*，不证明*装载进注意力*。若协议里写死静态口令，Agent 只需 `grep` 那一行即可绕过——必须升格为**动态内容口令**。

## 2. 决策 (Decision)

1. **路径即路由键，协议即上下文**：Agent 在写任何文件前，先把目标路径交给 `k3dge protocol resolve --path <file>`（或 MCP `k3dge_protocol_resolve(path=...)`），由脚本确定性返回该加载的协议全文。未命中 `[paths]` 的路径走 base spec（协议增强、不替代，避免协议碎片化）。
2. **路由是配置驱动的确定性映射**：`.agent/protocols.toml` 的 `[paths]` 段用 glob 绑定 `路径 → task_type`，按**特异度三元组 `(LiteralSegmentsCount, -WildcardSegmentsCount, PathDepth)` 降序取首命中**（如 `docs/reviews/**` 覆盖 `docs/**`）；`[protocols]` 段绑定 `task_type → 协议文件`。加协议只改这两段，不碰代码。**同一特异度三元组且重叠命中同一文件属严格平局，报 `PROTOCOL_REGISTRY_INVALID`**（见决策 5 门禁）。
3. **静态口令否决，动态内容口令采用**：`ProtocolResolver.challenge(target, task_id)` 返回 `sha256(normalize(protocol_text) + task_id)[:12]`。Agent 只有把协议**全文装入本次会话**才能答对——这是"注意力已重置"的密码学级 load-proof，检索式绕过失效。无协议映射返回 `None`（不强制戴帽）。答题与登记在 IO 边界第二阶段完成（见**门禁 task** 的 `attend`/`put`/`edit --answer` 两阶段时序），`get` 仅发题、不接收 `--answer`。
4. **软关卡，不硬拦截**：pre-tool 硬闸被否决——agent 够得到的一切（钩子、转盘凭证、协议文件）都只是约定，可绕过/直接读/编造，无法物理强制。改为：
    - *load/understand 软验证*：`verify`（`k3dge protocol verify` / MCP `k3dge_protocol_verify`）返回 `pass` / `advise` 的 advisory verdict；`advise` 附整改清单（"劝返"），**从不做硬拦截**。
    - *持续偏离上报*：`write_incident` / `k3dge protocol report` 把"劝返后仍我行我素"的偏离写入 `docs/incidents/INC-*.md`，供人可见。
    - *真正硬地板在 agent 够不到处*：L3 `k3dge check` 跑在 **服务端 CI + 分支保护**，agent 合不进主干除非过门禁。k3dge 提供 `verify`/`report` 与 `check`，**不自己当拦截者**（ADR 0006）。
5. **注册表受静态门禁**：`validate_protocols_config` 接入 `ConsistencyEngine.evaluate`，对 `.agent/protocols.toml` 做纯静态硬校验——文件不存在优雅跳过，存在则 100% 严格：悬空协议文件、空注册表、`[paths]` 指向未注册键、以及**同特异度三元组重叠平局**均报 `PROTOCOL_REGISTRY_INVALID`。协议与磁盘物理一致，无 404 悬空引用。
6. **本协议调度是 ADR 0012「规则=协议切片」的运行时落地、ADR 0019「protocol pack」的确定性解析器半边**：k3dge 负责"解析哪份协议 + 事后门禁"，绝不触碰会话生命周期。

## 3. 产生后果 (Consequences)

- **正**：Agent-Pull 的"伪确定性"被堵——路径路由让"调哪份"零模型判断，动态口令让"是否真装载"可验证；全程不越 ADR 0006；注册表受 `k3dge check` 防漂移。
- **负**：软关卡只降概率、不保依从——agent 若决意绕过，`verify`/`report` 都拦不住。唯一硬保证是服务端 CI 的 `k3dge check`（L3）+ 分支保护。
- **负**：当前 `docs/protocols/` 仅有 `audit_default.md` / `verify_default.md`；新增协议（adr / incident / task / protocol 四类）须同步补 `[protocols]` 与 `[paths]`，否则受 `PROTOCOL_REGISTRY_INVALID` 拦截（四件套同步见各 task 实现清单）。
- **何时重开**：若某 harness 能提供 agent 够不到的 pre-action 强制（如服务端策略网关），可重新评估硬闸；在那之前坚持"软关卡 + 上报 + CI 硬地板"。
