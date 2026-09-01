# 审计：8 维 + Vibe 特检五轮（相对 08-24 透镜的增量）

- **Date**: 2026-08-24
- **基线**：36 tests / 26 subtests / `k3dge check --with-tests PASS` / 4 域契约已同步
- **审计人**：Agent（Grok）按用户给出的 8 维 + Vibe 特检五轮清单（严于 `docs/memo/2026-08-23-5pass-audit-protocol.md`）
- **范围**：同 08-24 全仓；**只记录该标准新照出、且未在** [`2026-08-24-5pass-audit.md`](2026-08-24-5pass-audit.md) **立案的发现**
- **方法**：先读 SUMMARY 与 08-24 报告；Pass 1 安全/污点/回滚/None；Pass 2 DAG/重复造轮子；Pass 3 错误码契约；Pass 4 状态机绕过/幻觉 API/无测试即缺陷；Pass 5 循环 IO/大文件。不重提 A-01..A-12、F-14/F-15、R3-1/R3-4
- **结论**：**有新发现。** 本标准比 08-24 多出安全污点、事务回滚完整性、状态机非法跃迁/流程绕过、配置元数据、无测试即缺陷。本轮 12 项新发现（1 高 / 7 中 / 4 低）。**修复回记（同日）**：S-01/S-02/S-03/S-04/S-05/S-06/S-11 已修；S-07 部分（补了 manifest + L2 崩栈/模板/align/回滚测，diff/CLI 成功路径仍缺）；S-08/S-09/S-10 仍开；S-12 并入 0001；S-13 有意留。

## 本标准相对 08-24 的增量（为何会多出问题）

| 透镜 | 08-24 覆盖 | 本标准多出来、因此新中招的 |
| --- | --- | --- |
| Pass 1 | 边界、正则截断、pytest timeout、seal 子串 | 权限与污点、注入、回滚是否真回滚、None 防御、配置类型、ReDoS、eval/pickle/密钥 |
| Pass 2 | DAG 箭头、ADR 措辞 | 重复造轮子、分层/错误码规范割裂 |
| Pass 3 | 装饰器/哈希正交 | 入参出参错误码完整性、过/欠设计、传输层与核心解耦 |
| Pass 4 | 指纹、双轨脚本、矩阵 TC 过称 | 状态机非法跃迁、流程绕过/重放、幻觉 API、假实现、**无测试即缺陷**、跨平台对等 |
| Pass 5 | 死代码、双重 AST、O(N²) | 循环 IO、大文件全量读、N+1（本仓无 DB，N/A） |

08-24 已立案、本标准下**仍然成立但不重复开单**：A-02 `force_full`、A-03 align 复制 L2、A-04 align/回滚无测、A-06 抽取吞 SyntaxError、A-07 TS 整段入哈希、A-08 DAG/ADR 措辞、A-09 MCP 无 TC、A-10 死参、A-11 git 无 timeout（有意留）、A-12 `cached_property`。

## 发现

| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S-01 | 2026-08-24 | 中 | P1 | 缺陷 | `seal` 回滚内层 `except Exception: pass`：二次 `move` 失败仍返回「rolled back」，文件可留在 `archive/` 而顶层任务已消失 | `src/k3dge/engine/milestone.py:250–256` | 已修 | 回滚失败收集错误返回 `rollback incomplete`；`test_seal_rollback_reports_incomplete` | `47 passed` | 待复审 |  |
| S-02 | 2026-08-24 | 高 | P1 | 缺陷 | L2 失败/超时组装 Violation 时 `workspace / manifest.spec_path(d)`，域有 `tests` 无 `spec` 则为 `None`，**异常处理器自身 TypeError 崩栈**，门禁变 traceback | `src/k3dge/engine/evaluator.py:126,146,152`；`milestone.py` 同源复制 | 已修 | `_spec_violation_path` 允许 None；`test_missing_spec_with_failing_tests_does_not_crash` | 原复现 TypeError → 现 `SPEC_NOT_FOUND`/`TEST_FAILURE` | 待复审 |  |
| S-03 | 2026-08-24 | 中 | P1 | 缺陷 | `milestone_id` 未消毒即拼进路径：`docs/tasks/archive/{id}/` 与 `docs/reviews/{date}-{id}-align.md`。id 含 `../` 可写到工作区外 | `milestone.py:158,241` | 已修 | `_validate_milestone_id` + archive `relative_to`；`test_rejects_path_like_milestone_id` | `../evil` / `foo/bar` 拒绝 | 待复审 |  |
| S-04 | 2026-08-24 | 中 | P1 | 缺陷 | Manifest 只拒绝 `src/spec/tests` 绝对路径，不拒绝 `../`；`check`/`MCP` 会按相对路径读文件或把该路径丢给 pytest | `src/k3dge/engine/manifest.py:29–32` | 已修 | `_require_relative_path` 拒绝 `..` 与非 str；`test_rejects_parent_relative_paths` | `../secret.md` → `ManifestError` | 待复审 |  |
| S-05 | 2026-08-24 | 中 | P1 | 规范 | 时序可绕过：`align` 自动写出 seal 闸机 1 所需的 `{date}-{id}-align.md`（正文已写「准予封板压缩」且勾选未填）；seal **不验证** align 刚跑过回归、也不验证评审是否填完，只要 SUMMARY 含 token 即可封板 | `milestone.py:156–186,211–221` | 已修 | align 写入 `<!-- k3dge:align-stub -->`；seal 拒绝仍含标记的文件；`test_align_stub_blocks_seal` | stub 在则 SEAL REJECTED | 待复审 |  |
| S-06 | 低 | P2 | 规范 | 任务 Status 不校验枚举 `idea\|deferred\|in-progress\|done`，缺字段变 `unknown`；不拦截非法跃迁（`idea` 直接 `done`）。仅终态 `!= done` 拦 align/seal | `milestone.py:69–82,205–207` | 已修 | align/seal 拒绝非白名单 Status；`test_align_rejects_unknown_status` | `shipped` → Invalid Status |
| S-07 | 中 | P1 | 规范 | 无测试即缺陷：`diff.py`（quotepath/重命名/`K3DGE_BASE_SHA`/shallow）、`manifest.py` 单元、`cmd_sync`/`cmd_milestone`/`cmd_check` 成功路径、`_ts.py` 均无单测；`test_parser_has_check_and_sync_only` 不断言 `milestone` 存在。A-04/A-09 已覆盖的 align/MCP 不重复 | `tests/unit/**` vs `src/k3dge/**` | 待修 | 转 [tasks/2026-08-24-exception-path-tests.md](../tasks/2026-08-24-exception-path-tests.md) | grep `def test_` 对照模块 |
| S-08 | 低 | P2 | 规范 | 跨平台不对等：`generate-docs.sh` 无 `.ps1`；gate/init 已三轨，收尾脚本只 POSIX | `scripts/generate-docs.sh`；`templates/assets/` | 待修 | 同上任务 | `test_template_sync.PAIRS` 无 generate-docs.ps1 |
| S-09 | 低 | P2 | 设计 | MCP 错误契约三形态：JSON `{"error"}` / Markdown `# Error:` / `{"ok": false}`，与 CLI `--json` 的 `{passed,violations}` 不统一 | `src/k3dge/cli/mcp.py:67–88,128,203`；`cli/main.py:32–46` | 待修 | 转 [tasks/2026-08-24-mcp-error-contract.md](../tasks/2026-08-24-mcp-error-contract.md) | 源码对照 |
| S-10 | 低 | P3 | 冗余 | `_find_workspace` 在 `cli.main` 与 `cli.mcp` 各写一份，且 MCP 显式 `workspace_path` **跳过** `.agent`/`.git` 探测，任意目录可被当作 workspace | `cli/main.py:25–29`；`cli/mcp.py:49–59` | 待修 | 同上任务 | 显式路径不要求存在 `.agent` |
| S-11 | 中 | P1 | 缺陷 | 配置元数据校验不足：`ignore` 若为字符串则按字符迭代（`"*"` 匹配全部文件）；`src/spec/tests` 非 str 时 `Path(val)` TypeError 不进 `ManifestError`；`test_command_template.format` 缺 `{refs}` 抛 `KeyError` 冒泡 | `manifest.py:22–32`；`evaluator.py:112–115` | 已修 | ignore 必须 list[str]；模板 KeyError → `MANIFEST_INVALID` | `test_ignore_must_be_list_of_strings` / `test_bad_test_command_template_is_violation` |
| S-12 | 低 | P2 | 规范 | 幻觉文档：`scripts/init.sh` 注释写默认「本仓 `.[dev]` 可编辑安装」，实现是 `pip install k3dge`（PyPI）。与 deferred `0001` 同源 | `scripts/init.sh:6–7,32–33` | 待修 | **并入** [tasks/0001-downstream-bootstrap-install-source.md](../tasks/0001-downstream-bootstrap-install-source.md)，不新开单 | 注释 vs else 分支对照 |
| S-13 | 低 | P3 | 安全 | MCP `workspace_path` 可指向任意目录并 `seal`/跑 pytest。本地 stdio 下调用方即本机用户 | `cli/mcp.py:49–53,191` | 有意留 | 本机 stdio 桥：能调 MCP 的人已是 OS 用户，再拦无增量。**失效条件**：MCP 改为网络可达时必须重开。常驻否决见 `docs/architecture/overview.md` §5.1 | 本报告为证 |

### 本标准已扫、无发现（不编造）

- 无 `eval`/`exec`/`pickle`/`yaml.load`/`shell=True`/`os.system`
- 无硬编码 AK/SK、JWT、XSS、SQL 拼接、SSRF、网络客户端
- 正则无嵌套量词 ReDoS（`[^>]*` 等为线性）
- 默认 L2 命令为 argv 列表，非 shell（`test_command_template` 由项目所有者配置，视为信任）
- 无 DB / 无前端，N+1、lodash/moment N/A
- 大文件全量读内存：spec/源码按设计读入 AST，规模约束在域源码，有意不立项（同 F-14 量级）

## 结论

- **对用户问题的直接回答**：按这套 8 维 + Vibe 标准审，**有新发现**，不是 08-24 报告的重复。最值钱的增量是 S-02（`--with-tests` 可崩栈）、S-03/S-04（路径逃逸）、S-05（封板验收可绕过）、S-01（回滚撒谎）、S-07（无测试即缺陷把 `diff`/`manifest`/CLI 成功路径照出来）。
- **工程质量判定（本标准）**：日常无测试的 `k3dge check` 仍可通过；加上本标准的安全与时序透镜后，**不能**再说「生产就绪」。08-24 的 A-02..A-09 加上本轮 S-01..S-11 都还开着。
- **When to revisit**：网络暴露 MCP 时推翻 S-13；`milestone seal` 前至少关掉 S-01/S-03/S-05。

## 验证

- S-02：临时仓「有 tests、无 spec」+ 失败用例 + `evaluate(run_tests=True)` → `TypeError`
- S-03：`Path('/tmp/k3dge-ws/docs/tasks/archive/../../../../tmp/k3dge-pwn').resolve()` → `/private/tmp/tmp/k3dge-pwn`
- S-11：`Manifest({"domains":{}, "ignore":"*.pyc"}).is_ignored("foo") is True`
- `k3dge check --with-tests` 在本仓（四域均有 spec）仍 PASS，**不掩盖** S-02（需缺 spec 才触发）
