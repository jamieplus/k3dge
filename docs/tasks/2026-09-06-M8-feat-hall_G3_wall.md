---
status: idea
milestone: M8
priority: P1
date: 2026-09-06
---

# G3: W1 席目录墙 + 签名钥验签（先 opencode/pi 两宿主）

- **Status**: idea
- **Milestone**: M8
- **Priority**: P1
- **可检索摘要**: Hall spawn 窗口时建专属目录+deny-by-default 权限配置+env 清洗并校验，做"Hall 按窗 scope 把审计线现场拷进各窗"取代"席碰仓"；每窗一钥文件，collect验签、不匹配拒收；前置依赖 G3b 探测结论
- **Date**: 2026-09-06

## Intent

W1 从散文变成机制：目录墙 + 钥验签。先两宿主（opencode/pi），其余宿主按 G3b 矩阵后续扩展。席用原 seats 机制经配置自动起（`launch`/fire-and-forget 已有），本 task 只加墙（目录+钥+校验），不新建派席机制。本 task 与 G2 同为 ADR-0027 Accepted 双门之一。

## Notes

- 物化裁剪：Hall 按窗 scope 把审计线现场拷进各窗目录（只读拷贝/只读拷贝+清单/可写 scratch/修席经 Hall 收回线）；判读窗永不直接操作消费仓 `.git`。
- 钥：同信任域不做防伪，每窗一钥文件（ed25519），sign/验签在 Hall；自报 `--seat` 名不再作为身份。
- 穿墙测试是 G7 的事，本 task 只做到"配了墙 + 人肉窗能跑通"。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：目录/root/权限配置/env 清洗属 Hall；宿主 CLI 方言属 seats 适配层（不外溢契约）。
- 边界检查：Hall 不读席输出语义；席拿不到 Hall 计数与他窗目录。
- 桩子先行：无真席可测——dummy 席进程（sleep+回包）验证墙配置生成与校验逻辑。
