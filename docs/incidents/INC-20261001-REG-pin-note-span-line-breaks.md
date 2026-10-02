---
type: REG
severity: P2
status: closed
---

# Incident: 钉正则的行界只认 `\n`——`\r`/`\v`/`\x85`/`\u2028` 分隔的文件里，前一枚钉的 note 跨行吞掉下一枚钉

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为 (Baseline)**：钉是**行级**事实（契约 §8：行首注释 + `k3dit:<state> <id>`），
  "行"的权威口径＝`str.splitlines()`（code-11：`strip_pins` 按 splitlines 索引删行，
  `_line_starts` 已同口径认 `\r \n \v \f \x1c-\x1e \x85 \u2028 \u2029`）。
- **现存破损 (Treatment)**：`MARKER_RE`/`MARKER_RE_MD` 的 note 用 `[^\n]*?`、行尾锚用
  re.M 的 `$`——两者都**只认 `\n`**。出现其它行界时，note 一路跨过行界把下一行的钉
  当正文吃掉。实测（修复前）：
  ```python
  from k3dge.engine.markers import parse_text
  src = "x = 1  # k3dit:pending A1 first\ry = 2  # k3dit:pending A2 second\n"
  parse_text("src/a.py", src)   # → 1 枚（只剩 A1，note 里黏着整行 A2）；应为 2 枚
  ```
  同样的输入把 `\r` 换成 `\v`/`\x85`/`\u2028` 结果一致。后果面：`audit_verify` 用同一
  正则数钉（findings ↔ 报告行数对账）⇒ 少计 open 钉；`closure_ok`/`open_samples`
  同理 ⇒ **待修被读成已清**，正是结项判据最不能错的方向。
- **复现路径**：上述 snippet 在 `456dda9..HEAD` 修复前代码可复算；回归测
  `tests/unit/engine/test_markers_deep.py::TestLineIndex::test_lone_cr_source_parses_with_right_line_numbers`
  与 `test_all_splitlines_boundaries_count_as_lines`（九个行界逐一代入）。

## 2. 根因剖析 (5 Whys)

1. 为什么两套行界？code-11 修的是**行号**（`_line_index`/`_line_starts`），匹配侧
   （note 字符类、`$` 锚）没人对账——"一处修口径"留下了第二处旧口径。
2. 为什么 `$` 只认 `\n` 没被察觉？re.M 的 `$` 语义少有人背；fixture 全是 `\n`/`\r\n`
   （`$` 恰好停在 `\n` 前，`\r` 落进 note 再被 `.strip()` 抹平——CRLF 把缺陷盖住了）。
3. 为什么测试没抓到？行号守卫的 oracle 自己就是 `count("\n")+1`（t-160）——用错的
   口径验错的实现，恒绿。
4. 为什么扫描窗从没出现非 `\n` 行界文件？仓内文件都是 LF；缺陷面在**外来树**
   （worktree/审计 stage 复制的下游仓、Windows 检出）——正是 `strip_pins` 的主场。
5. 深层：同一文件里"行"的定义出现两份源（正则字符类 vs `_LINE_BREAK_RE`），
   规则 10 的反例——口径没沉成单一常量。

## 3. 防退化动作清单

- `src/k3dge/engine/markers.py`：`_LINE_BREAK_PAT` 提为**唯一源**；`_LINE_BREAK_RE`、
  两个钉正则的 note 类 `_NOTE_NOT` 与行尾锚 `_LINE_END`（行界 lookahead）全部由它派生。
- 回归测（`test_markers_deep.py`）：九种行界参数化 sweep；lone-`\r` 文件的
  `parse_text` 端到端对账（行号＋枚数）；oracle 改由 `splitlines(keepends=True)` 推导。
- 契约面：`k3dge sync` 回写 engine 契约哈希（常量值入哈希，实测有漂移）。

## 4. 经验灌入

- 修"口径"要**扫全用同一口径的所有点**：行号对齐了 splitlines，匹配/锚没对齐＝半修。
  凡两份实现（正则 vs 内建方法）共享一个概念，概念本身要成为常量，两侧引用它。
- 覆盖 CRLF 不等于覆盖 `\r`：被 `.strip()` 抹平的差异最会伪装成"已支持"。
