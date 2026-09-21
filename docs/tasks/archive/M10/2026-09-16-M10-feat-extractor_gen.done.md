---
status: done
milestone: M10
priority: P2
date: 2026-09-16
---

# 提取器生成器：`.agent/extractors.toml` + `k3dge extractor sync`

- **可检索摘要**: 为 `.agent/extractors/` 插件目录配生成器：`.agent/extractors.toml` 声明启用的语言（内置表给默认行，`[languages.*]` 自定义覆盖），`k3dge extractor sync` 渲染生成插件 `.py`（幂等、可剪枝），`k3dge sync` 顺带执行。TS 插件改为生成式（core 不再内置注册），新语言加一行配置即可。

## 意图

手写插件（复制 ts.py 改三处）可做一次，不可做十次。配置驱动生成：语言差异收敛为数据行（grammar 包、后缀、节点类型表），未知语言直接编辑配置文件加 `[languages.*]`，CLI 只管 load。

## 现状

- 插件接口已落地（`register_extractor` + manifest `extractors` + 约定目录扫描）
- TS 已是自包含插件文件（asset + 本仓 dogfood）
- 缺：从"手写插件文件"到"声明语言即生成"的最后一步

## 方案

### 1. `engine/extractor_gen.py`（新建，stdlib only）

- `DEFAULT_LANGS`：typescript / go / rust / c（节点名已实证核对，见 Notes）
- `render_plugin(name, row)`：代码生成器（非字符串模板——分支按需组装，生成的 `.py` 无死分支）
- `sync_extractors(workspace)`：读 toml → 合并内置表 → 幂等写盘（GENERATED 标记头）→ 剪枝过期生成文件（只删带标记且不在启用集的；手写文件/ README / `_*.py` 永不动）→ 缺 grammar 包只给 pip 提示，不报错
- `describe_extractors(workspace)`：供 `list` 命令

### 2. `.agent/extractors.toml`

```toml
enable = ["typescript", "go"]
[languages.mylang]
grammar = "pkg"
suffixes = [".ml"]
# …节点类型表（全键必填，错键/缺键直接报错，不静默）
```

语义：`enable` 命中内置表；`[languages.*]` 整行替换内置同名行（不逐字段合并）；自定义行 presence = 启用；未知名直接报错并列出可用内置名。

### 3. CLI：`k3dge extractor sync|list`

`sync`：执行生成 + 打印 written/pruned/pip-hint；`list`：打印解析后的语言表 + 当前生效提取器。`k3dge sync` 顺带调一次（迁移零步骤）。

### 4. TS 迁移

asset `ts.py` 删除（改为生成）；本仓 `.agent/extractors/ts.py` 改为生成版（含标记头，行为一致）；scaffold 改写 toml 不再拷 ts.py。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：`extractor_gen.py` 拥有表格 + 渲染；toml 拥有启用集；生成文件是派生产物（标记头声明）
- 边界检查：生成器不装包（只打印 pip 命令，venv 归用户）；不猜节点名（未知语言必须手写全行，错键报错）；剪枝只认标记头
- 桩子先行：先 `render_plugin` + fixture 断言（TS 生成版与现行 asset 行为一致）→ `sync` 幂等/剪枝测试 → CLI 接线 → 删 asset 迁 TS

## Notes

- 节点名实证（2026-09-16，tree-sitter 0.26 + 各 grammar 最新版，sample parse 确认）：
  - go：顶层 `function_declaration`（具名 New）/`method_declaration`（具名 Start）为方法——方法天然顶层，无需容器；`type_declaration` 整片切（含字段）
  - rust：`impl_item`/`trait_item` 下挂 `declaration_list`（需成员步进，与 TS class_body 同构）；trait 成员是 `function_signature`（无体，切片即签名）；`mod_item`/`use_declaration` 跳过
  - c：全平；`function_definition` 的 name 字段为空（走 declarator 链），但切片不需要名字，无影响；`preproc_include` 跳过，`preproc_def` 整片收录
  - 通用规则：含逻辑体的容器走成员步进，只含声明的容器整片收录；import/include 类一律跳过
- TS 保真要求：生成版 ts.py 对同一样本必须输出与现行版完全一致（迁移不红闸），fixture 锁定
- cpp/java 未核对，不进内置表（后续 task 逐个实证加入）

## 结案

- 关闭提交：`ebaff64`（2026-09-18）
- 落地记录：见该提交 message 与本文正文（回填于 2026-09-19，事实取自 `git log --diff-filter=AR -1 -- <path>`）。
