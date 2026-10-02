---
type: REG
severity: P2
status: closed
---

# Incident: `.mcp.json` 坏文件走"跳过 peer 闸"信号——坏配置把自己的缺失检查关了

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为 (Baseline)**：`MCP_JSON_PEER_MISSING` 闸比对"声明 enabled 的 peer ∈ `.mcp.json`"。
  `mcp_server_names` 的 `None` 是**唯一的**跳过信号，语义＝"文件不存在，没有可比的东西"
  （ocr-261 的 docstring 承诺；消费方 `pipeline_schema._validate_peers`、`cli/mcp_peers` 按 `is None` 分支）。
- **现存破损 (Treatment)**：ocr-261 只修了"文件在但 `mcpServers` 不是表 ⇒ `set()`"，
  **坏 JSON 与非对象根仍返回 `None`**（解析失败/根非对象在 `load_mcp_document` 折成 None，
  `mcp_server_names` 的 `data is None` 分支把"文件在、内容坏"重新读成"没有可比的东西"）：
  `.mcp.json` 被截断/手滑写坏 ⇒ peer 闸静默跳过，而闸的开关恰恰捏在被检查文件自己手里。
  实测（修复前）：
  ```python
  from k3dge.engine.mcp_json import mcp_server_names   # ws 内 .mcp.json = "{ not json"
  mcp_server_names(ws)      # None ⇒ 下游 skip（stderr 无声）；应为 set()+WARN
  ```
  `cli/mcp_peers.cmd_mcp_probe` 的三分措辞也靠这个 `None`——它至少还打印了"读不出/形状不对"，
  判定面（check/align/seal）则完全无声。
- **复现路径**：任意工作区把 `.mcp.json` 改成 `{ not json` 跑 `k3dge check`（修复前 peer 闸不响）；
  回归测 `tests/unit/engine/test_mcp_json.py::TestMcpJson::test_broken_json_is_present_not_missing`
  （含空文件、`[]`/`"text"`/`123` 根、缺 `mcpServers` 键、空表五张脸）。

## 2. 根因剖析 (5 Whys)

1. 为什么坏 JSON 还是 None？修 ocr-261 时把"表形状坏"这一支从 None 翻成 set()，
   但 None 的**产生点**在更上游（`load_mcp_document` 的解析失败/根非对象），翻漏了。
2. 为什么会翻漏？判据（三张脸）写在 docstring 里，实现分成两个函数——文档承诺的
   "None 只表示缺失"没有对应的**逐形状参数化测试**兜底，测试只覆盖了改到的那一支。
3. 为什么静默？`load_mcp_document` 的 `except (OSError, ValueError): return None` 不出声；
   只有 `mcpServers` 非表那一支加了 WARN ⇒ 坏文件的出声面比缺失文件还小。
4. 为什么方向要紧？peer 闸是"外部 harness 能不能被拿到"的判定；坏配置比缺失更可疑
   （有人动过），却拿到更宽的待遇（直接跳过）＝把 fail-open 奖励给损坏。
5. 深层：一个 Optional 返回值承载两种事实（缺失/不可读），消费者按"跳过"解释第二种——
   三值语义（缺失/坏/有）必须编码成**可区分的返回值**，而不是共用 None。

## 3. 防退化动作清单

- `src/k3dge/engine/mcp_json.py::mcp_server_names`：文件在 ⇒ 一律非 `None`；
  坏 JSON/根非对象/缺表 ⇒ `set()` + WARN（三种出声各自措辞），只有**不存在**才是 None。
- `src/k3dge/cli/mcp_peers.cmd_mcp_probe`：措辞分支不再依赖 `mcp_server_names is None`，
  直接看 `load_mcp_document`（缺失/坏/无声明 三句话，保留 386 的区分度）。
- 测试面（`test_mcp_json.py` 重写）：五张脸逐一参数化＋写文件路径走 `_MCP_CONFIG_REL` 单源＋
  WARN 可观测断言（redirect_stderr）＋端点**负载**与文档透传断言（t-149 顺带）。

## 4. 经验灌入

- 修"三张脸"必须**逐脸建测**，半修（只翻一支）＝ docstring 与实现的下一次分叉；
  用形状×返回值×出声面的矩阵当验收单。
- Optional 返回被消费成"跳过"信号时，任何"存在但坏"都不得复用该信号；坏 ⇒ 显式值＋显式声。
