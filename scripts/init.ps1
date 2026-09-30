$ErrorActionPreference = "Stop"

# Initialize the CURRENT WORKING DIRECTORY as a k3dge-governed project.
# TARGET is always pwd. Harness directories come from scaffold.

$Target = (Get-Location).Path
$ScriptRoot = Split-Path -Parent $PSScriptRoot

if ($env:K3DGE_SOURCE) {
  $K3dgeHome = $env:K3DGE_SOURCE
} elseif (Test-Path (Join-Path $ScriptRoot "src/k3dge")) {
  $K3dgeHome = $ScriptRoot
} else {
  Write-Error "K3DGE_SOURCE is required (this directory is not a k3dge checkout).`n  `$env:K3DGE_SOURCE='/path/to/k3dge'; ./k3dge-init.ps1`n  or:  cd <project>; /path/to/k3dge/k3dge-init.ps1"
  exit 1
}

Set-Location $Target

if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command python3 -ErrorAction SilentlyContinue)) {
  Write-Error "python (>=3.10) is required"
  exit 1
}
$Py = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }

if (-not (Test-Path ".git")) {
  Write-Host "[k3dge] git init -b main  ($Target)"
  git init -b main
}

$VenvPy = Join-Path $Target ".venv/Scripts/python.exe"
if (-not (Test-Path $VenvPy)) {
  $VenvPyUnix = Join-Path $Target ".venv/bin/python"
  if (-not (Test-Path $VenvPyUnix)) {
    Write-Host "[k3dge] $Py -m venv .venv"
    & $Py -m venv .venv
    # Windows 上 `python3` 常是 Microsoft Store 的 App Execution Alias：开商店、非零退出、**什么都不建**，
    # 只看文件存在会继续往下走（半初始化）。判退出码 + 事后验解释器（ocr-167）。
    if ($LASTEXITCODE -ne 0) {
      [Console]::Error.WriteLine("[k3dge] 建 venv 失败 (exit $LASTEXITCODE)；`python3` 可能是商店占位符 ⇒ 装真 Python 或先跑：Set-Alias python3 python")
      exit 1
    }
  }
}

$Pip = if (Test-Path (Join-Path $Target ".venv/Scripts/pip.exe")) {
  Join-Path $Target ".venv/Scripts/pip.exe"
} else {
  Join-Path $Target ".venv/bin/pip"
}
$PyVenv = if (Test-Path (Join-Path $Target ".venv/Scripts/python.exe")) {
  Join-Path $Target ".venv/Scripts/python.exe"
} else {
  Join-Path $Target ".venv/bin/python"
}
# venv 解释器必须真的在（.venv 目录残留会骗过 `Test-Path .venv`），且 pip 可用（坏 venv 的报错最难查，ocr-167）。
if (-not (Test-Path $PyVenv -PathType Leaf)) {
  [Console]::Error.WriteLine("[k3dge] 无可用的 venv 解释器：$PyVenv（删 .venv 重跑 init）"); exit 1
}
& $PyVenv -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
  & $PyVenv -m ensurepip --upgrade *> $null
  & $PyVenv -m pip --version *> $null
  if ($LASTEXITCODE -ne 0) { [Console]::Error.WriteLine("[k3dge] .venv 里没有可用的 pip（删 .venv 重跑 init）"); exit 1 }
}

# K3DGE_SOURCE 可能是 pypi / git+https URL（非路径）⇒ 只在确为目录时才 Resolve（ocr-021）。
$self = $false
if (Test-Path $K3dgeHome -PathType Container) {
  $self = ((Resolve-Path $K3dgeHome).Path.TrimEnd('/','\') -eq (Resolve-Path $Target).Path.TrimEnd('/','\'))
}
if ($self) {
  Write-Host "[k3dge] pip install -e .[dev] (self)"
  & $Pip install -q -e ".[dev]"
  if ($LASTEXITCODE -ne 0) { [Console]::Error.WriteLine("[k3dge] pip install 失败 (exit $LASTEXITCODE)"); exit 1 }
} else {
  $InstallFlags = @()
  if ([string]::IsNullOrWhiteSpace($env:K3DGE_SOURCE) -or $env:K3DGE_SOURCE -eq "pypi") {
    $InstallTarget = "k3dge[mcp]"
    Write-Host "[k3dge] Installing from package index (PyPI)..."
  } elseif (Test-Path $env:K3DGE_SOURCE -PathType Container) {
    $InstallTarget = "$($env:K3DGE_SOURCE)[mcp]"
    $InstallFlags += "-e"
    Write-Host "[k3dge] Installing editable from local path: $env:K3DGE_SOURCE"
  } elseif ($env:K3DGE_SOURCE -match '^(git\+|https://(github\.com|.*\.git))') {
    $InstallTarget = "k3dge[mcp] @ $($env:K3DGE_SOURCE)"
    Write-Host "[k3dge] Installing from VCS source (non-editable): $env:K3DGE_SOURCE"
  } else {
    # 兜底把 K3DGE_SOURCE 当**包名**交给默认索引：路径打错/typosquat 会静默从 PyPI 拉同名片段（供应链面，ocr-168）。
    # 只接受合法 PEP 508 名字（不含 `/`、空格、`[`、`=`），其余直接拒。
    if ($env:K3DGE_SOURCE -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
      [Console]::Error.WriteLine("[k3dge] K3DGE_SOURCE='$($env:K3DGE_SOURCE)'：既不是已存在目录、也不是 VCS URL、也不是合法包名（PEP 508）——拒绝交给默认索引")
      exit 1
    }
    $InstallTarget = "$($env:K3DGE_SOURCE)[mcp]"
    Write-Host "[k3dge] Installing from source/package: $env:K3DGE_SOURCE"
  }
  if ([string]::IsNullOrWhiteSpace($env:K3DGE_SOURCE) -and (Test-Path (Join-Path $K3dgeHome "src/k3dge"))) {
    $InstallTarget = "$K3dgeHome[mcp]"
    $InstallFlags = @("-e")
    Write-Host "[k3dge] Installing editable from K3DGE_HOME: $K3dgeHome"
  }
  & $Pip install -q @InstallFlags $InstallTarget pre-commit pytest
  if ($LASTEXITCODE -ne 0) { [Console]::Error.WriteLine("[k3dge] pip install 失败 (exit $LASTEXITCODE)"); exit 1 }
  # 统管落盘：记录本 venv 是哪份 K3DGE_SOURCE 装出来的（运行时一律读它，不猜）
  if ($InstallTarget -eq "k3dge[mcp]") { $srcRec = "pypi" }
  elseif ($InstallTarget -match '^k3dge\[mcp\] @ ') { $srcRec = $InstallTarget -replace '^k3dge\[mcp\] @ ','' }
  else { $srcRec = $InstallTarget -replace '\[mcp\]$','' }
  # 无 BOM 写收据：`-Encoding utf8` 在 WinPS 5.1 会加 BOM ⇒ 装源字符串比较（gate.py/.sh/.ps1）误判（ocr-132）。
  [System.IO.File]::WriteAllText((Join-Path $Target ".venv/k3dge-source.txt"), $srcRec + "`n", (New-Object System.Text.UTF8Encoding($false)))
}

Write-Host "[k3dge] generating harness scaffolding in $Target ..."
& $PyVenv -m k3dge.templates.scaffold $Target
if ($LASTEXITCODE -ne 0) { [Console]::Error.WriteLine("[k3dge] scaffold 失败 (exit $LASTEXITCODE)"); exit 1 }

$K3dgeExe = if (Test-Path (Join-Path $Target ".venv/Scripts/k3dge.exe")) {
  Join-Path $Target ".venv/Scripts/k3dge.exe"
} else {
  Join-Path $Target ".venv/bin/k3dge"
}
Write-Host "[k3dge] k3dge sync"
& $K3dgeExe sync
if ($LASTEXITCODE -ne 0) { [Console]::Error.WriteLine("[k3dge] k3dge sync 失败 (exit $LASTEXITCODE)"); exit 1 }

$PreCommit = if (Test-Path (Join-Path $Target ".venv/Scripts/pre-commit.exe")) {
  Join-Path $Target ".venv/Scripts/pre-commit.exe"
} else {
  Join-Path $Target ".venv/bin/pre-commit"
}
Write-Host "[k3dge] pre-commit install"
& $PreCommit install
if ($LASTEXITCODE -ne 0) { [Console]::Error.WriteLine("[k3dge] pre-commit install 失败 (exit $LASTEXITCODE)"); exit 1 }
& $PreCommit install --hook-type commit-msg
if ($LASTEXITCODE -ne 0) { [Console]::Error.WriteLine("[k3dge] pre-commit install commit-msg 失败 (exit $LASTEXITCODE)"); exit 1 }

Write-Host ""
Write-Host "[k3dge] Initialization complete for $Target"
