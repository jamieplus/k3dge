# Memo: 硬编码 → 生命周期钩子：可拆面盘点与取舍

- **类型**: 模糊概念（两个候选各缺一次"可复跑危害"，未过 `rule 12 §2`）
- **念头**: 仓里还有哪些部分是硬编码、可以拆成「声明 + 钩子派发」形式；拆了到底赚不赚。
- **触发场景**: 2026-09-21 讨论「k3dge 主持的流程是提交流程还是封版流程」时，追问「这些是不是以生命周期形式构造」，逐处翻代码做盘点。
- **Date**: 2026-09-21

## 判据（不新造，直接引）

| 来源 | 判什么 |
| --- | --- |
| `ADR-0026` §2.1 | 可编排 ⇔ 该过程的「归属」与「判断」同属一个主体，且该主体就是编排者。⇒ 只对「k3dge 自身的步」成立 |
| `ADR-0026` §2.7 | 下游**可配**的只有「走哪些步、什么顺序、失败怎么办、绑哪个实现」；**不可配**＝判据本体（`evaluator` 检查函数、`.schema.json` 结构规则）、投影形状、`gate_facts` 的 code 词表、D 线不变量 |
| `ADR-0001` §2 第 8 条 | 契约只承载**数据**，不含逻辑/表达式（不长第二套判定语言）；未知 id 一律拒绝；坏配置回落缺省 |
| `.agent/rules/12` §2–§4 | 要拆基建 ⇒ 先给「可复跑命令 + 输出」证明危害此刻存在；反例集已判死 `FIXERS` 注册表 + 编排器、大编排器 |

⇒ 本 memo 只问：**在 §2.7 划出的「顺序/开关/绑定」这一层里，还有哪些该钩子化却没钩子化**；判据本体那一侧不在此列。

## 现状三档（证据在路径里）

| 档 | 内容 | 证据 |
| --- | --- | --- |
| ① 已钩子化 | 四个编排单元的 `preconditions/actions/stages_*`、节点性质、peer 角色与传输链、`.schema.json` 文档结构规则、extractor 插件、`PAIRS`、`[NEXT]` 状态表 | `engine/nodes.py:99`（`run_phase`）、`engine/gates.py:75,84-105`、`.agent/pipeline.toml [roles.*]/[peers.*]` |
| ② 判据本体（§2.7 明写不可配） | `evaluator._check_*` 实现、`pure_refs` 的 detector（**只被 pre-commit 消费，`check` 不含**）、`gate_facts` 的 code 词表、`commit-msg` 的 conventional+attest、D 线 | `engine/evaluator.py:433-800`、`engine/pure_refs.py`、`engine/gate_facts.py`、`scripts/commit-msg` |
| ③ 灰区（下方逐条评） | A 三处触发点（清单 + 覆盖面）/ B pre-commit 的 detector 调用序 / C `evaluate()` 检查序列 / D task 状态两套词表 / E `[NEXT]` 进入条件 | — |

## 候选 A —「跑什么」的触发清单散在三处

```
scripts/pre-commit        三层：doc-gate → schema gate → gate.py check
                          （触发面 = _CHECK_PREFIXES/_CHECK_SUFFIXES 硬编码，:55-56；relevant_for_check:59）
engine/worktree.py        _run_landing_gate（:168）：sync → check → doc-gate --scan → pytest
.github/workflows/ci.yml  check --force-full --with-tests / pre-commit --scan / verify-attest（:13,29,74）
```

- 同一件事三份清单、三种粒度；加一道闸要记着改三处（**推断**）。
- **复核修正（2026-09-21）**：三处差的不是「清单写法」，是**实际判据覆盖面**：
  - **只有 `scripts/pre-commit` 触发**：`pure_refs` 的引用/名实/归档/markdown 闸（`check_dangling_adr` / `check_adr_ref_retired` / `check_adr_number_reuse` / `check_report_pointer` / `check_footnotes` / `check_task_consistency` / `check_adr_consistency` / `check_supersede_unreconciled` / `check_markdown_*` / `find_orphan_*` / `find_unguarded_archives`）与排查闸 `DOC_NEW_UNSCREENED`（`find_unscreened_new_docs`）。
  - **`check` 侧的同族覆盖只有一处**：`doc_catalog.validate_docs` 对 `docs/adr/obsolete/*` 跑 `check_retired_adr_dest`（`doc_catalog.py:429-440`）。
  - **两边都有**：`.schema.json` 结构（pre-commit 看 staged 内容，`check` 经 `doc_catalog.validate_docs` 看全量）、README/AUTHORING 存在性（pre-commit doc-gate / 落点闸与 CI 的 `--scan`）、域契约与 L2。
- **兜底声称与实际不符（待实测）**：进程机械提交明确绕过 hook（`worktree.py:104`、`seal.py:408` 用 `--no-verify`，注释称「仍须 attestation，CI 全量验」），但 CI 的「全量」＝`check --force-full --with-tests`＝`evaluator` 的检查集，**不含**上面那批只由 pre-commit 触发的判据（`grep -n pure_refs src/k3dge/engine/evaluator.py` 零命中）。⇒ 这两类判据在机械提交路径上目前无第二触发点。
  - **实例（2026-09-21，本仓自己的提交）**：用 `k3dge commit -a`（内部 `--no-verify`）提交两份新 memo 时，memo 里作例子的 `ADR-9xxx` 字面**没被拦**——`k3dge commit` 只跑一致性 `check`，不跑引用闸；是提交后手工调 `pure_refs` 才扫出来的。
  - **覆盖面比“提交那一刻”更窄**：闸只扫**当次 staged 的受管（非 aux、非 archive）文档**。全量复扫（命令见下）现有 **16 处悬空引用**仍潜伏（archive/aux/活跃 review 都没人再扫）。
    ```
    .venv/bin/python - <<'PY'
    from pathlib import Path
    from k3dge.engine import pure_refs as pr
    ws = Path('.')
    for p in sorted((ws/'docs').rglob('*.md')):
        rel = str(p.relative_to(ws))
        for code, msg in pr.check_dangling_adr(ws, rel, p.read_text(encoding='utf-8')):
            print(code, rel, msg.split(': ', 1)[-1])
    PY
    ```
  - **写法陷阱**：`check_dangling_adr` 先过 `pure_refs.strip_fences`，但它只认**行首**围栏（`^(`{3,}|~{3,})`）
    ⇒ 缩进在**列表项里**的围栏**不豁免**（本 memo 第一版就踩了：示例字面在嵌套围栏里仍被扫出来）；
    inline 反引号也不豁免（有意：真指针常写在反引号里）。安全写法：把围栏提到行首，或写成 `ADR-9xxx`（不匹配四位数字）。
- **缺点**：三处触发点**主体不同**（git / k3dge / GitHub）。CI 那份不属 k3dge 的编排面——k3dge 只是被调用；把它纳入声明等于声称管得住外部。§2.7「字段即契约」：加字段可以，改语义要 ADR。
- **判决**：值得，但**先分清要拆的是哪一件事**——(i)「清单写法」钩子化（把路径前缀→单元写进声明）只是省重复；(ii) 上面的**覆盖面缺口**才是事实本身，而它的解法可能是**补第二触发点**（落点闸/CI 也能跑那批判据），那不叫钩子化。
- **门槛**：覆盖面差异已是**实测事实**（含一个实例：本仓 2026-09-21 那次提交漏检）；但“这算缺陷还是有意留”是意图问题——`ADR-0022 §2.2 🅰1` 已写明「格式在提交时硬闸、`check` 恒静态」⇒ 判为有意留（见 `LEFTOVERS` `PRE-01`/`PRE-02`），形态仍不定。

## 候选 B — pre-commit 里 12 个 detector 的逐个 `for`

- 规则实现已在纯模块，调用序硬编码（`scripts/pre-commit::run_schema_gate`：`check_markdown_bytes` / `check_dangling_adr` / `check_adr_ref_retired` / `check_adr_number_reuse` / `check_retired_adr_dest` / `check_incident_id_redundant` / `check_report_pointer` / `check_footnotes` / `check_task_consistency` / `check_adr_consistency` / `check_supersede_unreconciled` / `check_markdown_text`，另加 orphan×3（`_orphan_warnings`）与归档去向×1（`find_unguarded_archives`，`scripts/pre-commit:214`））。
- 这些 detector **相互独立、顺序无语义** ⇒ 钩子化只省几行 `for`，代价是多一层间接 + 一个必须防空转的面（正是 `rule 12 §4` 里 `FIXERS` 的形状）。
- **判决**：不值得。现有机制（纯函数 + 显式调用 + `gate_facts` 交叉核对测试）已完整解决。

## 候选 C — `evaluate()` 的检查序列

- `engine/evaluator.py:335-358`：域检查 → 版本一致性 → template drift → pipeline → audit trail → docs，硬编码。
- **缺点**：**顺序有语义**——域契约 `fatal` 短路、`staged` 与 `force_full` 互斥语义、测试批跑与改动域耦合。顺序一旦进数据，"致命即停""只跑重活"这些**失败语义**也得进数据 ⇒ 契约承载逻辑，违 `ADR-0001 §2 第 8 条`；且允许关检查＝把门禁开关交给被审方，违 `ADR-0006` 双主体。
- **判决**：不值得，属 §2.7 判据本体。要做最多到「选定单元」，不能到「关掉某检查」。

## 候选 D — task 状态：声明表与判据分家【本 memo 唯一新事实】

```
声明（唯一源，注释明写消费者一律 resolve()）：engine/state_machine.py:5,37,48
  TRANSITIONS + TERMINAL_STATES + resolve()
实际拦合法性：engine/task_index.py:13  _ALLOWED_STATUS frozenset
  ← engine/align.py:82、engine/seal.py:465 使用
写入侧：engine/task_write.py:345-349 正则替换 status，不查 FSM
生产消费者：`TRANSITIONS`/`TERMINAL_STATES` → `summary()` → `k3dge status --json` 的观测件（**不是死声明**）；但 `resolve()` 在 src/ 里零调用——“应用一次转移”在生产路径上由 `task done` 直写 status + align/seal 事后验合法性承担
测试：tests/unit/engine/test_state_machine.py（`resolve()` 本身）；守「名字不撞」有 `tests/unit/engine/test_nextstep.py:407 test_no_state_name_collides_with_task_status`，但**没有**「`TaskState` 值集 ＝ `_ALLOWED_STATUS`」的相等性守卫
```

- ⇒ 同一事实两套词表、无相等性守卫（“声明了却没人用”只针对 `resolve()`，表本身有 status JSON 消费者）+ `§13 证据链` 缺“到达”环。
- **可复跑实验（待做）**：把 `deferred` 从 `TaskState` 删掉（或改名），看哪些地方会红——预期只有 `state_machine` 的测试红，`align`/`seal` 的校验不红 ⇒ 漂移面真实但当前无闸看见。
- **缺点**：让写入路径走 `resolve()` 会把合法性判定搬进执行面（现在写入侧不管合法性、只在 align/seal 拦），可能把人手改 frontmatter 的现状路径打红。
- **判决**：值得，但**解法是"收敛"而不是"加钩子"**——删 `TRANSITIONS`（承认状态只用于展示）或让 `_ALLOWED_STATUS` 从 `TaskState` 派生。
- **落地（2026-09-21）**：取后者——`task_index._ALLOWED_STATUS = frozenset(s.value for s in TaskState)`（`docs/tasks/2026-09-21-M11-fix-memo_review_landing.done.md`）。**更正我先前那句「加相等性守卫」**：派生之后「两处相等」类断言就是同义反复（断言的就是那个表达式）⇒ **不加测试**；FSM 侧的真守卫是既有的 `check_completeness`（终态/死锁/可达）。

## 候选 E — `[NEXT]` state 的进入条件

- `STATE_OPTIONS` 只声明 state→fact/options；"什么条件进哪个 state"散在 `audit_trigger` / `nextstep` / `seal_flow`。
- **判决**：不值得。投影形状属 `ADR-0026 §2.2` 明写不可配；且**可调的部分已经可调**（阈值在 `gates.DEFAULTS["audit_trigger"]`：`c2_nesting_max` / `volume_max`）。

## 不引入（勿重提）

| 提案 | 死在哪 |
| --- | --- |
| detector 实现钩子化 / `gate_facts` code 词表可配 | `ADR-0026 §2.7` 不可配面 |
| `commit-msg` conventional+attest 钩子化 | 同上（协议面，碎片化即失效） |
| D 线（席位圈）编排 / 通用 `[hooks]` 段 | `ADR-0026 §2.6` 不可编排 + 不是缺设计 |
| `FIXERS` 注册表 + 编排器、大编排器（Step/Flow/Pipeline）、① 判定式统一形状、② 载体边界 | `.agent/rules/12 §4` + 归档 memo S9（均有"推测性通用性、无实测危害"特征） |
| 候选 B（detector 调用序钩子化） | 顺序无语义 ⇒ 收益仅审美 |

## 横切优缺点（一句话版）

- **赚**：单点声明消除多处清单漂移；异构下游可自定顺序/绑定（`[roles.*]` 已吃到红利）；可断言「声明里每个 id 都有实现与消费者」（现手段是交叉核对测试）。
- **赔**：门禁可被静默削弱（`actions = []`）；契约承载逻辑会长第二套判定语言；调试面变三层（缺省 ∪ 仓内覆盖 ∪ 注册表）；每个新钩子都要三链证据 + 活接入点，而收益是"以后好改"——`rule 12 §2` 不认这种推断。

## 关联（指针，勿复述）

- 判据：`ADR-0026` §2.1/§2.6/§2.7、`ADR-0001` §2 第 8 条、`.agent/rules/12-introduction-discipline.md`、`.agent/rules/08-design-discipline.md`、`ADR-0012`（证据链）。
- 前身：`docs/memo/archive/2026-09-16-orchestration-form-exploration.md`（S1–S5 仅探索记录；S6/S7 已落 `ADR-0026`；S9 筛掉的四项本 memo 不重开）。
- 现状机制：`scripts/{pre-commit,commit-msg,gate.py}`、`engine/{evaluator,pure_refs,gate_facts,nodes,worktree,state_machine,task_index,task_write}.py`、`.github/workflows/ci.yml`。

## 下一步

1. 候选 A、D 各做一次「可复跑命令 + 输出」（`rule 12 §2`）；过线 ⇒ promote 成 `docs/tasks/`；不过线 ⇒ 本 memo 即结论（有意留）。
2. A 若转票：先定它要解的是「清单重复」还是「覆盖面缺口」（后者可能是补触发点，不是钩子化）；涉及声明字段新增 ⇒ 按 §2.7「字段即契约」走 ADR。
3. D 已落地（2026-09-21，收敛为派生；不加同义反复的守卫测试）。
