---
Status: Proposed
Supersedes: -
Amended-by: -
Landed-by: src/k3dge/engine/attest.py
Date: 2026-10-04
Deciders: Core Maintainer
Note: OCR ocr3-009（dccff5f6 扫描）记入的安全留留，上升为一项决策；实现前需 k3dit/人审核。
---

# ADR-0028: Attestation token 应有足够熵

## 1. 上下文 (Context)

- `chore(seal):` 提交靠 `k3dge-commit:` trailer 在 CI 全量验证、作为「该提交经受管路径落地」的证据。
- 当前 token 算法是 `token = WORDLIST[sha256(secret|window|tree) mod 26]`（`src/k3dge/engine/attest.py`）：只保留了模 26 之后的那个词，~4.7 bit；`verify_commit` 还接受前后分钟相邻三窗内的任一词，单次伪造命中上限约 3/26。
- 未设 `K3DGE_ATTEST_SECRET` 时本行退化为公开常量威慑（见 `[ATTEST] WARN: ...`），此时 token 熵更不是承诺。

## 2. 决策 (Decision)

- **安全前提下的 token 必须足以绑定 secret**：不再以「单词表模 26」作为可靠性的承诺；实现方必须能从 `secret` 派生出**至少等价于 128 bit 可比较熵**的证据（如 `4–6` 个独立 digest word 拼接、或完整 hex digest 的分档截断）。
- **兼容策略**：新 token 格式生效时，封版基线应记录 token `format`（或以 `attest_v2` 之类方式区分），`verify_commit` 按现行批次落在同一 `format` 内校验；旧 `format` 行只发「归档威慑」语义，不作为可运行信证明。
- **非目标**：加长 sha256 摘要不防止 CI 环境的 secret 泄露；这类事故的处置仍是换密与全量重验，已在 SECURITY.md 说明。

## 3. 产生后果 (Consequences)

- **Up**：伪造的单次有效命中从 ~11.5% 降到 ~2^-128，引入高组合熵后 token 才真正撑起「证明」语义。
- **Down**：更换 token 格式破旧 `chore(seal):` 的可验证面；需在过渡窗内让重新封章的版本显式携带新语义，并阻止旧比对误判。
- **Reopen when**：当发现多方 agent/系统在生产上仍依赖旧 token 位长进行校验，或 CI 使用新格式后的实证表明仍存在可企业伪造面时，重开此议题再校准。
