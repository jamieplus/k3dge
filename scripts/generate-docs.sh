#!/usr/bin/env bash
set -euo pipefail

# Project completion script — generate human docs per config.
# Reads .agent/docs.toml (preset template, true/false multiple-choice) and
# creates stub files under docs/guides/ for agent to fill per software engineering standards.
# Idempotent: existing files are not overwritten.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CONFIG=".agent/docs.toml"
if [ ! -f "$CONFIG" ]; then
  echo "[k3dge] $CONFIG not found, creating from preset..."
  mkdir -p .agent
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

mkdir -p docs/guides

# README has a base version that always exists; refresh its layout when enabled
if grep -Eq "^\\s*readme\\s*=\\s*true" "$CONFIG"; then
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
  echo "[k3dge] README layout: 归 `k3dge sync`（本脚本不再触碰）"
else
  echo "[k3dge] disabled in config, skip: readme -> README.md"
fi

# helper: create file if enabled and not exists
gen() {
  local key="$1" file="$2" title="$3"
  # simple TOML boolean parse: key = true (allow spaces, ignore comments)
  if grep -Eq "^\\s*${key}\\s*=\\s*true" "$CONFIG"; then
    if [ -f "$file" ]; then
      echo "[k3dge] exists, skip: $file"
    else
      echo "[k3dge] generating: $file"
      cat > "$file" << EOT
# ${title}

> Auto-generated stub by \\`./scripts/generate-docs.sh\\` from \\`.agent/docs.toml\\`.
> Agent: please fill this document per software engineering standards, referencing
> \\`docs/specs/\\`, \\`.agent/manifest.json\\` and \\`docs/generated/\\`.

## 概述

<!-- k3dge:guide-stub -->

## 详细内容

<!-- k3dge:guide-stub -->

EOT
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
