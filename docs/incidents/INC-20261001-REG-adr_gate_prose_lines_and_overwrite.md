---
type: REG
severity: P2
status: closed
---

# Incident: seal 的 ADR 对账闸把**正文顶格示例行**当 frontmatter 判据，且 Rejected 归档撞名静默覆盖

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为 (Baseline)**：`docs/adr` 的字段语法（`Status:`/`Supersedes:`/`superseded_by:`）
  只活在 **frontmatter 区**（ADR AUTHORING/schema）；`reconcile_supersedes` 承诺
  "先只读校验全部声明，全通过才动盘"（ocr-034），且"拒绝覆盖归档事实源"（ocr-193）。
- **现存破损 (Treatment)**：三条同时成立（扫描报告 `2026-09-30-M11-ocr-tests-scan.md`
  t-062/t-063/t-064 指认，复核坐实）：
  1. `_is_superseded`/`_status`/`_FM_SUPERSEDES` 用**全文**行锚定正则——正文里一行顶格的
     `superseded_by: ADR-0026`（文档示例恰好与真字段一字不差）＝假"已标记"⇒ 幂等早退，
     真字段永不写（ocr-390 残留同类）；顶格 `Status: Rejected` 示例行更把**活件**收进 obsolete。
  2. Rejected 归档分支裸 `dest.write_text(text)`：`obsolete/` 已有同名件（编号重用/备份恢复）
     ⇒ **静默销毁归档事实源**，与 Supersedes 分支的同名守卫不对称（该守卫本身也零覆盖）。
  3. "两遍"只覆盖声明相校验：目标不可标记/撞名要到**写相**才发现——前半合法声明先落盘、
     后半才拒 ⇒ 工作区停在"部分生效"（正是该结构宣称要防的形状）。
- **复现路径**（修复前，均可在 `456dda9` 复算）：
  ```python
  from k3dge.engine.adr_gate import _is_superseded, _status
  prose = "---\nStatus: Superseded\n---\n\n# x\n\nsuperseded_by: ADR-0026\n"
  _is_superseded(prose, "0026")      # True（假幂等：字段在正文，不在 frontmatter）
  _status("---\nStatus: Accepted\n---\n\nStatus: Rejected\n")  # 'Accepted'（首个 match 侥幸对；
                                                # 无 fm 的文件里正文顶格示例行则直接判错）
  ```

## 2. 根因剖析 (5 Whys)

1. 为什么全文搜？frontmatter 的"区"从来没被当**解析边界**实现——只有"行锚定"这一半，
   锚定解决了"句中提到"（390），没解决"顶格示例"。
2. 为什么 Rejected 分支漏守卫？它是后补的旁路（"从未生效，直接移走"），补的时候没把
   Supersedes 分支刚立的归档不变量（不覆盖事实源）当**全局**规则读——同类规则的第二处
   实现各写各的。
3. 为什么"部分生效"没暴露？测试只喂**单条**声明（t-063），好/坏混合的排序从不出现；
   写相晚发现的失败在单声明下＝首条即拒，看不出半落。
4. 为什么撞名零覆盖？撞名是"脏仓"形状，fixture 都从干净目录起步；而编号重用/备份恢复
   恰是长期项目会走到的状态。
5. 深层：判据的**归属面**（字段活在哪）没有单点实现（`_frontmatter` 本次补上），
   于是每个调用点各自"差不多对"。

## 3. 防退化动作清单

- `adr_gate.py`：`_frontmatter()` 成为唯一解析边界；`_status`/`_is_superseded` 只在其内搜；
  `_mark_superseded` 改行界实现，只在 fm 区内改写/注入（正文行不是写入靶）。
- `reconcile_supersedes`：计划相做完**全部**只读校验（含标记可行性、归档撞名、Rejected
  撞名）并算好落盘文本；写相只剩 tmp+replace（Rejected 分支获得同样的原子写＋撞名拒）。
- 回归测（`tests/unit/engine/test_adr_gate.py`）：顶格示例行判据两例；好声明＋缺目标/
  不可标记混合 ⇒ 零落盘断言；Supersedes 与 Rejected 各一条撞名拒覆盖；
  ws 外**真实文件**的指针越界＋端到端 `adr_landed`。
- `k3dge sync`：无契约漂移（函数签名未变）；`k3dge index` 重生（新增 `_frontmatter`）。

## 4. 经验灌入

- "锚到行首"只修了子串的一半：字段判据要同时回答**在哪一行**与**在哪个区**。
  解析边界应是一个可引用的函数，而不是每个正则各自的心照不宣。
- 一条不变量（归档不覆盖）在第二处实现时最容易漏——新旁路落地时把同域已有守卫列成
  checklist（此处：tmp+replace、撞名拒、幂等早退）；不对称本身就该红。
