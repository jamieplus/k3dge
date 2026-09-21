---
status: done
milestone: M11
priority: P1
date: 2026-09-20
---

# closure_note 写在 seal_record 之后：清单不进封版提交、版本多记一拍、证据 glob 空

- **可检索摘要**: `[checks.seal].actions` 序是 archive → version_bump → seal_record → closure_note → prune。封版提交先 `git add -A`，收摊清单后写 ⇒ 工作树 `??`；`_next_version(get_version())` 在 bump 之后再 +1（清单写 0.1.13，实为 0.1.12）；archive 后 glob 审计报告得到 `-`。seal 动作链也没有 sync ⇒ 随后 `DOC_INDEX_STALE`。

## 已确认意图

收摊清单是封板产物，必须进**那次封版提交**；记的版本是终版；证据指针指向本轮报告（归档后的路径也行）。

## 证据（M10 真跑，seal 提交 dea69ca 之后）

```
git status: ?? docs/reviews/2026-09-20-M10-closure.md
清单第 4 条：「归档 + 收摊 + 文档一起进一个 commit」——做不到
§5 TSV evidence=`-`  result=`0.1.13`
实际：pyproject/version = 0.1.12；报告已在 docs/reviews/archive/M10/
k3dge check：DOC_INDEX_STALE（归档 + 后写的 closure 让索引过期）
```

`_write_closure_note`（`seal_flow.py`）：

```
cur = get_version(workspace)          # 此时已是 bump 后的 0.1.12
sealed_version = _next_version(cur, "patch")   # → 0.1.13
audit_reports = glob(docs/reviews/*-{id}-*.md) # archive 之后顶层没有
```

## 方案

```
① 声明序：closure_note（+ 需要进提交的 sync/docs-index）在 seal_record 之前
② 版本：bump 已发生 ⇒ 记 get_version()；未发生才 _next_version
③ 证据 glob 含 archive/<id>/，或 archive 前先记下报告名
④ 单测：跑完 run_seal_flow 后 closure 文件在封版提交里；正文版本 == pyproject；evidence ≠ '-'
```

## 边界与拆分

- 事实归属：动作序归 `[checks.seal].actions`；清单内容归 `seal_flow._write_closure_note`；提交归 `seal.seal_record`。
- 边界检查：closure 是投影（可重生成），但必须在记录提交之前落盘。
- 桩子先行：真 git 临时仓跑 seal_record 前后看工作树是否含 closure。

## 结案

- 声明序 closure_note 在 seal_record 前；记 get_version()；glob 含 archive/<id>/；写清单后 write_docs_index。
