$ErrorActionPreference = "Stop"

# Project completion script — generate human docs per config.
# Reads .agent/docs.toml and creates stub files under docs/guides/.
# Idempotent: existing files are not overwritten.

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$CONFIG = ".agent/docs.toml"
if (-not (Test-Path $CONFIG)) {
  Write-Host "[k3dge] $CONFIG not found, creating from preset..."
  New-Item -ItemType Directory -Force -Path ".agent" | Out-Null
  @(
    "[docs]",
    "readme = true",
    "user_guide = true",
    "architecture = true",
    "api_guide = false",
    "deployment = false",
    "changelog = true",
    "faq = false"
  ) | Set-Content -Path $CONFIG -Encoding utf8
}

New-Item -ItemType Directory -Force -Path "docs/guides" | Out-Null

function Test-DocsFlag([string]$key) {
  if (-not (Test-Path $CONFIG)) { return $false }
  return [bool](Select-String -Path $CONFIG -Pattern "^\s*$([regex]::Escape($key))\s*=\s*true" -Quiet)
}

if (Test-DocsFlag "readme") {
  if (-not (Test-Path "README.md")) {
    Write-Host "[k3dge] README.md not found, creating base version..."
    @(
      "# Project",
      "",
      "Spec-gate harness：为 vibecoding agent 提供确定性的契约漂移检测与 git 硬门禁。",
      "",
      "## 初始化（Init）",
      "",
      "``````bash",
      "./k3dge-init.sh",
      "``````",
      "",
      "## 布局",
      "",
      "> 基础版本随仓库存在；工程收尾时由 ``./scripts/generate-docs.sh``（agent 按 ``.agent/docs.toml``）刷新下表。",
      "",
      "域路由以 ``.agent/manifest.json`` 为唯一事实源：",
      "",
      "<!-- k3dge:layout-start -->",
      "<!-- k3dge:layout-end -->",
      "",
      "另见：``docs/specs/<domain>/spec.md``（各域契约事实源）。"
    ) | Set-Content -Path "README.md" -Encoding utf8
  }
  # README layout 归 `k3dge sync`（与 generate-docs.sh 同口径；本脚本不再触碰，消跨轨漂移与假绿，ocr-017）。
  Write-Host "[k3dge] README layout: 归 `k3dge sync`（本脚本不再触碰）"
} else {
  Write-Host "[k3dge] disabled in config, skip: readme -> README.md"
}

function Write-Guide([string]$key, [string]$file, [string]$title) {
  if (Test-DocsFlag $key) {
    if (Test-Path $file) {
      Write-Host "[k3dge] exists, skip: $file"
    } else {
      Write-Host "[k3dge] generating: $file"
      $dir = Split-Path -Parent $file
      if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
      @(
        "# $title",
        "",
        "> Auto-generated stub by ``./scripts/generate-docs.sh`` from ``.agent/docs.toml``.",
        "> Agent: please fill this document per software engineering standards, referencing",
        "> ``docs/specs/``, ``.agent/manifest.json`` and ``docs/generated/``.",
        "",
        "## 概述",
        "",
        "<!-- k3dge:guide-stub -->",
        "",
        "## 详细内容",
        "",
        "<!-- k3dge:guide-stub -->"
      ) | Set-Content -Path $file -Encoding utf8
    }
  } else {
    Write-Host "[k3dge] disabled in config, skip: $key -> $file"
  }
}

Write-Guide "user_guide"   "docs/guides/user_guide.md"   "User Guide"
Write-Guide "architecture" "docs/guides/architecture.md"  "Architecture Guide"
Write-Guide "api_guide"    "docs/guides/api_guide.md"    "API Guide"
Write-Guide "deployment"   "docs/guides/deployment.md"   "Deployment Guide"
Write-Guide "changelog"    "docs/guides/changelog.md"    "Changelog"
Write-Guide "faq"          "docs/guides/faq.md"          "FAQ"

Write-Host ""
Write-Host "[k3dge] Done. Enabled docs generated under docs/guides/ (existing files not overwritten)."
Write-Host "        Agent: please fill guide stubs (<!-- k3dge:guide-stub -->) before milestone seal."
