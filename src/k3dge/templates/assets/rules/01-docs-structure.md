# Rule 01: Docs Structure

> Protocol slice for tools that look under `.agent/rules/` (ADR-0010).
> Live protocol is repo-root `AGENTS.md`. If this file disagrees, `AGENTS.md` wins.

1. Never place files directly under `docs/` except `docs/README.md`.
2. Write `docs/<type>/…` → that type's `docs/<type>/AUTHORING.md` and `docs/<type>/_template.md`. Structure gate is `docs/<type>/.schema.json`.
3. Find docs with `k3dge doc list` / `k3dge doc where`. Body scan: `k3dge doc grep` (path only). Do not raw-grep `docs/`.
4. `DOCS_ROOT_DISALLOWED` is enforced by `k3dge check`.
5. 写作风格（软规则，k3dit 判；洁净室自 `pstack/technical-writing`，MIT）：先定 Diátaxis 模式（教程/操作/参考/解释），再管句子——**删不干活词**、**用短日常词**（"用"非" utilizing"）、**规则让句子更糟就改句或留原样**；写真实符号/文件/命令名（codebase 即词表），不臆造行话；长短句交替、有观点、具体优先（"列改名会让 build 失败"而非"schema 变更可能出问题"）。
