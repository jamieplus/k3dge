# 审计：Pass 5 简洁性与性能（死代码 / 重复 AST / 临时对象 / 算法复杂度 / IO）

- **Date**: 2026-08-25
- **审计人**: Agent（Muse Spark）Pass 5 单透镜
- **基线**: `70 passed / 1 skipped / 44 subtests`（`.venv/bin/python -m pytest -q`）；`.venv/bin/k3dge check --force-full` → `[GATE SUCCESS] Validated domains: cli, engine, sync, templates`；`k3dge sync` 幂等；4 域 Contract Hash 已同步 `cli 3f89e5… / engine 5c0b13… / sync 819887… / templates b05302…`（见 `2026-08-25-pass4` 实测，不复算）
- **范围**: 仅 Pass 5 — `src/k3dge/**`（`engine/{contract,evaluator,_ts,manifest,version,milestone,diff,spec_schema,models}` + `cli/{main,mcp}` + `sync/generator` + `templates/{pairs,scaffold,assets/*}`）与 `scripts/*`（`gate.{sh,py,ps1}` / `generate-docs.{sh,ps1}` / `init.{sh,ps1}`）；不重开 §5.1 有意留 `F-14/F-15/R3-1/R3-4/A-11/S-13` 与 Pass 3/4 已转 tasks 的 `D-*`/`P4-*`（仅作残余性能债复核）
- **方法**: `read` 全量至行号 + `grep -rn` 消费链 + `PYTHONPATH=src python -c` 小复现 + `diff -u assets↔scripts` + `ast` 热循环分配扫描；每条断言给出产物+消费者+到达方式三链（ADR 0015）；输出 9 列
- **结论**: **有新发现 — 8 项（0 高 / 1 中 / 6 低 / 1 信息通过），0 P0 阻断**。与落地 M1 对齐后：仅 P5-01 转 task；P5-02..P5-07 有意留（各有阈值）；P5-08 通过。无生产阻断，热路径（`k3dge check` selective 无 `--with-tests`）当前 `~2 git 进程 + ~1 spec 读 + ~rglob 解析 + 3 version 读 + 44 TEMPLATE_DRIFT 读`，活跃文件少，OS 缓存足

## 发现（9 列）

| ID | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P5-01 | 中 | P2 | 冗余 | `k3dge_verify_domain_contract` 重复收集同一域 AST：`verify_contract`（`contract.py:271-273` 内 `collect_domain_interface`）后再 `collect_domain_interface` 取 `current_interface`（`cli/mcp.py:121-122`）。同一域源码被完整 `rglob→read→ast.parse/tree-sitter` 两遍（2×IO + 2×AST），仅为在一次 MCP 调用中同时返回 `ok/expected/actual` 与展示用 `current_interface`。当前域文件少（`engine` 10 文件、其余 ≤4），实测毫秒级，但属可避免的 `N` 重复计算；`sync_all` 的 `iface_cache/doc_cache` 已修同类重复，MCP 侧遗漏 | `src/k3dge/cli/mcp.py:104-137` 尤 `121-122`；`src/k3dge/engine/contract.py:231-273` 对照 | 待修 | [tasks/2026-08-25-M1-audit-P5_01_MCP_collect.md](../tasks/2026-08-25-M1-audit-P5_01_MCP_collect.md) | `grep -n "collect_domain_interface" src/k3dge/cli/mcp.py` 命中 `122` 同时 `verify_contract` 内 `273`；`PYTHONPATH=src python -c "import pathlib; print(open('src/k3dge/cli/mcp.py').read()[3800:4200])"` 复现双调用 |
| P5-02 | 低 | P2 | 冗余 | TS 提取器每文件重建 `Language`+`Parser`：`extract_ts_interface`（`engine/_ts.py:69-93`）内 `Language(tree_sitter_typescript.language_typescript())` 与 `Parser(language)` 均在函数体内构造，`TypeScriptExtractor.extract` 每 `.ts/.js` 文件调一次。若域含 `N` 个 TS 文件则 `N` 次 `tree_sitter` 编译期对象分配 + `read_bytes`，热循环临时对象 `N×(Language+Parser+bytes)`。当前仓零 TS 文件（实测 0 命中），`k3dge check` 不触发；但为线性放大的隐藏 `N` 复杂度，且与 `contract.py:151-155` 的 `extract` 热路径耦合 | `src/k3dge/engine/_ts.py:69-97`；调用方 `src/k3dge/engine/contract.py:147-155` `TypeScriptExtractor.extract` | 有意留 | 有意留：本仓零 TS。何时重开：首个 TS 域落地或 `Parser` 构造 >10ms/文件 | `read src/k3dge/engine/_ts.py:69-93`；`grep -rn "extract_ts_interface" src/` 仅 `contract.py:212` 一处转调；本地 `rg "\.ts"` 零业务文件 |
| P5-03 | 低 | P2 | 冗余 | `TEMPLATE_DRIFT` 无条件 44 次读盘/次 `check`：`evaluator.evaluate`（`evaluator.py:218-265`）的脚手架漂移段对 `PAIRS` 22 对每对做 `asset_path.read_text` + `repo_path.read_text`（`.rstrip("\n")` 后比对），**不论** `force_full` 与 `touched` 是否含 `templates` 域。`selective` 下仅改 `engine/contract.py` 一行仍触发 44 读（当前本仓 22 对，`ls scripts/ + assets` 实测 22 diff 同步）。虽有 `is_self_host` 早退（下游跳过），自举仓仍每次必做；G-01/G-02 的修复使下游不再误伤，但未加 `touched` 门控，属 `N+1` 冗余 IO（`N=PAIRS` 常量，`+1` 为每次 check） | `src/k3dge/engine/evaluator.py:218-257` 尤其 `238-248` 循环；`src/k3dge/templates/pairs.py:6-30` | 有意留 | 有意留：自举仓安全优先，`44× <2KB` 在 OS 页缓存内。何时重开：`check` P50 >1s 或 `PAIRS` >40 | `grep -n "TEMPLATE_DRIFT\|PAIRS" src/k3dge/engine/evaluator.py`；执行 `time .venv/bin/k3dge check --force-full` <1s；`python -c "from k3dge.templates.pairs import PAIRS; print(len(PAIRS))"` → `22` |
| P5-04 | 低 | P3 | 冗余 | 每文件每提取器一次 `set.intersection` 临时集合：`PythonExtractor.can_handle`（`contract.py:141`）与 `TypeScriptExtractor.can_handle`（`149`）均 ` _IGNORED_DIRS.intersection(path.parts)`。`path.parts` 为 tuple，需转 set 取交集，热循环（`collect_domain_interface:245 rglob`）中对每个文件最多 2 次临时 set 分配 + `suffix` 再判。等价无分配写法 `any(p in _IGNORED_DIRS for p in path.parts)` 或 `not _IGNORED_DIRS.isdisjoint(path.parts)` | `src/k3dge/engine/contract.py:136,141,149,255`；`src/k3dge/engine/contract.py:136 _IGNORED_DIRS` | 有意留 | 有意留：每次 check ~16 文件，分配 <KB。何时重开：`N>500` 或 `py-spy` 显示热点 | `read contract.py:139-155`；`grep -n "intersection" src/k3dge/engine/contract.py` 命中 2；`PYTHONPATH=src python -c "from pathlib import Path; from k3dge.engine.contract import _IGNORED_DIRS; print(_IGNORED_DIRS.intersection(Path('src/k3dge/engine/contract.py').parts))"` |
| P5-05 | 低 | P3 | 冗余 | `version.py:66-74` 重实现 `manifest.json` 解析：`get_manifest_version` 手写 `json.loads(p.read_text()) + data.get("version")`，与 `manifest.Manifest.load`（`manifest.py:56-67`）的 `JSONDecodeError→ManifestError` 包装与 `package_root` 校验逻辑重复。同一文件在 `validate_versions`/`bump_version` 与 `Manifest.load` 间产生双轨解析，且错误语义分叉（`version.py` 对坏 JSON 返回 `None` 静默，而 `evaluate` 对坏 manifest 报 `MANIFEST_INVALID`）。非热点（每 check 一次）但属重复 AST/IO 逻辑 | `src/k3dge/engine/version.py:66-74` vs `src/k3dge/engine/manifest.py:56-67`；消费方 `src/k3dge/engine/evaluator.py:204-216` 与 `src/k3dge/engine/version.py:93-126` | 有意留 | 有意留：复用 `Manifest.load` 会搅循环依赖感知；静默 `None` 与 `MANIFEST_INVALID` 分工明确。何时重开：抽公共 `manifest.version` 访问器时一并 | `read version.py:66-74` vs `read manifest.py:56-67`；`grep -rn "get_manifest_version\|Manifest.load" src/k3dge --include="*.py"` |
| P5-06 | 低 | P3 | 冗余 | 任务扫描 `glob+read+regex` 双轨重复：`cli/main.py:276-288` `cmd_task done` 的 `tasks_dir.glob("*.md") → read_text → "Status" 替换` 与 `engine/milestone.py:111-129` `scan_milestone_tasks` 的 `glob → read_text → STATUS_RE/MILESTONE_RE` 同构，仅过滤谓词不同（`pattern in name` vs `m_id == milestone_id`）。`milestone.py:265` 甚至 `re-read` `incomplete_reviews[0].read_text()` 第二次。F-15 已将“任务少/OS 缓存够”判为有意留（见 §5.1），本项仅指出调用点重复，跨模块抽 `scan_tasks(predicate)` 可省一次 `glob` 热循环，但收益低于抽象成本 | `src/k3dge/cli/main.py:220-314` 尤 `276-297`；`src/k3dge/engine/milestone.py:111-324` 尤 `117-129,265` | 有意留 | 有意留 — 复用 `F-15` 理由，活跃任务仅 3 个（`ls docs/tasks/*.md` 实测 4 含 README），`glob` <1ms；若活跃任务 >20 或 `scan` 进火焰图前三，再转 tasks 抽 `k3dge.engine.tasks.scan(filter)` | `ls docs/tasks/*.md` + `grep -n "glob.*tasks" src/k3dge --include="*.py"` 命中 2 |
| P5-07 | 低 | P3 | 冗余 | `scaffold.py` 导入时 eager 读 13 个资产：`_asset("agents.md")` 等 13 个顶层常量（`scaffold.py:19-60`）在 `import k3dge.templates.scaffold` 时即 `resources.files(...).read_text()`。`k3dge check/sync` 等仅用 `PAIRS` 或 `Manifest` 的进程仍承担 13 次包内资源 IO + 字符串常驻（各 <5KB）。`resources.files` 在可编辑安装下走文件系统，冷启动轻微放大 | `src/k3dge/templates/scaffold.py:12-60`；消费方 `src/k3dge/engine/evaluator.py:220` 仅 `from k3dge.templates.pairs import PAIRS` 却连带触发 `scaffold` 模块？实测不导入 `scaffold` 则不触发，但 `k3dge.templates.scaffold` 被 `k3dge-init.sh` 以外仅 `tests` 调 | 有意留 | 有意留：13 文件共 <40KB，`k3dge check` 不导入 scaffold。何时重开：启动基线 >200ms | `read scaffold.py:12-60`；`time .venv/bin/python -c "import k3dge.templates.scaffold"` ~60ms |
| P5-08 | 信息 | — | 通过 | 全量通过项（作基线）：① 死代码：`grep -rn "def " src/k3dge --include="*.py"` 56 定义均有消费者（`mcp` 4 符号由 `FastMCP` 装饰器注册，外部 harness 为事实消费者；`cli/main` 7 命令由 `build_parser` 注册；其余 `engine/*` 均被 `evaluator/contract/sync` 直调），无生产死函数 ② 重复 AST：`sync_all` 已以 `iface_cache/doc_cache` 修 F-13 双收集（`generator.py:178-185` 一次 `rglob` 产两缓存），`evaluator` 每域一次 `collect` 为必要而非重复；剩余仅 P5-01 MCP 一域双取 ③ `PAIRS` 22 对 `diff -u assets↔repo` 全 Same（`gate.{sh,py,ps1}/generate-docs.{sh,ps1}/init.{sh,ps1}` 等 7 脚本 + 15 模板），`scripts/` 无孤儿文件 ④ 大文件全量读：spec 最大 `cli/spec.md ~6KB`，`interface` 合并 <100KB，F-14 O(N²) 有意留仍成立 | `src/k3dge/** 56 def` 清单 + `scripts/` 7 文件 + `src/k3dge/templates/pairs.py:6-30` + `src/k3dge/sync/generator.py:178-197` | 已验证 | 无需转 tasks；回归锚：`k3dge check --force-full --with-tests PASS` / `pytest 70 passed` / `diff assets↔scripts OK` | 同左 + `diff -u src/k3dge/templates/assets/gate.* scripts/gate.* → 0`；`grep -rn "def " src/k3dge` + `grep -rn "@mcp\." src/k3dge/cli/mcp.py` |

## 已复核不重开（Pass 5 相关但已有定论）

- **F-14 / LR-5** `_replace_between_all` 多轮切片 O(N²) — `sync/generator.py:38-54`（`performance.md#F-14` 已判有意留：单 spec ≪100KB，单文件微秒级，改单遍扫描易错折叠语义）。本次 `wc -l docs/specs/engine/spec.md` 实测 142L 有意留仍成立
- **F-15 / LR-6** `milestone` 重复读盘 — `milestone.py:111-129,132-201,204-324` 与 `evaluator.py:218-265` 的任务/评审全量 `read_text`（见 `docs/architecture/overview.md:112`）。活跃任务 3、评审 11，OS 页缓存足；新增 PAIRS 44 读属 F-15 同类但已在 P5-03 单列为候选，不推翻 F-15 主结论
- **R3-1** 三处域表行 — `scaffold:26-34 / generator:157-165 / overview:27-34`（ADR 0002 判据/投影不可合并，`SUMMARY.md:15`）
- **R3-4** 函数内 `import subprocess` — `evaluator.py:36-38` L2 冷路径（见 `SUMMARY.md:16`），本次 `check` 无 `--with-tests` 不触发
- **D-02/D-04/D-10** 结构债（策略注册/哈希文件名锚/IO 不对称）— D-04 已转 M1 task；D-02/D-10 有意留。Pass 5 不增开

## 证据链（ADR 0015 / §13）

| 断言 | 产物（已读/已跑） | 消费者 | 到达方式 |
| --- | --- | --- | --- |
| MCP 一域双收集 | `src/k3dge/cli/mcp.py:104-137 read` + `src/k3dge/engine/contract.py:231-283 read` + `grep -n collect_domain_interface src/k3dge/cli/mcp.py:122` | 外部 harness 经 `mcp.run` stdio 调 `k3dge_verify_domain_contract` | `FastMCP @mcp.tool` 注册，`contract.verify_contract` 硬编码 `collect_domain_interface` |
| TS 每文件重建 Parser | `src/k3dge/engine/_ts.py:69-97 read` + `grep -rn _ts src/k3dge --include="*.py"` 一处转调 | `contract.collect_domain_interface` → `TypeScriptExtractor.extract` → `extract_ts_interface` | `contract.py:147-155` 遍历 `_EXTRACTORS` 硬编码调用 |
| TEMPLATE_DRIFT 无条件 44 读 | `src/k3dge/engine/evaluator.py:218-265 read` + `PAIRS 22 len` + `time .venv/bin/k3dge check` | `k3dge check`（`cli/main.py:53-71`）每次 `evaluate` | `evaluator.evaluate` 内联 `for asset, rel in PAIRS: read_text` 无 `touched` 门控 |
| `intersection` 临时集合 | `src/k3dge/engine/contract.py:136,141,149 read` + `grep -n intersection` | `collect_domain_interface:245 rglob` 热循环 | `can_handle` 硬编码 `set.intersection` |
| version 重实现 manifest 解析 | `src/k3dge/engine/version.py:66-74 read` vs `src/k3dge/engine/manifest.py:56-67 read` | `evaluator.validate_versions` / `bump_version` | `version.py` 手写 `json.loads(read_text)` |
| 任务扫描双轨 glob | `src/k3dge/cli/main.py:276-297 read` + `src/k3dge/engine/milestone.py:111-129,265 read` | `k3dge task done` 与 `milestone align/seal` | `Path.glob("*.md") + read_text + REGEX` 硬编码两套 |
| scaffold eager 13 资产 | `src/k3dge/templates/scaffold.py:12-60 read` + `python -c import timing` | `python -m k3dge.templates.scaffold` / `k3dge-init.sh` | 模块顶层 `_asset()` 执行 |
| 无死代码/双收集已修 | `grep -rn "def " src/k3dge --include="*.py"` 56 个 + `diff -u assets↔scripts 0` + `sync_all:178-185` 缓存 | `k3dge check/sync` 全链路 / `PAIRS` 自检 | 硬编码 `collect→iface_cache/doc_cache` + `@mcp.tool` + `build_parser` 注册 |

## 方法与复现指引

- 读 `docs/reviews/SUMMARY.md` 定相关性，仅对 `src/k3dge/**` + `scripts/*` 做 Pass 5 单透镜，不扩至 `docs/**` 软资产
- 每项均 `read` 源码至行号 + `grep -rn` 消费链 + `PYTHONPATH=src python -c` 小复现（见 Verification 列），避免“目录名即证据”
- 热点判定：`collect_domain_interface:245 rglob` 与 `evaluator:238 PAIRS循环` 为唯二热循环；`normalize:222` 的 `" ".join(line.split())` 与 `compute_hash:227 sha256` 均 <100KB 输入，分配 <KB，不入火焰图
- 误用阈值：`P5-02` 需 `N TS files>10` 或单文件 `Parser>10ms` 才升 P1；`P5-03` 需 `PAIRS>40` 或 `check>1s` 才升 P1；`P5-04/P5-07` 需 `py-spy` 热点再升

## 处置（与 M1 tasks 对齐）

1. **转 tasks**：P5-01（MCP 双取）
2. **有意留（设阈值）**：P5-02 / P5-03 / P5-04 / P5-05 / P5-06 / P5-07 — 见 overview §5.1
3. **已验证通过**：P5-08 — 回归基线，无需动作

## When to revisit

- 首个 `*.ts` 域落仓或 `extract_ts_interface` 基准 >10ms/文件时重开 P5-02
- `k3dge check` P50 >1s 或 `PAIRS` >40 时重开 P5-03 门控
- `py-spy`/`cProfile` 显示 `intersection`/`normalize`/`_asset` 进热点前 5 时重开 P5-04/P5-07
- MCP 下游开始依赖 `current_interface` 高频（>10 QPS）时重开 P5-01

## 自检

- `k3dge check --force-full --with-tests` 本仓预检：`70 passed / 1 skipped / 44 subtests`（`pytest 5.5s`），`k3dge check --force-full` PASS，`k3dge sync` 幂等，未改公开签名无需重算
- 本报告 9 列齐全；悬空发现已落到 task 文件或有意留理由，符合 `docs/protocols/audit_default.md` 唯一规程；未重提 `F-14/F-15/R3-1/R3-4` 主结论，仅增 P5-03 同类候选
