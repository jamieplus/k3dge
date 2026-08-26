# Domain Specification: sync

- **Status**: Active
- **Module Path**: `src/k3dge/sync`
- **Contract Hash**: `sha256:594d35489e70db9e99394859007ae76bf3007ebdab23ca2a4ffa21a7d7f39673`
- **Last Updated**: 2026-08-25

## 1. Domain Boundary & Responsibilities
- **In Scope**:
  - 从域源码提取公开接口并生成 spec 的接口代码块。
  - 计算契约哈希并回写 `**Contract Hash**` 字段。
  - 更新 `**Last Updated**` 日期。
  - 生成 `docs/reference/` 机器文档（`api.md` / `domains.md`，无需 agent）。
  - 支持指定单个域或全部域同步。
- **Out of Scope**:
  - 接口签名提取的底层实现（由 `engine.contract` 负责）。
  - CLI 参数解析（由 `cli` 域负责）。

## 2. Public Interfaces & Type Contracts
<!-- k3dge:interfaces-start -->
```python
sync_domain(workspace: Path, manifest: Manifest, domain: str, iface: str | None=None) -> Optional[Path]
render_readme_layout(workspace: Path, manifest: Manifest) -> Optional[Path]
render_manual_docs(workspace: Path, manifest: Manifest, doc_cache: dict[str, str] | None=None) -> List[Path]
sync_all(workspace: Path, domains: Optional[Sequence[str]]=None) -> Tuple[List[str], bool]
```
<!-- k3dge:interfaces-end -->

## 3. State Machine & Invariants
- 接口块由 `<!-- k3dge:interfaces-start -->` / `--end -->` 标记包裹，可幂等重写。
- 哈希只由代码派生，禁止手写。

## 4. Verification Matrix
| Scenario ID | Level | Input Condition | Expected Outcome | Test File |
| --- | --- | --- | --- | --- |
| TC-SYNC-01 | L1 | 代码接口变更后运行 sync | spec 哈希与代码一致 | `tests/unit/sync/test_generator.py` |
| TC-SYNC-02 | L1 | `sync_all` 生成 `docs/reference/{api.md,domains.md}` | 两文件存在且幂等；README 布局不由 sync 负责 | `tests/unit/sync/test_generator.py` |
