# Memo: gap-trap 吸收评估（proven-red / PR-body / 多语 gate / "无闸规则即缺陷"）

> **Legacy note（归档 2026-09-21）**：①⑤ 已落，③④ 与“明确不吸收”三项为**判定留档（不做）**。
> - **① proven-red → ✅**：k3dge `docs/protocols/audit_default.md:18`（Pass 4 含 proven-red）；k3dit `docs/guides/audit-method.md:100`、`src/k3dit/mcp.py:46`（`_PASS_FOCUS[4]`）、`src/k3dit/tools/inject.py:36`（写 `facts/new_tests.json`）、`src/k3dit/windows/{code,review}.md`（窗口消费）。
> - **⑤ “可检规则没闸＝缺陷” → ✅**：`AGENTS.md` §12 行（提醒，不硬阻断散文）。
> - **③ PR-body quotes → ⬜ 未做**（`scripts/commit-msg` 仍只有 conventional + attest；`evidence=` / `decision.tsv` 仍只在报告面，未上提交面）。
> - **④ 多语 `.sh` 壳闸 → ⬜ 未做**（`templates/assets/gates/` 不存在；`templates/assets/gate.sh` 只是本仓启动器镜像，与 `scripts/gate.sh` 字节相同）。
> - 附注：「契约选择是最高杠杆」的透镜注记未落 k3dit `audit-method.md`（当时标“可留”，未写）。

- **类型**: 部分落地（①→审计模块 已落；⑤→`AGENTS.md` §12 已落；③④ 判不做）——判定留档
- **念头**: `../gap-trap`（Claude Code skill，"给每条规则装闸"）与我们**同宗不同器**：它有我们没有的三种"测试可信度/门禁"硬闸，且跨语言壳闸思路可借；但它无契约哈希、无生命周期(align/audit/seal)、无审计三权分立。取其长、不动我们骨架。
- **触发场景**: 2026-09-14 会话对比 `../gap-trap` README + `reference/{framework,gates}.md` 与 k3dge 异同。

## 候选（各标"能力增量 vs 现状 + 落点"）
- **① proven red**：**已议定 → 审计模块**（不进 `k3dge check`，check 纯静态）。
  - 白话：新测试必须在**没修过的旧码**上真挂；断言失败才算打中，缺符号/import 失败不算。
  - 落点：k3dge `audit_default.md` Pass 4（fallback 种子）；k3dit 活透镜 `_PASS_FOCUS[4]` + `audit-method.md` Pass 4 + `facts/new_tests.json`（2026-09-15，不跑测）。
- **③ PR-body quotes acceptance**：feat PR 须引 issue 验收行 / 或写明"无 spec 因由"。
  - 增量：把我们的 `evidence=` 尾段 + `decision.tsv` 从"报告栏"提到"提交面"强制。
  - 落点：`scripts/commit-msg` / pre-commit；与我们 §13 证据链同源，勿成第二份。
- **④ 多语 `.sh` gate 模板**：只要 git/grep/awk + 目标仓 test cmd 的壳闸（Go/Rust/Java/…）。
  - 增量：下游**非 Python 仓**现在拿不到我们 `check` 的全部机检；壳闸是"永远能跑"的兜底。
  - 落点：`templates/assets/gates/` 加 `.sh` 变体；`PAIRS` 镜像锁。
- **⑤ "可检规则没闸＝缺陷"**：**已议定 → `AGENTS.md` §12**（提醒，不硬阻断散文）。
  - 白话：你新写了一条机器能判的规则（check 能红的那种），同轮必须配上闸；只写进 AGENTS/rules 没人跑，等于没规则。

## 明确**不**吸收
- 单-agent setup（发现规则→装闸同一 agent）——违 `ADR-0006/0025` 三权分立；我们保持 壳⊥席⊥人章。
- "skill 装进目标仓"形态 + model-gate(必须 Opus)——我们 sidecar 常驻不同路径；但**"契约选择是最高杠杆、错了赔每一轮"这个判断**可留作一句透镜注记（k3dit audit-method，别当代码规则）。
- mutation smoke（翻分支逼模块测试失败）：成本高、脆，先不列候选。

## 关联（指针，勿复述）
- 判据：`ADR-0009`（吸收纪律）、`.agent/rules/09-absorption.md`、`docs/memo/archive/2026-09-13-agent-dev-tools-absorption-eval.md`（同类账，已归档）。
- 现状机制：`scripts/{pre-commit,commit-msg,gate.py}`、`engine/evaluator.py`(L2/覆盖)、§13 证据链、`templates/assets/`。
- 对照物：`../gap-trap/gap-trap/reference/framework.md` §Gates（grep/instruction/ratchet/proven-red/mutation/PR-body）。
