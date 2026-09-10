# Memo: DeepTutor 吸收评估（2026-09-06）

- **类型**: 可落地（两条，洁净室；其余排除）
- **念头**: 扫 `workspace/DeepTutor`（HKU lifelong tutoring，Apache-2.0），找能被审计模块/k3che 吸收的模式。只搬模式/判据，零粘代码；1 行署名。
- **触发场景**: 2026-09-06 会话，维护者问"DeepTutor 里有值得吸收的设计吗"
- **Date**: 2026-09-06

## 1. 吸收：AST import 边表抽取器 → 工具面依赖图事实

- **来源**: `DeepTutor/scripts/check_architecture.py`（197 行）+ `tests/architecture/test_import_boundaries.py`（CI 门）。
- **搬什么（模式）**: `ast.walk` 全量扫（含函数内 import）+ 相对导入解析 + 边表 `(importer, imported, path, line)`。这正是 graph memo §7"依赖/import 环→SCC→WARN"缺的**边表抽取器**——stdlib `ast`，零依赖，符合工具面实现政策（stdlib 优先）。
- **落点**: 审计模块工具面 `import_graph()`（G4 工具面），喂 SCC/拓扑序（stdlib `graphlib`）。测试形态照搬：脚本 + CI 断言 exit 0。
- **不搬**: 它的边界规则文本（DeepTutor 自家分层），只搬抽取机制。

## 2. 吸收：检索失败 16 模式 + 诊断清单 → k3che / 复核窗

- **来源**: `DeepTutor/REASONING_SAFETY_CHECKLIST.md`（Quick Diagnostic 6 问 + Failure Modes 表 + Retrieval Failure Patterns 16 条 + Evidence Collect + Issue 模板）。
- **搬什么（判据）**:
  - 16 条 retrieval patterns（no retrieval / wrong scope / stale / chunk split / near-topic drift / keyword mismatch / duplicated chunks / over-broad top-k / missing rerank / conflicting sources / citation mismatch / hallucinated evidence 等）→ **k3che 检索失败分类**：k3che 的 miss 不再只是一个数，每个 miss 可归类（这正是 k3che stats 缺的维度）。
  - Failure Modes 表形态（症状/成因/检查三列）→ 复核窗"证据可信度"判据：引用检索证据的发现，先过失败分类。
  - Evidence Collect 清单 → issue/B-T-D 模板的证据段。
- **落点**: k3che guides + stats 分类字段（k3che 仓 task）；复核窗引用（protocol 一节）。
- **吸收时改进（DeepTutor 原文不动，改进落在我方实现）**：
  1. 按流水线阶段分层（query 改写→召回→rerank→引用→成文），16 条归位到阶段，每阶段配可观测信号；
  2. 拆可机检（empty/stale/duplicated/citation mismatch，进 k3che 工具面自动打标）与需判断（drift/near-topic/keyword mismatch，进复核窗判据）；
  3. 挂严重度 + 证据降级触发器：致命（幻觉证据/引用对不上）→阻断，降质（top-k 过宽/缺 rerank）→待确认；命中即按 ADR-0005 置信分层自动降级。
- **不搬**: tutoring 业务语义（learner/book/quiz），只搬失败分类学与清单形态。

## 3. 排除（附因）

- `SKILL.md`（CLI skill 写作格式）：technical-writing 已吸收过同类，无增量。
- `learning/mastery.py`、`grading.py`（掌握度/评分）：教育评分语义，与质量度量不同构，不硬套。
- `knowledge/*`（KB 管理）：RAG 业务层，k3che 只做索引/检索，不碰 KB 语义。
- 编排/多用户/鉴权（`agents/`、`multi_user/`、`partners/`）：业务运行时，与 Hall 无对应。

## 4. 执行

- P1：条目 1 随 G4 工具面落地（边表抽取器是 G4 注入管线的前置事实源）。
- P2：条目 2 记 k3che 仓 task（stats 分类 + guides），复核窗引用随 protocol 增补。
