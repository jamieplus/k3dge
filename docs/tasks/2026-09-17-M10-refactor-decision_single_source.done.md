---
status: done
milestone: M10
priority: P3
date: 2026-09-17
---

# 判定点单源化：prompt 文案源出 STATE_OPTIONS

- **可检索摘要**: 同一判定点的文案在两处各写一遍且已漂移——`STATE_OPTIONS["seal_ready"].ask`（`审计已闭环（待修=0），封板？`）vs `seal_flow.py` 的 `prompt.ask("里程碑 {id} 审计已闭环，封板？")`。`audit_open` 同形（`agent 修？` vs `审计/质量共发现 {n} 项待修。是否由 agent 修复？`）。修法待定形：一个判定声明 + 两投影（`[NEXT]` / `prompt`）。

## 意图

消除判定点文案的双源。源：`docs/memo/archive/2026-09-16-orchestration-form-exploration.md` 下一步第 5 项（memo 标「先定形再评」）。

## 证据（实测）

```
封板判定
  [NEXT] : STATE_OPTIONS["seal_ready"].ask = "审计已闭环（待修=0），封板？"
  prompt : seal_flow.py:136               = "里程碑 {id} 审计已闭环，封板？"

修不修判定
  [NEXT] : STATE_OPTIONS["audit_open"].ask = "agent 修？"
  prompt : milestone_audit.py:266          = "审计/质量共发现 {n} 项待修。是否由 agent 修复？"

⇒ 同一判定点两处文案，措辞不一致（且 prompt 侧缺「待修=0」、[NEXT] 侧缺里程碑 id）
```

## 待定形（本票的阻塞点）

候选形状：

| 方案 | 内容 | 代价 |
|---|---|---|
| **(a) prompt 源出 STATE_OPTIONS** | `prompt.ask(f"里程碑 {id} {STATE_OPTIONS['seal_ready']['ask']}", ...)` | `audit_open` 有动态计数（`{n}` 项待修），需占位符机制 |
| **(b) 加 `prompt` 参数字段** | STATE_OPTIONS 增 `prompt: {default_yes, countdown}`；文案单源 | 新增字段；`[NEXT]` 与 prompt 共用一句疑问句（与 S7 的陈述式方向相抵） |
| **(c) 明分两投影** | 声明 `fact`（陈述）+ `decision`（疑问主体）；两通道各自渲染 | 结构变更最大；MCP JSON 形状变（`.next.ask`/`if_y`） |

**(a)/(c) 的取舍取决于要不要同时落 S7 的「[NEXT] 陈述式」**——若落，则 (c) 是自然形态；若不落，(a) 更小。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：判定文案归 `nextstep.STATE_OPTIONS`（唯一源）；`prompt` 只负责渲染与收回答
- 边界检查：`prompt.ask` 的 `default_yes` / `countdown` 是**通道行为**，不是文案——是否也单源化待定
- 桩子先行：先定形（上表三选一）→ 再改

## 定形裁定（2026-09-19，用户：本轮做）

取 **方案 (a)**：prompt 文案源出 `STATE_OPTIONS`，加占位符机制。

不取 (c) 的理由：(c) 的前提是同时落 memo §S7 的「`[NEXT]` 改陈述式」，而用户已裁定 B
「只删装饰词」——不变量 1/3/4（问号结尾、options ≥2、播报态无分支）**仍未做**（无实测危害）。
在没有陈述式 `fact` 字段之前上 (c)，等于为一个不存在的投影形状先造结构（规则 12：不单独扩基建）。

## 落地

| 位置 | 改法 |
|---|---|
| `nextstep.ask_text(state, milestone, *, n=None)` | 新增：判定文案单源投影，填 `<id>` / `<n>`；`ask` 缺失时回落 `note` |
| `NextStep._fill` | 支持 `<n>`（取 `self.pending`）——`[NEXT]` 与 prompt 走同一填充 |
| `STATE_OPTIONS["seal_ready"].ask` | `里程碑 <id>：审计已闭环（待修=0），封板？`（补回 prompt 侧缺的「待修=0」+ `[NEXT]` 侧缺的 id） |
| `STATE_OPTIONS["audit_open"].ask` | `里程碑 <id>：发现 <n> 项待修，agent 修？` |
| `seal_flow.py` | `prompt.ask(nextstep.ask_text("seal_ready", id), default_yes=False)` |
| `milestone_audit.py` | `prompt.ask(nextstep.ask_text("audit_open", id, n=pending_total), countdown=60, default_yes=True)` |

**边界（本票的第二个悬案）**：`default_yes` / `countdown` **不**单源化——那是「怎么问」（通道行为），
留在调用点；单源化的只是「问什么」。顺带修掉一处形态错误：旧 prompt 文案里的
「（超时默认修复）」是通道词汇漏进文案（`Prompt.ask` 已自渲染 `[Y/n, 60s default Y]`）。

## 验收（实测）

```
tests/unit/engine/test_nextstep.py::TestDecisionSingleSource
  test_ask_text_fills_placeholders        两态占位符填充正确
  test_prompt_and_next_channel_agree      两投影同一句（ask_text ⊂ render_cli）
  test_ask_text_falls_back_to_note        无 ask 的态回落 note；未知态返回 ""
  test_no_hardcoded_ask_literals_in_src   AST 扫 src/k3dge：`.ask(` 首参不得是
                                          字面量/f-string/拼接 ⇒ 第二源长不出来
tests/unit/engine/test_seal_flow.py::TestGateIdDispatch
  test_seal_prompt_wording_is_single_sourced       实跑 seal_flow，捕获 prompt 输出比对
  test_audit_open_prompt_wording_is_single_sourced 实跑 audit_flow，同上

521 passed, 2 skipped；k3dge check 绿；k3dge sync 回写 engine 契约哈希
```

## Notes

- 与 `2026-09-18-M10-refactor-gate_action_dispatch`（P2）同轮落地：那票管**投影给进程**（闭集判定），本票管**投影给判断主体**（文案单源），memo §S7 的两条对偶约束各归其位。
- memo 归档的前置条件之一（另一为 ADR 投影契约票，已 done）
- 已完成的相邻项：装饰词删除（用户裁定 B，2026-09-17）——那是本项的一小部分，不含单源化
