---
status: idea
milestone: M7
priority: P1
date: 2026-09-04
---

# 首案真跑前遗留清单（k3dge 侧）

- **Status**: idea
- **Milestone**: M7
- **Priority**: P1
- **可检索摘要**: 十单收口＋G1/G2 后清点：G3 封板判定未换源（seal 仍走 scaffold 旧链）、G4 号段发放与席位身份未实现、.mcp.json 解释器靠 landing、§7 复用预筛三条件未实现、audit 四动词 CLI 烟测欠账
- **Date**: 2026-09-04

## 已确认意图

首案（k3dge 自审 M7，src 入检，人工坐席）**不需要**本清单任何一项即可开跑；本清单是把"跑通一次"升级为"每次封板都走棘轮"之前的挂账，防止聊完即忘。

## 边界与拆分

- 席位侧（seat_prompt 活体首用、seat launch 棘轮化、席位宿主 PATH）归 k3dit 仓同批任务，见 `k3dit/docs/tasks/2026-09-04-feat-seat_adapter_ratchet_backlog.md`。
- 每项独立可授可拒，不打包授权。

## 验收

- 每项完成后在本文件勾除并指向证据；全清后本单 done。

## 挂账明细

1. **G3 · seal/`milestone audit` 换源棘轮单**：`on_seal_enter` 改走 `audit_flow.submit_audit` → 工单中间态（`ratchet_open` 已有，但封板状态机不认识"待单"）→ collect 落位后复判。旧 scaffold 链（`k3dit_run_audit_flow`）届时降为 manual 档。验收：`k3dge milestone audit <id>` 全程无 agent 代笔报告。
2. **G4 · 号段发放**：`claim_round` 随单发 `next_ids`（A/F 段），账本拒绝无源 ID 与撞号。验收：两席撞号回归测。
3. **G4 · 席位身份登记**：claim 时登记审计席名；终态翻转（fixed 等）校验"签席 == 登记审计席"。`--role` 自报制的诚实边界收窄（契约"seat 诚实性归人"保留）。
4. **`.mcp.json` 解释器固化**：k3dit/k3che/k3lity server 由 `"python"`＋landing 改为各仓 venv 绝对路径（demo 已验证该形）。验收：doc-audit/audit 活体各一次，`[PEER-MCP] landed` 警告消失。
5. **CLI 四动词烟测欠账**（submit/status 已补；advance 带 present_pushed、close 待补）：`audit submit|status|advance|close` 各自 no-peer rc1 不崩的成组测试（本轮只补了 submit/status；⑩ 亮账时只测两个，违纪实锤入账）。
6. **§7 复用预筛**：三条件（闭环报告＋当场重算 tree oid 比对 baseline＋lens_version 相等）在人工入口实现短路，痕迹行 `PRE-FILTER` 落 log。验收：无变更重跑 audit 提示"无审计需要执行"且 logs 有行。

## 首案活体新增（09-04 晚，席工单回改清单）

- **A/F 号段纪律**：工单未明说"审计席只用 A 段"⇒ 首席把 7 条发现全用了 F 段。修：seat_prompt 加"你是审计席，用 A 段号；F 段留给修席"。
- **note ≤80 字符**：席落的三枚钉 note 超宽被 `markers` 判 PROBLEM（闸抓住了，席没看自己的 --check 输出）。修：工单里带"落钉后跑 `markers --check` 自检"。
- **号段不可增补**：修席的新发现（cache 测试读真实 .k3che 状态＝环境脆弱）因 F 段耗尽无处登记。设计缺：claim 应能按已用号段续发。
- **冲突重试无动词**：`merge 冲突→人工 rebase→重试` 的重试步只能进引擎手调 `merge_back`；且 worktree rebase 落 detached 需手动 update-ref。缺 `k3dge audit merge <milestone>`（幂等重试）。
