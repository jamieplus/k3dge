# Security

本仓的设计目标是降低 vibecoding agent 漂移，不是安全边界本身。

- **漏洞报告**：请不要贴到公开 issue/PR。先邮件或私聊维护者（`jamieplus`），描述受影响路径与复现步骤，给我们合理时间再公开。
- **不要把 secret 入仓**：`K3DGE_ATTEST_SECRET`、`.mcp.json` 对等 harness 的路径/地址、`.agent/session.json`、`.ua/` 产物一律走 `.gitignore`/本机配置，不进 git。
- **Attest 语义**：未设 `K3DGE_ATTEST_SECRET` 时 `k3dge-commit:` 只是「威慑」（公开常量可伪造）；真证明必须由 CI 用同一 secret 复算。不要把这个 token 当认证凭据。
- **不要在门禁逻辑里自证闭环**：`audit` 必须由第三角色生产/审计，按 ADR-0006 sidecar 语义执行。

## 附注

`AUDIT-QWEN-STATUS.md` 是一次历史 OpenCodeReview 状态的调试留痕，不属公开文档；开源前建议移走或改名归档。
