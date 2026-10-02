---
type: SEC
severity: P2
status: closed
---

# Incident: `write_incident` 的 sanitizer 只转义 0 列 `#`——缩进标题穿透，人看到的 B-T-D 结构可被外部文本伪造

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为 (Baseline)**：`write_incident` 把**外部可控文本**（detail/CI JSON）写进
  `docs/incidents/` 的人读文档；反伪造承诺＝外部内容不得改变 incident 的 B-T-D 四节结构
  （`_block` docstring：「行首 `#` 转义……结构闸仍数到自己的四节」）。
- **现存破损 (Treatment)**：判据 `s.startswith("#")` 只看**顶格**。CommonMark 允许
  ≤3 个前导空格的 ATX 标题：`   ## 2. 我伪造的根因` 不转义、GitHub 渲染成**真 H2**——
  人在事故文档里看到伪造的"根因剖析"，而 `INCIDENT_FORM_INVALID` 结构闸（`^##\s+1\.`
  行锚定）根本不数缩进行 ⇒ 闸与人的眼睛看到的是两份文档。
  实测（修复前）：
  ```python
  from k3dge.engine.protocol import _block
  assert "   ## 2. 伪造" == _block("   ## 2. 伪造").strip()   # 原样穿透
  ```
- **复现路径**：`k3dge incident --from-ci` 喂的 detail 含缩进标题（审计/CI 输出里
  复制粘贴的 markdown 天然带缩进）；回归测
  `tests/unit/engine/test_protocol.py::TestIncidentSlugAndSanitize::test_external_detail_cannot_forge_the_b_t_d_headings`
  （顶格＋缩进两形状，计数口径升级为 `^\s*##`）。

## 2. 根因剖析 (5 Whys)

1. 为什么漏缩进？把"行首 `#`"理解成"字符串第 0 个字符"，而 markdown 的语义是"（缩进后）行首"。
2. 为什么测没抓到？伪造测自己用 `ln.startswith("## ")` 计数——与被测代码**同一个错**：
   数不到缩进行，于是"4 个标题"恰好成立。判据复用了漏洞的形状，守卫与漏洞同盲。
3. 为什么闸不兜底？结构闸（pure_schema）只验"四个必需节在不在"，多出来的伪造节本来就不报
   ——防伪只能靠 sanitizer，它漏了就是漏了。
4. 为什么外部文本会带缩进标题？detail 来自 CI JSON/审计转述，粘贴 markdown 是常态输入。
5. 深层：净化判据与消费方判据必须**同源同形**；此处三处（sanitizer、结构闸、测试计数）
   三种"什么算标题行"的实现。

## 3. 防退化动作清单

- `protocol._block`：判据改 `lstrip().startswith("#")`，转义**保留缩进**（`   \## …`），
  缩进≥4 自动成代码块不渲染标题——两档都不再是 H2。
- 测面：payload 同时含顶格与缩进伪造；计数改 `^\s*##`（与 sanitizer 同口径）；
  断被伪造行以转义形态存在（内容不丢）。
- 同轮 t-227/229：落点断言（`docs/incidents/` 之外＝人看不见、闸查不到）；
  形闸对账改用**仓内权威 `.schema.json`**（旧测抄 fixture 副本＋抓别的测试类的私有
  helper——ship 的 schema 加规则时真 check 红、这测绿）。

## 4. 经验灌入

- 净化/校验类判据要按**消费方语义**写（"渲染后是不是标题"），不是按字符串巧合（"第 0 个字符"）。
- 守卫与被守卫代码犯同一个错时，守卫的存在是假象：计数口径独立于被测形状（用 `lstrip` 数
  一切 `##`），让漏洞在测里**显形**而不是被跳过。
