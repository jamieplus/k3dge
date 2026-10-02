#!/usr/bin/env bash
set -euo pipefail

# Project completion script — generate human docs per config.
# Reads .agent/docs.toml (preset template, true/false multiple-choice) and
# creates stub files under docs/guides/ for agent to fill per software engineering standards.
# Idempotent: existing files are not overwritten.

# ROOT 由"本脚本在 <root>/scripts/ 下"推出：`pwd`（逻辑路径）经符号链接/复制会指错根，
# 而且从不验根 ⇒ 政策、配置、docs 全在错根上算（355）。取物理路径 + 布局校验。
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [ ! -d "$ROOT/.agent" ] && [ ! -d "$ROOT/docs" ]; then
  echo "[k3dge] generate-docs.sh: 推断的仓根 '$ROOT' 既无 .agent/ 也无 docs/ ⇒ 布局假设不成立，拒跑" >&2
  exit 1
fi
cd "$ROOT"

CONFIG=".agent/docs.toml"
if [ ! -f "$CONFIG" ]; then
  echo "[k3dge] $CONFIG not found, creating from preset..."
  mkdir -p .agent
  # 首选字节锁定的模板（`pairs.PAIRS` 把 `.agent/docs.toml` 与它对锁）；就地重写一份内联预设
  # 会让"配置丢失→恢复"这条路造出与模板不一致的内容 ⇒ 自举下 TEMPLATE_DRIFT 红（ocr-164）。
  TPL="$ROOT/src/k3dge/templates/assets/docs.toml.template"
  if [ -f "$TPL" ]; then
    cp "$TPL" "$CONFIG"
  else
    cat > "$CONFIG" << 'EOF'
[docs]
readme = true
user_guide = true
architecture = true
api_guide = false
deployment = false
changelog = true
faq = false
EOF
  fi
fi

mkdir -p docs/guides

# README has a base version that always exists; refresh its layout when enabled
if grep -Eq "^[[:space:]]*readme[[:space:]]*=[[:space:]]*true" "$CONFIG"; then
  if [ ! -f "README.md" ]; then
    echo "[k3dge] README.md not found, creating base version..."
    cat > README.md << 'EOF'
# Project

Spec-gate harness：为 vibecoding agent 提供确定性的契约漂移检测与 git 硬门禁。

## 初始化（Init）

```bash
./k3dge-init.sh
```

## 布局

> 基础版本随仓库存在；域表由 `k3dge sync` 从 `.agent/manifest.json` 刷新（不再由本脚本碰）。

域路由以 `.agent/manifest.json` 为唯一事实源：

<!-- k3dge:layout-start -->
<!-- k3dge:layout-end -->

另见：`docs/specs/<domain>/spec.md`（各域契约事实源）。
EOF
  fi
  echo '[k3dge] README layout: 归 `k3dge sync`（本脚本不再触碰）'
else
  echo "[k3dge] disabled in config, skip: readme -> README.md"
fi

# helper: create file if enabled and not exists
gen() {
  local key="$1" file="$2" title="$3"
  # 与门禁 `_check_docs_toml` 同判据（全文件找 `key = true`），但用 **POSIX 字符类**：
  # BSD/macOS 的 `grep -E` 不支持 `\s`（会退化成匹配字面 `s`，静默漏判/误开，ocr-165）。
  # `grep -Eq` 的 rc=2（读不出/权限/二进制）在 `if` 条件里不触发 `set -e`，会掉进 else
  # ⇒ 每项都报"disabled in config"并以 0 退出：配置坏了却装作跑成功（357）。
  local _rc=0
  grep -Eq "^[[:space:]]*${key}[[:space:]]*=[[:space:]]*true([[:space:]#]|$)" "$CONFIG" || _rc=$?
  if [ "$_rc" -ge 2 ]; then
    echo "[k3dge] 读不出 $CONFIG（grep rc=$_rc）⇒ 中止，不按'未启用'处理" >&2
    exit 1
  fi
  if [ "$_rc" -eq 0 ]; then
    if [ -f "$file" ]; then
      echo "[k3dge] exists, skip: $file"
    else
      echo "[k3dge] generating: $file"
      # 就地 `> "$file"` 先截断：中途失败（磁盘满/被杀/并发）留下半成品，而"存在即跳过"
      # 让它**永久**停在半成品上，与脚本开头宣称的幂等不符（356）⇒ 同目录临时件 + mv 原子落盘。
      local tmp
      tmp="$(mktemp "${file}.XXXXXX")"
      printf '# %s\n\n' "$title" > "$tmp"
      cat >> "$tmp" << 'EOT'
> Auto-generated stub by `./scripts/generate-docs.sh` from `.agent/docs.toml`.
> Agent: please fill this document per software engineering standards, referencing
> `docs/specs/`, `.agent/manifest.json` and `docs/generated/`.

## 概述

<!-- k3dge:guide-stub -->

## 详细内容

<!-- k3dge:guide-stub -->

EOT
      if ! mv "$tmp" "$file"; then
        rm -f "$tmp"
        echo "[k3dge] 落盘失败：$file" >&2
        exit 1
      fi
    fi
  else
    echo "[k3dge] disabled in config, skip: $key -> $file"
  fi
}

gen "user_guide"   "docs/guides/user_guide.md"   "User Guide"
gen "architecture" "docs/guides/architecture.md"  "Architecture Guide"
gen "api_guide"    "docs/guides/api_guide.md"    "API Guide"
gen "deployment"   "docs/guides/deployment.md"   "Deployment Guide"
gen "changelog"    "docs/guides/changelog.md"    "Changelog"
gen "faq"          "docs/guides/faq.md"          "FAQ"

echo ""
echo "[k3dge] Done. Enabled docs generated under docs/guides/ (existing files not overwritten)."
echo "        Agent: please fill guide stubs (<!-- k3dge:guide-stub -->) before milestone seal."
