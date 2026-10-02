$ErrorActionPreference = "Stop"

# Project completion script — generate human docs per config.
# Reads .agent/docs.toml and creates stub files under docs/guides/.
# Idempotent: existing files are not overwritten.

# dot-source / `pwsh -Command` 内联时 `$PSScriptRoot` 为空 ⇒ `Split-Path -Parent ''` 给 $null，
# 后续 Push-Location 落到错误目录（477）
$Root = if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot }
        elseif ($PSCommandPath) { Split-Path -Parent (Split-Path -Parent $PSCommandPath) }
        else { (Get-Location).Path }
if (-not (Test-Path -LiteralPath (Join-Path $Root ".agent"))) {
  [Console]::Error.WriteLine("[k3dge] 定位到的项目根没有 .agent/（$Root）⇒ 请用文件路径运行：pwsh -File ./scripts/generate-docs.ps1")
  exit 1
}
# `Set-Location` 是**进程级**副作用：`.sh` 的 `cd` 关在子进程里不泄漏，而本脚本被 `&`/点源调用时
# 会把调用方的当前位置改掉且永不恢复（376）。`trap ... EXIT` 不是合法 PowerShell（trap 只认
# Break/Continue，EXIT 会被当成错误类型名 ⇒ 静默不执行，ocr2-018）。用 `try/finally` 包住主体，
# 任何出口（含 `exit 1`）都还原（`exit` 会先跑 `finally`）。
Push-Location $Root
try {

$CONFIG = ".agent/docs.toml"
# 与 .sh 轨统一：**LF + 无 BOM** 写盘。`Set-Content -Encoding utf8` 在 WinPS 5.1 写 BOM、Windows
# 上按 `[Environment]::NewLine` 拼 CRLF ⇒ 自家 MD_CRLF/MD_ENCODING（block）会拦自己生成的桩（ocr-161）。
$UTF8LF = New-Object System.Text.UTF8Encoding($false)
function Write-TextFile([string]$path, [string[]]$lines) {
  # 相对路径喂 `[System.IO.File]` 会按**进程** CWD 解析，不是 PowerShell 当前位置（ocr2-019）。
  # `Push-Location` 只改 provider 位置 ⇒ 必须拼成绝对路径再写，否则文件落到调用方目录。
  if (-not [System.IO.Path]::IsPathRooted($path)) { $path = Join-Path $Root $path }
  [System.IO.File]::WriteAllText($path, (($lines -join "`n") + "`n"), $UTF8LF)
}
$script:Fails = 0

if (-not (Test-Path $CONFIG)) {
  Write-Host "[k3dge] $CONFIG not found, creating from preset..."
  New-Item -ItemType Directory -Force -Path ".agent" | Out-Null
  try {
    Write-TextFile $CONFIG @(
      "[docs]",
      "readme = true",
      "user_guide = true",
      "architecture = true",
      "api_guide = false",
      "deployment = false",
      "changelog = true",
      "faq = false"
    )
  } catch { $script:Fails++; Write-Host "[k3dge] FAIL: $CONFIG：$_" }
}

New-Item -ItemType Directory -Force -Path "docs/guides" | Out-Null

# 与门禁侧 `_check_docs_toml` 同一判据（Python 正则大小写敏感、只认 `= true`）：
# `Select-String` 默认**不敏感** ⇒ `README = true`/`Api_Guide = True` 在这里算启用、闸算没启用（双轨互斥，ocr-159）。
function Test-DocsFlag([string]$key) {
  if (-not (Test-Path $CONFIG)) { return $false }
  return [bool](Select-String -Path $CONFIG -Pattern "^\s*$([regex]::Escape($key))\s*=\s*true\b" -CaseSensitive -Quiet)
}

if (Test-DocsFlag "readme") {
  if (-not (Test-Path "README.md")) {
    Write-Host "[k3dge] README.md not found, creating base version..."
    try {
      Write-TextFile "README.md" @(
        "# Project",
        "",
        "Spec-gate harness：为 vibecoding agent 提供确定性的契约漂移检测与 git 硬门禁。",
        "",
        "## 初始化（Init）",
        "",
        "```bash",
        "./k3dge-init.sh",
        "```",
        "",
        "## 布局",
        "",
        "> 基础版本随仓库存在；域表由 ``k3dge sync`` 从 ``.agent/manifest.json`` 刷新（不再由本脚本碰）。",
        "",
        "域路由以 ``.agent/manifest.json`` 为唯一事实源：",
        "",
        "<!-- k3dge:layout-start -->",
        "<!-- k3dge:layout-end -->",
        "",
        "另见：``docs/specs/<domain>/spec.md``（各域契约事实源）。"
      )
    } catch { $script:Fails++; Write-Host "[k3dge] FAIL: README.md 落盘：$_" }
  }
  # README layout 归 `k3dge sync`（与 generate-docs.sh 同口径；本脚本不再触碰，消跨轨漂移与假绿，ocr-017/160）。
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
      try {
        Write-TextFile $file @(
          "# $title",
          "",
          "> Auto-generated stub by ``./scripts/generate-docs.ps1`` from ``.agent/docs.toml``.",
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
        )
      } catch { $script:Fails++; Write-Host "[k3dge] FAIL: $file：$_" }
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
if ($script:Fails -gt 0) {
  # 无步骤级失败聚合 ⇒ 中途写盘失败仍打 Done（高估完成度，收尾清单被骗，ocr-163）。
  Write-Host "[k3dge] INCOMPLETE: $script:Fails 步失败（见上 FAIL 行）。"
  exit 1
}
Write-Host "[k3dge] Done. Enabled docs generated under docs/guides/ (existing files not overwritten)."
Write-Host "        Agent: please fill guide stubs (<!-- k3dge:guide-stub -->) before milestone seal."
} finally { Pop-Location }
