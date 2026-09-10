---
status: idea
milestone: M8
priority: P1
date: 2026-09-10
---

# 修席接受改由快照 diff 推断（禁二值空翻已修）

- **Status**: idea
- **Milestone**: M8
- **Priority**: P1
- **可检索摘要**: 活体 a950ab294b34：修席 accepted:true，`_apply_live` 把 25 条 pending 全翻已修；main↔线除 25 枚钉和 incidents/_template.md 外无代码改——报告撒谎
- **Date**: 2026-09-10

## Intent

落地 ADR-0025 §2.7「修=对 Hall 物化只读原快照 diff 推接受」。席不再用 `accepted:true` 把未改代码的发现标成已修。这是修/核窗批（step4），判读钉-only 批已过。

## Notes

- 实证：job `a950ab294b34` findings 25/25 `fixed`；线 `k3dit/M8` @ `010f1e0` vs main `e9fd924` 真改代码仅 `docs/incidents/_template.md`（doc-1）。其余 24 条是判读钉被合线带上，修席未重构。
- 现行：`hall._apply_live` 修席腿 `if artifact.get("accepted"):` 对所有 pending/fixnote 一次翻 `fixed`（`src/k3dit/hall.py`）。复核 `verdict != bounce` 再 `review_ack`。
- 目标：物化时留只读快照（窗无 `.git`）；包装器/Hall 对窗 src vs 快照 diff；**有 diff 的文件上的钉**才可标 fixed；无 diff 的钉保持 pending（或席翻 leftover/disputed + 短 how）。禁止整单 `accepted` 一票全翻。
- 复核：无 src 变化却全 fixed → bounce，不得 closed。
- 本单不合主干；`incidents/_template.md` 真修若要保留，另 cherry-pick，不随假已修线走。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：快照属 Hall 物化；diff 属进程；「拒绝 + how」属修席在树上翻 leftover/disputed；已修状态属账本，由进程根据 diff 写，不由席 JSON。
- 边界检查：Hall 不判改得对不对（那是复核窗）；只判「有没有改到这个钉所在文件」。
- 桩子先行：假修席只写 accepted、不改 src → 账本不得出现 fixed；改一文件 → 仅该文件上的钉 fixed。

## 原话备查

「修/核二值 accepted 让报告谎报已修（就是 §2.7 未落地的修席 diff 推断）。绝不该合主干。」
