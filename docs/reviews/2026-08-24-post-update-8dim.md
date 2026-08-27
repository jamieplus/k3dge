# 审计：项目更新后 8 维 + Vibe 五轮（version / 双 0016）

- **Date**: 2026-08-24
- **基线**：`61 passed, 1 skipped`；`k3dge check --with-tests` PASS（本轮增量域为 templates）；`pyproject.toml` / manifest / `__init__.py` 均为 `0.1.0`
- **审计人**：Agent（Grok）按 `docs/protocols/audit_default.md`。k3dit `docs/guides/protocol.md` 不存在。
- **范围**：更新后全仓；透镜叠 8 维。不重开 §5.1：A-11 / S-13 / F-14 / F-15 / R3-1 / R3-4。不重开已修的 A-01..A-12、S-01..S-12。
- **结论**：有新发现，集中在后加的版本子系统和撞号 ADR。无 eval/密钥/SQL/XSS。
- **回记（同日）**：U-01..U-07 已在代码中核过（见下表）。脚手架门控 G-01..G-04 **未**随本轮关闭。

## 发现

| ID | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U-01 | 中 | P1 | 规范 | 两份 ADR 同号 `0016` | `docs/adr/0016-*.md`；overview §5 | 已修 | 版本 ADR 改号 **0017**；overview 有独立一行 | 仅一份 `0016-living-doc-relocation.md`；`0017-version-and-changelog.md` |
| U-02 | 高 | P1 | 缺陷 | `validate_versions` 被 `except pass` 吞掉；缺字段不算漂移 | `evaluator.py`；`version.py` | 已修 | 异常记 `VERSION_MISMATCH`；`mf_v != py_v` 含 None | `test_validate_missing_manifest_field_is_drift` |
| U-03 | 中 | P1 | 规范 | version 零测试、矩阵无 TC | `tests/`；engine/cli spec §4 | 已修 | `test_version.py` + TC-ENG-06 / TC-CLI-05 | `11` 条 version 测；全套 `70 passed` |
| U-04 | 中 | P1 | 规范 | MCP seal 不 bump | `cli/mcp.py` | 已修 | seal 成功后 `bump_version`；失败带 `version_bump_failed` | mcp.py 190–218 |
| U-05 | 中 | P1 | 缺陷 | bump 非原子；seal 后 bump 失败仍 0 | `version.py` `bump_version` | 已修 | 先算全文再写、失败回滚；ADR 0017：归档不回滚、禁止静默 | `test_bump_is_atomic_on_failure` |
| U-06 | 中 | P2 | 设计 | `_init_path` 写死 `src/k3dge` | `version.py` | 已修 | 走 `manifest.package_root`，`src`+name 回退 | `test_init_path_uses_manifest` |
| U-07 | 低 | P2 | 规范 | MCP 审计 prompt 只指向缺失的 k3dit protocol | `cli/mcp.py`；mcp-bridge.md | 已修 | 与 AGENTS.md §9 同一回退句 | prompt 含 memo 路径 |

## 各轮摘要

- **Pass 1**：无注入/密钥/eval。新风险是版本写盘半成功与 seal 后 bump 失败仍 0。git timeout 不重开 A-11。
- **Pass 2**：engine 收 version 副作用与 milestone 同类，未拆第五域。双 0016 破坏 ADR 编号事实源。
- **Pass 3**：version 已进 engine spec 接口块；判定在 engine、CLI 只路由，分层尚可。`except pass` 把闸做成摆设。
- **Pass 4**：VERSION 无 TC；MCP/CLI seal 行为不一致。`k3dge check` 本轮只报到 templates（增量），不证明 version 闸在跑。
- **Pass 5**：version 模块体积小，无热循环问题。不重开 F-14/F-15。

## N/A

Web/SQL/JWT/XSS/前端打包：本仓无对应面，不编造。
