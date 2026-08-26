# 版本闸可静默失效，且 bump/seal 无测试、跨入口不一致

- **Status**: done
- **Milestone**: M0
- **Priority**: P1
- **Date**: 2026-08-24

## 已确认意图
审计 U-02..U-06。`evaluate` 吞掉 `validate_versions` 异常；缺 version 字段不当漂移；`version.py` 与 `cmd_version` 零测试；CLI seal 自动 bump、MCP seal 不 bump；`bump_version` 非原子；init 路径写死 `src/k3dge`。

## 方案
1. 去掉 `except Exception: pass`；校验失败记 `VERSION_MISMATCH` 或包装后的违规。
2. `py_v` 有值而 manifest/init 缺字段或 JSON 坏了，也算漂移（与 ADR「三者同值」一致）。
3. `bump_version` 先算全文再写，或失败回滚已写文件。
4. seal 自动 bump：CLI 与 MCP 同一条（都 bump 或都显式不 bump）；bump 失败是否阻断 seal 要在 ADR 写死，禁止「归档成功、版本一半」。
5. `_init_path` 用 `manifest.package_root`。
6. 补 `tests/unit/engine/test_version.py` 与 cli 路由测；engine/cli spec 矩阵加 TC。

公开签名若变，同任务 `k3dge sync`。

## 入口
- `src/k3dge/engine/version.py`
- `src/k3dge/engine/evaluator.py`
- `src/k3dge/cli/main.py` `cmd_milestone` / `cmd_version`
- `src/k3dge/cli/mcp.py` `k3dge_milestone_control`

## 来源
[docs/reviews/2026-08-24-post-update-8dim.md](../reviews/2026-08-24-post-update-8dim.md) U-02..U-06
