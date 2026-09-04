---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-08-25
Deciders: Core Maintainer
Note: -
---

# ADR-0015: 下游 init 必须能被门禁咬住，协议包不得带本仓特化

## 1. 上下文 (Context)
自举生产级（ADR-0007）已立：本仓 `k3dge check` 能拦住契约漂移。下游工程生产级是另一条线：空仓 `k3dge-init` 之后，门禁必须保护**这个工程的代码**，Agent 协议不能指到不存在的 k3dge ADR / 本仓审计索引。

实证：k3dit init 后 `domains: {}`，`k3dge check` 假绿；`AGENTS.md` 点名 `docs/adr/` 尤其 0001 与 `docs/guides/mcp-bridge.md`，二者在下游都不存在；`reviews-readme` 曾与本仓审计目录字节锁，新 init 会带毒。

## 2. 决策 (Decision)

1. **`NO_DOMAINS`**：`manifest.domains` 为空则 `evaluate` 失败。空壳不得声称门禁可用。
2. **第一条域**：scaffold 用目录名（或 `--name`）登记一域：`src/<name>/`、`docs/specs/<name>/spec.md`、`tests/unit/<name>/`。已有非空 domains 不改（自举仓安全）。已有 **空** domains 的 manifest 会被升级（给 k3dit 这类旧 init 一条出路）。
3. **init 后 `k3dge sync`**：补第一条域的 Contract Hash，避免立刻 `CONTRACT_HASH_MISSING`。
4. **协议包与本仓特化拆开**（同 G-04 architecture 模式）：
   - `reviews-readme.md` **进 PAIRS**（与模板字节锁，改门面须双写模板与本仓，同 `tasks/README.md`）；`reviews/LEFTOVERS.md` **不进 PAIRS**（实例特有，空表）。本仓 README 是类型门面、LEFTOVERS 是本仓有意留。
   - scaffold 写出 `docs/guides/mcp-bridge.md`、`docs/reviews/README.md`、`docs/reviews/LEFTOVERS.md`、`docs/adr/README.md`、`.gitignore`。
   - `AGENTS.md` 仍与模板字节锁（不衰退），但正文改为读**本仓** overview/adr；harness 自身 ADR 留在 k3dge 检出。

## 3. 产生后果 (Consequences)

- **正**：新 init 的仓 `check --force-full` 有一域可验；Agent 能读到 mcp-bridge。
- **负**：旧空壳仓下次跑 scaffold/init 会被写入第一域；不想要则先自己登记 domains。
- **未做（刻意）**：给 k3dit 写审计透镜（那是 k3dit 产品）。MCP `sync`/`version`/`task` 与 commit-msg 钩已补。
