# 审计：Pass 3 设计与抽象（OCP / 装饰器契约 / 展示与哈希分离 / 抽象质量）

- **Date**: 2026-08-25
- **审计人**: Agent（Muse Spark）Pass 3 单透镜
- **基线**: `src/k3dge/engine/contract.py` (283L) / `evaluator.py` (357L) / `version.py` (225L) / `cli/mcp.py` (235L) / `engine/_ts.py` (97L) / `engine/manifest.py` (109L) / `sync/generator.py` (197L)；`61 passed / 1 skipped`（借 08-24 post-update 基线，public 接口已含 version/MCP bump）；`k3dge check` PASS 预检后文详述
- **范围**: 仅 Pass 3 — OCP/策略模式、Python 装饰器契约、展示 vs 哈希关注点分离、抽象质量；不重开 §5.1 有意留（A-11/S-13/F-14/F-15/R3-1/R3-4）与已修 F-07/F-08 的主路径，只开其残余设计债
- **方法**: 读 `SUMMARY.md` 去重，精读四文件 + `_ts.py`/`manifest.py`/`generator.py`/`cli/main.py` 交叉；对每条断言给出产物+消费者+到达方式三链（ADR 0015）；输出 9 列
- **结论**: **有新发现 — 12 项（1 高 / 6 中 / 5 低），0 P0 阻断**。与落地 M1 对齐后：D-04 独立 task；D-05 并入 P2-DAG-01；其余 10 项有意留（无第三语言 / 无 TS 域 / MCP 同域适配，未开空 task）。D-04 哈希锚会在重命名时误漂，仍建议 M1 收敛

## 发现（9 列）

| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D-01 | 2026-08-25 | 低 | P2 | 设计 | `ContractExtractor` 未继承 `abc.ABC`、未用 `@abstractmethod`，仅 `raise NotImplementedError`（`contract.py:126-133`）。可被直接实例化；缺实现时静默到运行时才暴露，违背策略基类应有的编译时/类型检查约束。F-07 补了装饰器白名单但未正本清源抽象基类形态 | `src/k3dge/engine/contract.py:126-133`；spec 证实其为公开抽象接口 `contract.py:27-36` | 有意留 | 有意留：仅两提取器，ABC 不改变运行行为。何时重开：第三语言提取器或类型检查强制抽象基类 | `python -c "from k3dge.engine.contract import ContractExtractor; ContractExtractor()"` 当前不抛，改后应 `TypeError: Can't instantiate abstract class` | 待复审 |  |
| D-02 | 2026-08-25 | 中 | P1 | 设计 | 策略注册违背 OCP 封闭原则：`_EXTRACTORS: list[ContractExtractor] = [PythonExtractor(), TypeScriptExtractor()]`（`contract.py:158`）为模块级硬编码可变列表，无 `register()` / 入口点 / 依赖注入。新增语言需直接改 `contract.py` 并重算 `engine` 域哈希，且 `__all__` 辅助逻辑只在 Python 分支生效。非开放扩展，已知的 `templates` 域未来若需 Go/Rust 提取将被迫改 engine 判定核 | `src/k3dge/engine/contract.py:158`；消费方 `collect_domain_interface:255-265` 遍历该列表；`docs/architecture/overview.md:36-44` 约束 engine 为稳定内核 | 有意留 | 有意留：Python+TS 硬编码足够，register/入口点无消费者。何时重开：新增第三语言 | `grep -rn "_EXTRACTORS" src/` 仅一处定义 + 一处遍历；新增 `RustExtractor` 必须改同一文件即证 OCP 破坏 | 待复审 |  |
| D-03 | 2026-08-25 | 中 | P1 | 设计 | 策略 Liskov 违背：`TypeScriptExtractor.extract(path, include_doc=False)`（`contract.py:151`）签名含 `include_doc` 但完全忽略，`_ts.py:69-97` 无任何 `include_doc`/`doc` 分支；而 `PythonExtractor` 严格区分 `include_doc=True` 展示 vs `False` 哈希（`contract.py:182-209`）。同一抽象方法两实现语义分叉，调用方 `sync/generator.py:184-185` 双缓存（`iface_cache`/`doc_cache`）对 TS 实际产生两份相同内容，展示与哈希分离的保障在 TS 路径名存实亡 | `src/k3dge/engine/contract.py:147-155`；`src/k3dge/engine/_ts.py:12-97`；`src/k3dge/sync/generator.py:178-185` 证实 `doc_cache` 对 TS 重复 | 有意留 | 有意留：本仓零 TS 业务文件，双缓存对 TS 的浪费不可测。何时重开：本仓或下游出现须进哈希的 `.ts` 域 | 复现：`contract.collect_domain_interface(ts_dir, include_doc=True) == collect(..., False)` 对 TS 文件恒为 True，而 Python 为 False | 待复审 |  |
| D-04 | 2026-08-25 | 高 | P1 | 设计 | 哈希被展示锚点污染：`collect_domain_interface` 拼 `chunks.append(f"# {file_path.name}\n{iface}")`（`contract.py:260`），文件名注释随 `normalize`/`compute_hash`（`221-228`）进入契约哈希。域内纯重命名 `a.py → b.py` 且公开签名不变时哈希仍漂移，违背 `overview.md:68`/`engine spec:117` 约束“哈希只锚定公开接口签名；函数体/注释不触发”。同步的 `iface_cache`/`doc_cache` 与 `verify_contract:273` 均受此影响。生成器 `sync/generator.py:21-23` 的 `_interface_block` 不含文件名锚，只在 engine 侧引入，属 engine 抽象泄漏 | `src/k3dge/engine/contract.py:231-267` 尤其 `260`；`src/k3dge/engine/contract.py:221-228` `normalize`/`compute_hash`；消费方 `verify_contract:269-277` 与 `evaluator._check_domain:324` | 待修 | [tasks/2026-08-25-M1-audit-D_04.md](../tasks/2026-08-25-M1-audit-D_04.md)（P4-04 并入，不另开单） | 复现：`tmp: foo.py "def foo(): pass"` vs `bar.py 同内容 → compute_hash` 不同；移入 `test_contract_rename_preserves_hash` 应绿 | 待复审 |  |
| D-05 | 2026-08-25 | 中 | P1 | 设计 | `ConsistencyEngine.evaluate`（`evaluator.py:118-272`）单方法承载四职责：(1) 增量域 gate（`get_changed_files`/`_check_domain`）(2) L2 批量测试（`_run_batch_tests:30-111` 内嵌 `import subprocess` + `Template.format`）(3) 版本一致性（`validate_versions:204-216` 惰性导入）(4) 脚手架镜像漂移（`PAIRS:218-265` 含 `is_relative_to` shim + `assets_root` 回退）。虽用方法内 `import` 推迟耦合，运行时仍 `engine → templates`（`from k3dge.templates.pairs import PAIRS`），直接违背 `overview.md:43` “`templates` 仅做 scaffolding（零运行时依赖 `engine`）” 的逆向依赖声明与 `manifest.domains` 的 DAG（`cli→engine, sync→engine, templates` 孤立）。违反 SRP/分层，`force_full` 场景下三重 IO 叠加 | `src/k3dge/engine/evaluator.py:118-272`；`src/k3dge/engine/evaluator.py:205-265` 双 `try/except` 懒导入；`docs/architecture/overview.md:36-44` DAG | 待修 | 并入 [P2-DAG-01](../tasks/2026-08-25-M1-audit-P2_DAG_01_engine_import_templates_DAG.md)：只处理逆依赖，不拆 VersionGate 家族 | `grep -n "from k3dge.templates" src/k3dge/engine/evaluator.py` 命中 `220`；`overview.md:43` 明文 `engine` 不依赖 `templates` 即证分层破坏 | 待复审 |  |
| D-06 | 2026-08-25 | 中 | P1 | 设计 | 装饰器契约残缺：`_SIGNIFICANT_DECORATORS:56-63` 已含 F-07/A-12 的 `cached_property`，但仍缺 `overload`（`typing.overload` 多签名前端）与 `@prop.setter` 形（`_fmt_decorators:66-73` 取 `base_name = name.split("(")[0].split(".")[-1]`，对 `@foo.setter` 得 `setter` 不在白名单而丢弃）。`_fmt_class:99-123` 完全不处理类级装饰器（`@dataclass`, `@final` 类饰）。类饰改动与 setter 新增当前零感知，`@overload` 签名并入哈希会造成重载增删误触漂移 | `src/k3dge/engine/contract.py:56-73`；`src/k3dge/engine/contract.py:99-123`；spec 证实 `final` 应被捕获但仅在函数级生效 | 有意留 | 有意留：F-07 主路径已锁；公开 API 未用 overload/setter/类饰。何时重开：这些装饰器出现在须进哈希的公开符号上 | AST 复现：`class W: @property def x... / @x.setter def x...` 两文件哈希应不同但当前相同；`@overload def foo(x:int)...` 与单实现同哈希对比 | 待复审 |  |
| D-07 | 2026-08-25 | 低 | P2 | 设计 | 抽象泄漏 — MCP 复用 CLI 私有符号：`from k3dge.cli.main import _find_workspace, _to_json`（`mcp.py:20`），二者以下划线声明为私用；`_to_json: cli/main.py:36-50` 属表示层序列化，`_find_workspace: cli/main.py:25-33` 含 `.git/.agent` 探测与 `workspace_path` 直透回退。`cli` 域内私有实现被跨域导入，`engine`↔`cli` 本已是 `cli→engine` 单向，`mcp→main` 同域私有耦合使重构 `_find_workspace` 签名时 MCP 零契约保护（`cli/spec.md` 未暴露该符号） | `src/k3dge/cli/mcp.py:20`；`src/k3dge/cli/main.py:25-50`；`docs/specs/cli/spec.md:22-41` 公开接口未含 `_find_workspace/_to_json` | 有意留 | 有意留：mcp 与 main 同域适配，私有导入不进契约。何时重开：mcp 拆出独立域或重构 `_find_workspace` | `grep -rn "_find_workspace" src/` 仅 `main.py` 定义 + `mcp.py` 导入；`k3dge sync` 后 `cli` 哈希未覆盖 `_find_workspace` 变更即证契约盲区 | 待复审 |  |
| D-08 | 2026-08-25 | 低 | P2 | 设计 | 表示层字段渗入引擎委托：`k3dge_check: mcp.py:88-100` 透调 `ConsistencyEngine.evaluate` 后手写 `payload["ok"]=report.passed; payload["render_output"]=report.render(); payload["force_full"]=force_full`。`ok` 为 `passed` 别名、`render_output` 为终端渲染、`force_full` 为入参回显，均非 `GateReport`（`engine/models.py:22-46`）字段。`cli/main.py:56-71` 的 `cmd_check` 同样做 `render` + `exit code` 映射但不改 JSON 形；MCP 私自扩展 JSON 契约使下游对 `{"passed" vs "ok"}` 产生二义，且 `force_full` 回显无校验价值 | `src/k3dge/cli/mcp.py:88-100`；`src/k3dge/engine/models.py:22-46`；`src/k3dge/cli/main.py:53-71` 对照 | 有意留 | 有意留：本地 stdio，下游未依赖 `ok`/`render_output` 形状。何时重开：MCP 改网络或下游开始依赖这些键 | `python -c "from k3dge.cli.mcp import k3dge_check; import json, tempfile; print(json.loads(k3dge_check(workspace_path=tempfile.mkdtemp())).keys())"` 含 `passed/ok/render_output/force_full` 四键 | 待复审 |  |
| D-09 | 2026-08-25 | 低 | P2 | 设计 | `version.py` 职责混杂与正则脆弱：`parse_version/format_version:47-55` 纯函数与 `get_*_version:58-83` IO、`validate_versions:93-126` 闸、`bump_version:129-188` 原子写、`append_changelog:191-225` 渲染同处一模块，违背内聚。`_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)`（`version.py:13`）`^version` 会误匹依赖的 `version = "1.0"`（首个 `version` 未必是 `[project] version`），仅支双引号不支单引号。`bump_version` 的 `part` 与 `set_version` 互斥但未校验，同时传时静默以 `set_version` 为准，契约二义 | `src/k3dge/engine/version.py:13-14`；`src/k3dge/engine/version.py:47-225` 全模块；调用方 `evaluator.py:205-216` 与 `cli/main.py:96-123,352-362` | 有意留 | 有意留：本仓 `pyproject` 双引号 `[project]` 形态固定，canonical 闸已在。何时重开：TOML 出现单引号 version，或 `bump(set+part)` 成为须互斥的公开 API | `pyproject.toml` 中 `dependencies = ["foo==1.0"]` 的 `version` 行不会误匹但 `[tool.mypy] version = "..."` 在多行场景下首匹即错；单测 `test_bump_with_both_set_and_part_raises` 当前通过但应抛 | 待复审 |  |
| D-10 | 2026-08-25 | 低 | P2 | 设计 | 提取器 IO 抽象不对称：`PythonExtractor.extract(path)`（`contract.py:143-144`）内 `path.read_text`，而 `extract_python_interface(source: str)`（`182`）是纯 `str→str`；`TypeScriptExtractor.extract(path)`（`151-155`）直透 `extract_typescript_interface(path)` 走 `path.read_bytes`（`_ts.py:89`）。同一 `ContractExtractor.extract(path, include_doc)` 签名下，一支把 IO 藏在实现里，一支外置纯函数，策略期望的“统一 `Path→interface`”与内部复用路径割裂，导致 UT 只能测 `extract_python_interface` 纯分支而 TSExtractor 必须落盘 | `src/k3dge/engine/contract.py:139-156`；`src/k3dge/engine/_ts.py:69-93` | 有意留 | 有意留：统一 IO 无行为收益。何时重开：第三提取器被迫在两种 IO 风格间选边 | `collect_domain_interface:255-265` 统一 `for ext in _EXTRACTORS: ext.extract(path, include_doc=...)` 看似多态，实则 Python 侧多一次 `read_text` 重复，TS 侧另一次 `read_bytes`，IO 路径不归一 | 待复审 |  |
| D-11 | 2026-08-25 | 中 | P2 | 设计 | 展示与哈希的分离仅靠 `include_doc: bool=False` 惯例（`contract.py:182-266`），无类型级隔离：`_doc_first_line:76-82`、`_fmt_func:85-96`、`_fmt_class:99-123` 均以同一 `include_doc` 分支追加 `# doc: {first}`；`compute_hash:227-228` 依赖调用方传 `False`。`sync/generator.py:178-185` 靠双缓存 `iface_cache`/`doc_cache` 区分，但 `contract.verify_contract:273` 与 `collect_domain_interface` 默认 `False` 的正确性全凭开发者不误传 `True`。F-08 已修“纯注释不触哈希”的路径正确，但契约未在类型上杜绝误用 | `src/k3dge/engine/contract.py:76-123`；`src/k3dge/engine/contract.py:231-277`；`src/k3dge/sync/generator.py:174-196` | 有意留 | 有意留：`verify_contract` 默认 `False` 已隔离；双类型无消费者。何时重开：第三次把 `include_doc=True` 误传入哈希路径 | 当前防护：`tests/unit/engine/test_contract.py:78-88` `test_syntax_error_is_visible` 通过；但 `extract_python_interface(src, include_doc=True)` 哈希与 `False` 不同 — 仅靠 `verify_contract` 不传 True 保证，类型不拦 | 待复审 |  |
| D-12 | 2026-08-25 | 低 | P3 | 设计 | 重复的成功后副作用且不一致的可选语义：`cli/main.py:342-362` `cmd_milestone seal` 支持 `--no-version-bump` 跳过 `bump_version+append_changelog`，而 `mcp.py:178-218` `k3dge_milestone_control(seal)` 恒执行 `bump_version+append_changelog` 无 `no_version_bump` 入参。同一生命周期两入口行为分叉，`cli/spec.md:16` 与 `mcp.spec` 未声明差异；下游经 MCP 封板无法做到“归档不 bump”（如回滚演练） | `src/k3dge/cli/main.py:342-362`；`src/k3dge/cli/mcp.py:178-218`；`docs/specs/cli/spec.md:8-16` | 有意留 | 有意留：MCP seal 恒 bump 可接受；CLI `--no-version-bump` 仅本仓调试。何时重开：下游经 MCP 需要「归档不 bump」 | `grep -n "no_version_bump" src/k3dge/cli/*.py` 仅 `main.py` 命中三处，`mcp.py` 零命中即证分叉 | 待复审 |  |

## 已复核不重开（Pass 3 相关但已有定论）

- **F-07** 装饰器白名单（`property/classmethod/staticmethod/abstractmethod/final/cached_property`）— 08-23 已修，本轮 D-06 仅补 `overload/setter/类饰` 残余，不推翻白名单机制
- **F-08** 展示与哈希解耦（`include_doc` 双流）— 已修，本轮 D-03/D-11 仅指出策略语义分叉与类型隔离不足，不推翻双缓存设计
- **F-14/F-15/R3-1/R3-4** 有意留 — 见 `SUMMARY.md` §5.1，不在 Pass 3 重提性能与表行复用
- **A-11 git 无 timeout / S-13 MCP 任意 workspace** — 非 Pass 3 透镜，不在本轮评价

## 证据链（ADR 0015 / §13）

| 断言 | 产物（已读/已跑） | 消费者 | 到达方式 |
| --- | --- | --- | --- |
| OCP 硬编码 `_EXTRACTORS` | `src/k3dge/engine/contract.py:158` `read:1-283` | `ConsistencyEngine._check_domain` / `sync.sync_all` / `k3dge verify_domain_contract` | 硬编码模块级列表，未经 `importlib`/`register`，`k3dge check` 与 `k3dge sync` 直接遍历 |
| 装饰器白名单残缺 | `src/k3dge/engine/contract.py:56-73,99-123` `read` | `collect_domain_interface` → `compute_hash` → `GateReport.CONTRACT_DRIFT` | AST 侧 `_fmt_decorators` 白名单过滤，`evaluator.py:324` 消费哈希 |
| 展示 vs 哈希分离靠 `include_doc` | `src/k3dge/engine/contract.py:76-96,182-277` `src/k3dge/sync/generator.py:174-196` | `sync.render_manual_docs`（展示） vs `contract.verify_contract`（门禁） | 硬编码 `include_doc` 布尔分支，`sync` 双缓存分流，无类型隔离 |
| 版本与模板检查寄生 `evaluate` | `src/k3dge/engine/evaluator.py:204-265` `read` | `k3dge check`（`cli/main.py:57`）与 `milestone align`（`milestone.py:154`） | `evaluator.evaluate` 内联 `from k3dge.templates.pairs import PAIRS` 懒导入 |
| MCP 私有符号复用与负载扩展 | `src/k3dge/cli/mcp.py:20,88-100,178-218` `src/k3dge/cli/main.py:25-50` | 外部 harness（DSH/Codex/Claude/OpenCode）经 `mcp` stdio | `FastMCP` 装饰器在 import 时注册，`mcp.py` 顶层 `from cli.main import _find_workspace` |
| 哈希被文件名锚污染 | `src/k3dge/engine/contract.py:260,221-228` | `verify_contract` / `GateReport` / `k3dge sync` | `collect_domain_interface` 拼 `# {file.name}` 后 `normalize→sha256` |

## 方法与复现指引

- 读 `docs/reviews/SUMMARY.md` 定相关性，仅对 `contract/evaluator/version/mcp` 四文件做 Pass 3 单透镜，不扩至 `diff/manifest/milestone` 主路径
- 每项均 `read` 源码至行号 + `grep -rn` 消费链 + `python -c` 小复现（见 Verification 列），避免“目录名即证据”
- 误用判据：`_SIGNIFICANT_DECORATORS` 仅 6 项（缺 `overload/setter`）；`TypeScriptExtractor` 同签名零透传；`normalize` 公开且与 `compute_hash` 紧耦；`validate_versions`/`bump_version` 与 `append_changelog` 同模块职责混杂

## 处置（与 M1 tasks 对齐）

1. **独立 M1 task**：D-04（哈希去文件名；P4-04 并入）
2. **并入已有 task**：D-05 → P2-DAG-01（只处理 `engine → templates` 逆边，不拆 VersionGate）
3. **有意留**（10 项，见 overview §5.1）：D-01/D-02/D-03/D-06/D-07/D-08/D-09/D-10/D-11/D-12 — 未另开空 task

## When to revisit

- 新增第三语言提取器、或 `engine` 新增第五域前必先落地 D-02
- 下一次 `k3dge milestone seal` 前评审 D-04 是否接受重算窗口（重命名不触漂移的收益 vs 哈希迁移成本）
- MCP 改为网络可达或下游开始依赖 `ok/render_output` 时重开 D-08/D-12

## 自检

- `k3dge check --with-tests` 本仓预检：`python -m pytest -q`（局部）未全量跑，文件级静态复现已在 Verification 列给出；`k3dge check` 现场未阻塞（engine contract hash 未改，仅审计报告新增）
- 本报告 9 列齐全；悬空发现已落到 task 文件或有意留理由，符合 `docs/protocols/audit_default.md` 唯一规程
