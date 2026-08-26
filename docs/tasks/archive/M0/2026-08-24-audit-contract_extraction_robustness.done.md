# 契约抽取：失败可见、TS 只哈希签名、补 `cached_property`

- **Status**: done
- **Milestone**: M0
- **Priority**: P1
- **Date**: 2026-08-24
- **来源**：[docs/reviews/2026-08-24-5pass-audit.md](../reviews/2026-08-24-5pass-audit.md) A-06 / A-07 / A-12

## 可检索摘要
三处使「公开接口哈希」承诺落空：(1) `collect_domain_interface` 对 `SyntaxError`/`UnicodeDecodeError`/`OSError`/`ImportError` 静默跳过，域内新增语法损坏文件不改哈希，无 `--with-tests` 时 `check` 放行；(2) TypeScript 抽取使用 tree-sitter 节点起止字节，把函数体和顶层非 export `lexical_declaration` 打进哈希，直接违背 overview/engine spec「函数体不改哈希」；(3) `_SIGNIFICANT_DECORATORS` 在 F-07 后仍不含 `cached_property`，方法改属性访问器不触发漂移。

## 上下文/切入点
- 静默跳过：`src/k3dge/engine/contract.py` `collect_domain_interface` 内 `except (SyntaxError, UnicodeDecodeError, OSError, ImportError): pass`
- TS 整段：`src/k3dge/engine/_ts.py` `extract_ts_interface` 循环 `source[node.start_byte:node.end_byte]`
- 装饰器白名单：`src/k3dge/engine/contract.py` `_SIGNIFICANT_DECORATORS`
- 不变量：`docs/architecture/overview.md` §4；`docs/specs/engine/spec.md` §3「契约哈希只覆盖公开接口签名」
- 复现（A-06）：临时目录写入合法 `ok.py` 再写入 `def bar( ->` 的 `broken.py`，两次 `compute_hash(collect_domain_interface(...))` 相等

## 方案
1. 抽取失败改为可见：至少对 `.py` 的 `SyntaxError` 产生 `CONTRACT_EXTRACT_FAILED`（或等价）Violation，不要静默。`ImportError`（缺 tree-sitter）保持可选依赖语义，可继续跳过 TS。
2. TS：只序列化签名（函数名/参数/返回类型、interface/type 声明），排除函数体；忽略非 `export` 的 `lexical_declaration`。补单测（有 tree-sitter extra 时跑，无则 skip）。
3. 将 `cached_property` 加入显著装饰器白名单，并加「加/去该装饰器必改哈希」用例。改白名单会改当前 Python 域哈希当且仅当代码里已有该装饰器——本仓源码目前没有，预期 `k3dge sync` 为零漂移。

## 触发条件
用户确认后开工。若 `collect_domain_interface` 返回值形状或公开签名变化，同任务 `k3dge sync`。
