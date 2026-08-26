# TC-SYNC-02 仍把 README 布局算在 sync 上

- **Status**: done
- **Milestone**: M1
- **Priority**: P1
- **Date**: 2026-08-25

## 已确认意图
`sync_all` 不再刷 README；布局由 `scripts/generate-docs.sh` 调 `render_readme_layout`。矩阵仍写 README marker 归 sync。

## 方案
TC-SYNC-02 改为 `sync_all` 生成 `docs/reference/{api.md,domains.md}` 且幂等。README 布局不作为 sync 域验收。P2-PUR-03（spec 仍写 architecture.md）同文件改成 `domains.md`。

## 入口
- `docs/specs/sync/spec.md`

## 来源
[docs/reviews/2026-08-25-pass4-consistency-alignment.md](../reviews/2026-08-25-pass4-consistency-alignment.md) P4-03；Pass 2 P2-PUR-03 并入
