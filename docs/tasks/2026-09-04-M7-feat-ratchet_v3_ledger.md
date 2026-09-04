---
status: done
milestone: M7
priority: P2
date: 2026-09-04
---

# ratchet v3 exchange implementation ledger

- **Status**: idea
- **Milestone**: M7
- **Priority**: P2
- **可检索摘要**: `ADR-0026`（证据交换拓扑）转正后的施工账：每单自带验收命令，**不存在"整体完成"状态**——只有逐单亮灯；ADR 未转正前整账冻结（deferred 的理由即此）
- **Date**: 2026-09-04

## 边界与拆分（规则 08）

- 事实归属：见 `ADR-0026` §2.1 主权四章——每单只动一个主权域的件；跨域只经 claim/collect 信封字段。
- 边界检查：②③ 只碰 k3dge 消费域；①④ 只碰 k3dit 账本域（不新增内容存储——§2.1 最小化的直接检验是"改动后 k3dit 仓里没有 .pack/.bundle 文件"）；⑤ 纯文本。
- 桩子先行：每单先写"跑法"再写实现；跨进程回归以 `.ratchet_ws` 六步 demo 为底版扩展（它已是"能跑"的实物证据）。

## 前置拍板（ADR-0026 §3 Reopen③ 相关，两题，不定则 ③⑥ 冻结）

- ~~P1~~ **已拍板**：自动合并，冲突升级人工（入 ADR-0026 §2.3）。
- ~~P2~~ **已拍板**：ref 住消费仓 `.git`。

## 施工账（每单=一个可验证增量；✅ 单附完成证明）

| # | 单 | 域 | 状态 | 验收命令（做完当场跑） |
| --- | --- | --- | --- | --- |
| ② | 快照 commit 链＋bundle create（`has` 参数同形状）；链住 store `refs/snap/*`、工作分支住消费仓 `.git`（P2 两界分明；git 拒裸 SHA→每-commit ref） | k3dge | ✅ 09-04 | `test_bundle`/`test_worktree` 绿：同输入两次 commit oid 相等；bundle `list-heads` 可列 |
| ④ | `pack_provenance{config_digest,mode,git,ignore,scrub_keys}` 进 manifest（可复现性件，非防伪——镜头三定案） | k3dge | ✅ 09-04 | 改一行 `bundle.toml` ⇒ digest 变（回归测在） |
| ⑦ | worktree 进程件：ensure 幂等／present 由进程抽取（席位口供退役为交叉核对）／advance＝进程代 commit＋祖先判定＋**CAS 更新 ref**（真分叉拒→升级人工） | k3dge | ✅ 09-04 | `test_worktree.py`：present==手工 markers；非 ff 分叉 raises；快进路径 head==branch |
| ① | claim_round 回传 `bundle{ref,file,commit,config_digest}`（纯字符串搬运，k3dit 不开文件） | k3dit | ✅ 09-04｜claim 回传 bundle{ref,file,commit,config_digest}（submit 参数透传；rounds 零 open()，grep 为证）；k3dit 44→46 含句柄断言 | claim 输出含 bundle 块；`grep -r "\.bundle" k3dit/` 无内容落盘 |
| ⑨ | rounds 角色门：`claim/complete` 带 `role`；非审计角色提交终局裁决 ⇒ 拒（`fixnote` 除外） | k3dit | ✅ 09-04｜role 门：fixed 非审计席即拒；修席新条目限 fixnote/disputed/leftover（申辩合法）——两回归测 | 修席身份提交 fixed → FORMAT 拒绝回归测 |
| ⑧ | `k3dit audit-report <job>`：账本⋈delta 机械渲染器，**审计席运行并署名**；close 门槛改为"已交署名报告" | k3dit | ✅ 09-04｜audit-report 渲染器（处置列封闭枚举修正）＋sign_report 形检+覆盖账本全 id；close 门改「pending_report→署名 done」；collect 未署名只回 PENDING | 两次渲染逐字节等；未交报告 close ⇒ 拒 |
| ③ | 分支写回收尾：closure 自动 merge（冲突停→人工 rebase 确认流）；废单删分支 | k3dge | ✅ 09-04｜merge_back（ff/真merge/conflict→abort 复原+升级；脏守卫放行编排自家写的件——双向前缀白名单）；活体重放 logs/ratchet_demo.py：submit→落标→审计签账→修→签fixed→署名报告→collect **merge:ff、主干带回修复=True**；冲突/脏树/add-add 自愈三回归测 | `.ratchet_ws` 六步 demo 换分支模型回放；abort 后主干零变化 |
| ⑤ | end-flow prune：seal 收口清 bundle/worktree（store 与分支史保留） | k3dge | ✅ 09-04｜prune_finished 挂 seal 钩子（容错不阻断）；demo ⑦：bundles 剩 0、worktree 清、store 与分支史保留） | seal 演示后 `.k3dge/bundles/` 空、`store.git` 健在 |
| ⑩ | 轨A 面板：`k3dge audit submit/status/advance/close` 四子命令（全走 ①–⑨ 已建件） | k3dge | ✅ 09-04｜audit submit/status/advance/close＋bundle create 全走 func 式 CLI（工作区=CWD 与 bundle 同式）；老守卫 assertNotIn(audit) 转正；无对端 rc1 不崩/活体 create 出三件套烟测 | demo 由四命令驱动逐条 exit 0；ff 守卫回归在 |
| ⑥ | 契约 §3/§1.4/§7 按 0026 改写（消 §3↔§7 矛盾）；memo 废案碑两行（随案卷入 k3dit、file:// hint） | 文本 | ✅ 09-04｜契约 v0.6：§3 整段重写（身份/位置、bundle 即宇宙、分支工作现场、主权、present 机器供给、EXPIRED/NO_TARGET 降预留）＋§1.4 结项两步署名＋§7 锁即续期；memo 化石追加四条 | `doc where ADR-0026` 对读；check 绿 |

## 已跑通底版（非本账范围，作验收脚手架）

- 交换三代（tar→tree→bundle 单文件）中 **tree/oid/baseline 链已实装已测**（232/44 passed，`.ratchet_ws` 六步 demo 可回放）；本账从①起为**全新未建**。

## Related

- 决策：`docs/adr/0026-audit-evidence-exchange-topology.md`（**Proposed——转正前本账禁止开工**）
- 主权与写回背景：`docs/tasks/2026-09-04-M7-feat-audit_job_protocol.md`（k3dit）、`docs/memo/2026-09-02-peer-wiring-and-seat-options.md` 废案账
