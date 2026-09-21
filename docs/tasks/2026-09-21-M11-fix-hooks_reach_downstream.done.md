---
status: done
milestone: M11
priority: P1
date: 2026-09-21
---

# 到达环：hooks 与治理件随 init 下发（D1/D2）+ 便携性机检

- **可检索摘要**: `k3dge init` 的下游仓**拿不到** `scripts/pre-commit` / `scripts/commit-msg`（不在资产里），而 `.pre-commit-config.yaml` 的 `entry: scripts/pre-commit` 与下发的 `AGENTS.md` 都指向它们 ⇒ 按文档激活 hooks 后 git **静默跳过**（实测 `git commit` rc=0，doc-gate/schema/引用/排查闸全不生效）；同时 `docs/{specs,guides,protocols,architecture,generated}` 两份治理件缺失 ⇒ 即便钩子在，第一次提交 spec 也红（门禁与资产互斥）。修法＝把三层闸实现迁进 engine（可单测）、hooks 做成**薄壳资产**、治理件补齐并接线，再加"到达"机检。

## 复现（实测）

```
mkdir /tmp/p && cd /tmp/p && git init -q && k3dge init . && git config core.hooksPath scripts
git add -A && git commit -m "docs: 第一次提交"      # rc=0：hook 不存在 ⇒ 一句闸都没跑
ls scripts/                                        # gate.*/init.*/generate-docs.* —— 没有 pre-commit/commit-msg
```

## 方案

1. 三层闸实现从 `scripts/pre-commit` 迁入 **`engine/doc_gate.py`**（doc-gate / schema gate / screen gate；一致性闸仍由薄壳调 `scripts/gate.py`，本模块只出 `relevant_for_check()` 判据）。
2. `scripts/pre-commit` 变**薄壳**（定位 k3dge：自举 `src/` 或仓内 `.venv`（re-exec）或已安装包）→ `doc_gate.main()`；`scripts/commit-msg` 原样可移植。两者进资产 + `PAIRS` 字节锁 + scaffold 写出（可执行）。
3. 补 5 个类型的 `README.md`/`AUTHORING.md`（进资产 + `PAIRS`），scaffold 接线；下发文档统一过 `_qualify_adr_refs`（`architecture.md.template` 一并重写为骨架，去掉本仓专属域表）。
4. 新增 `INIT_DELIVERED_DOCS`（排查面豁免）：init 产物不是本仓的"新建决策"，否则**下游第一次提交必被 `DOC_NEW_UNSCREENED` 拦**（实测齐报 4 件）。
5. `check_dangling_adr` / `check_adr_ref_retired` 忽略**跨仓自限定引用**（`k3dge ADR-NNNN`）：否则 k3dge 自己下发的文档永远过不了自己的 hook。
6. `ARCH_STATE_DOC_DRIFT` 改「要么不写、要么写全」：骨架文档不被迫抄 k3dge 的状态表，半张表才红。
7. `protocols/quality_default.md`：资产有、本仓有，但既不在 `PAIRS` 也没下发 ⇒ 补 pair + 下发。
8. 新测试 `tests/unit/templates/test_hooks_reach_downstream.py`：init → hooks 可执行 → 治理件齐 → hook 真跑（PASS）→ 缺 AUTHORING 必红。

## 边界与拆分

- 事实归属：闸的逻辑归 engine（可单测）；hook 只做定位与进程编排；下发件归 templates 资产（`PAIRS` 锁本仓副本，`.template` 为下游专用）。
- 不动的：一致性闸仍在 `scripts/gate.py`（薄壳调用），审计线/封版路径的 `--no-verify`。
- 有意留：`k3dge ADR-XXXX` 自限定引用不再被引用闸校验（下游需要过闸；记账）；`INIT_DELIVERED_DOCS` 是手维护清单。

## 结案

- 落地：`engine/doc_gate.py`（新，原 hook 三层）、`scripts/pre-commit`（薄壳，含 venv re-exec）、`scripts/commit-msg`、资产 `pre-commit`/`commit-msg`/`{specs,guides,protocols,architecture,generated}/{README,AUTHORING}.md`、`pair`s 追加 13 对（含 `protocols/quality_default.md`）、`scaffold.py`（hooks + 治理件 + 统一下发 `_qualify_adr_refs`）、`engine/pure_refs.py`（`INIT_DELIVERED_DOCS` 豁免 + 自限定引用不解析）、`engine/evaluator.py`（状态集闸改「要么不写要么写全」）、`templates/assets/architecture.md.template`（重写为骨架）。
- 测试：`tests/unit/templates/test_hooks_reach_downstream.py`（5 例）新增；`tests/unit/scripts/test_precommit.py` 改从 `engine.doc_gate` 导入；templates spec 加 TC-TPL-06/07/08。
- 实测：修后在临时仓（PATH 上放 k3dge shim + PYTHONPATH 指向源码）——`git commit` 时 hook 真跑（`[k3dge doc-gate] PASS: 25 managed doc(s)` + schema + screen + check）；删 `docs/specs/AUTHORING.md` 后同样提交被拦（rc=1，消息点名 AUTHORING.md）。
- 验证：`k3dge check --with-tests` 绿（四域）；`pytest -q` 724 passed, 2 skipped, 113 subtests。
