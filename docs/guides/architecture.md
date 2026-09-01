# Architecture Guide

人读导读。跨域不变量与依赖方向以 [`docs/architecture/overview.md`](../architecture/overview.md) 为判据，本文不复制。

## 概述

k3dge 是一致性门禁：`check` 比对公开签名哈希，`sync` 回写 spec，`milestone` 做对齐与封板。域地图见 overview §1。

## 详细内容

* 域与依赖：`docs/architecture/overview.md` §1–2
* 提交数据流：`docs/architecture/overview.md` §3
* 已定案决策：`docs/architecture/overview.md` §8 及 `docs/adr/README.md`
* 有意留：`docs/reviews/LEFTOVERS.md`（`overview §8` 为索引）
* 本地自用与职责切分：`docs/adr/0005-local-first-and-layer-cuts.md`
