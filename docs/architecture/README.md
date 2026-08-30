# Architecture — 架构叙述

`docs/architecture/overview.md` 是全仓架构的唯一叙述源；各域边界、分层与协议引用见该文。

## 文档编撰规则 (Document Authoring Rules)

- 仅 `overview.md` 一篇，作为架构事实源；新决策优先落成 `docs/adr/` 而非在此扩写。
- 章节以稳定 `§N` 编号，被其它文档（incidents / reviews / guides）反向引用时不得更名或重排。
- 改动须与对应 `ADR` 对齐（见 `docs/adr/README.md`）；不在此存放过程状态。
