---
Status: Accepted
Supersedes: -
Amended-by: -
Landed-by: docs/protocols/audit_default.md
Date: 2026-08-27
Deciders: Core Maintainer
Note: 修订痕迹见 git 历史。
---

# ADR-0017: Audit Report Schema v2 (12 columns)

- **Supersedes**: 9-column report contract.
  - Implicit in `k3dit` `audit-method.md` + `k3dge` `audit_default.md`.

## 1. 上下文 (Context)

The report schema needed stronger static structure.

- `pipeline.toml` moved from `[peers.k3dit.actions.audit]` to `[peers.k3dit.actions.verify]`.
- The audit flow thereby gained a second lifecycle stage: **re-verify (复审)**.
- The original 9 columns `ID|严重度|优先级|类型|问题描述|位置|状态|处置|验证` could not record:
  - (a) when a finding was raised;
  - (b) the re-verify conclusion and who closed it.
- Agents were observed fabricating stage references (`k3dit.actions.lint`).
- They were also observed leaving dangling `manual` protocol paths.

## 2. 决策 (Decision)

Expand the report header from 9 to **12 columns**:

`ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收`

- **`日期`**: `YYYY-MM-DD`, finding/initial-audit date, non-empty.
- **`复审`**: `待复审 | 通过 | 驳回`; `待复审` at audit time, resolved by the verifier.
- **`验收`**: required when `复审 ∈ {通过, 驳回}`.
  - Format: `验收人 YYYY-MM-DD [#reason]`.
  - Examples: `k3dit 2026-08-27` or `manual 2026-08-27 #cli unavailable`.

Enforce the contract in `k3dit`'s `check-report` (`src/k3dit/report.py`):

- `REQUIRED_HEADERS` now includes the 3 new columns.
- `_check_row` validates the `复审` enum and the `日期` format.
- It also requires `验收` when `复审` is terminal.
- `k3dit`'s own historical report `docs/reviews/2026-08-26-k3dit-5pass.md` was migrated to v2.

`k3dge check` does not parse report contents; the schema is enforced at the `k3dit` boundary.

k3dge gates existence; k3dit gates lens + format, consistent with ADR-0001.

## 3. 产生后果 (Consequences)

- New reports must carry `日期`/`复审`/`验收`; `k3dit check-report` fails otherwise.
- Historical 9-column reports are **archival under v1**; they are not re-validated.
- Only newly produced reports follow v2.
  - Migration of existing `docs/reviews/*.md` is optional and left to the owning milestone.
- The three "fact-source pillars" of k3dge's gate matrix are now:
  - `manifest.json` (`MANIFEST_INVALID`)
  - `spec.md` (`CONTRACT_DRIFT`)
  - `pipeline.toml` (`PIPELINE_*`)
- The report schema lives in the `k3dit` pillar as a format contract.

## References

- `k3dge` `docs/protocols/audit_default.md`, `docs/protocols/verify_default.md`, `rules/07-audit.md`
- `k3dit` `docs/guides/audit-method.md`, `src/k3dit/report.py`
