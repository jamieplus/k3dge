---
id: INC-20260910-CON-audit-merge-doc-drift
type: CON
severity: P2
target_milestone: M8
discovery_date: 2026-09-10
status: closed
root_cause_harness: k3dge
action_task_ref: docs/reviews/2026-09-10-doc-audit-docs.md
---

# Incident: 合并审计模块/postmortem 落地后设计文档滞后于已决行为

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为**: 设计文档是"已落实现实"的单一投影——角色集 = `audit/cache`；钉＝写源、账本/报告＝投影；`fixed` 生命周期只有 §2.7 四合口径。
- **现存破损**（合并 + pin-only 迁移后文档未同任务跟随）: 独立 Doc Audit 首轮报 **待修 7**：
  - `D-1` ADR-0025 §2.2/§2.3 仍写"复核删 fixnote 产生 fixed"，与本篇 §2.7 自相抵。
  - `D-2` ADR Note 裸引不存在的 ADR-0026/0027/0028，`analyze_adr_coverage` 报 `pointer_dangling`。
  - `D-3` 新增就地修订 Note 缺可复跑过闸证据。
  - `D-4` `audit_default.md`/`AGENTS.md`/`rules/04` 仍把钉当"只读指针、理由只写报告"。
  - `D-5` `AGENTS.md` §12 触发表 `ratchet_open` 重复两行。
  - `D-6` k3dit spec 仍写判断窗"写 artifact.json"，违 §2.7 钉-only+心跳。
  - `D-7` `peer_contract` §0/§4 仍列 quality 角色/产出方，与已删 `[roles.quality]` 冲突。
- **复现路径**:
  ```bash
  .venv/bin/python -c "import sys;sys.path.insert(0,'src');from pathlib import Path;\
from k3dge.engine.doc_catalog import analyze_adr_coverage as a;print([f for f in a(Path('.'))['findings'] if f.get('type')!='scope_overlap'])"
  # 曾 => pointer_dangling ADR-0026/0027/0028
  grep -n "标记只是指针\|不出正文\|只写本表" AGENTS.md .agent/rules/04-milestone.md docs/protocols/audit_default.md
  grep -n "ratchet_open" AGENTS.md   # 曾 => 2 行
  grep -n "artifact.json" /Users/jamie/Workspace/k3dit/docs/specs/k3dit/spec.md  # 曾 => 判断窗写见
  ```

## 2. 根因剖析 (5 Whys)

1. 为什么滞后？ → 行为/代码先落地（ratchet pin-only、审计模块合并），设计/契约/规范文档未在**同任务**改。
2. 为什么同任务没改？ → 改动跨两个仓、多个文档类型（ADR/contract/rules/spec），无"改行为必带文档"的机器锚。
3. 为什么 ADR 自相抵能幸存？ → §2.7 经 ⑫⑬⑭ 连续就地修订，只重写 §2.7 段，未扫同篇 §2.2/§2.3 的旧措辞。
4. 为什么契约滞后？ → 合并批只改了 `pipeline.toml`/`role`，未回改 `peer_contract §0/§4`；契约不在 `k3dge check` 的语义闸内。
5. 为什么未被闸拦？ → `k3dge check` 是静态结构闸（T-01）；文审 `doc-audit` 非阻断且此前未跑。

## 3. 防退化动作清单

- [x] 全部 7 条按报告修完，独立复审 **待修=0 / 已修=7**（`docs/reviews/2026-09-10-doc-audit-docs.md`）。
- [x] ADR-0025 §2.6 增「修订纪律」：改变行为的就地修订须**同任务**改代码/测试 + `k3dge sync`。
- [x] `rounds.TRANSITIONS` → `conformance.TRANSITIONS` 单源派生（消第二份状态机字面量）。
- [x] `peer_contract §0/§4` 角色收敛为 `audit/cache`；`findings` 产出方改指模块内判读窗。
- [x] 钉写源纪律统一到 `AGENTS.md`/`rules/04`/`audit_default`（+模板镜像）。
- [ ] 候选机器锚（未做）：`k3dge check` 加"行为改动任务须带 doc/spec 更新或显式豁免"的启发式（归 `chore-audit_module_doc_align` 后续）。

## 4. 经验灌入

- 合并/pin 迁移这类**跨文档类**行为变更，必须先列"受影响文档清单"（ADR 同篇交叉段、契约、rules 镜像、spec、AGENTS），再动代码；否则设计债立刻变实现债（本次即例）。
- ADR 就地修订要"扫全篇"，不只改目标小节：旧措辞会在 §2/§3 各处复述。
- 文审是可跑的（k3dit Doc Audit 透镜 + `k3dge_adr_index` 事实）；封板前必须跑，因为 `check` 不看语义。
