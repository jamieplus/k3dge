$ErrorActionPreference = "Stop"

# Initialize the CURRENT WORKING DIRECTORY as a k3dge-governed project.
# TARGET is always pwd. Harness directories come from scaffold.

$Target = (Get-Location).Path
# `$PSScriptRoot` 在 `iex (Get-Content …)`/`pwsh -Command` 内联等场景是**空串**，
# `Split-Path -Parent ''` 返回"当前目录的父目录"⇒ K3dgeHome 会指向一个无关目录（378）。
$ScriptRoot = if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { "" }

if ($env:K3DGE_SOURCE) {
  $K3dgeHome = $env:K3DGE_SOURCE
} elseif ($ScriptRoot -and (Test-Path -LiteralPath (Join-Path $ScriptRoot "src/k3dge"))) {
  $K3dgeHome = $ScriptRoot
} else {
  # Stop 偏好下 `Write-Error` 本身就是终止错误 ⇒ 紧随的 `exit 1` 永不执行，调用方拿到未处理异常
  # 而不是干净退出码（379）。写 stderr + 显式退出。
  [Console]::Error.WriteLine("K3DGE_SOURCE is required（本目录不是 k3dge checkout，且定位不到脚本所在目录）")
  [Console]::Error.WriteLine("  用文件路径跑：powershell -File .\k3dge-init.ps1（在目标项目目录里）")
  exit 1
}

Set-Location $Target

# 宣称要 >=3.10 就必须**验版本**：只做存在性检查时，低版本一路跑到 pip/scaffold 才报
# 难懂的语法/导入错（359）。Windows 上 `python3` 常是商店占位符 ⇒ 优先 `python`。
if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command python3 -ErrorAction SilentlyContinue)) {
  [Console]::Error.WriteLine("python (>=3.10) is required")     # 同 379：Stop 下 Write-Error 会吞掉 exit 码
  exit 1
}
$Py = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "python3" }
$prevPref = $ErrorActionPreference; $ErrorActionPreference = "Continue"
try { & $Py -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" *> $null }
catch { $global:LASTEXITCODE = 1 }
finally { $ErrorActionPreference = $prevPref }
if ($LASTEXITCODE -ne 0) {
  [Console]::Error.WriteLine("[k3dge] 需要 Python >= 3.10，实际：$(& $Py --version 2>&1)（`$Py='$Py'）")
  exit 1
}

# 只看**当前目录**有没有 `.git` ⇒ 在既有仓库的子目录里跑 init 会造嵌套仓：外层仓的提交
# 完全绕过 k3dge 闸口（360）。用 rev-parse 向上找真正的仓根。
$prevPref = $ErrorActionPreference; $ErrorActionPreference = "Continue"
try { $top = ((& git rev-parse --show-toplevel 2>$null) | Out-String).Trim() }
catch { $top = "" }
finally { $ErrorActionPreference = $prevPref }
if ($LASTEXITCODE -ne 0 -or -not $top) {
  Write-Host "[k3dge] git init -b main  ($Target)"
  git init -b main
} elseif (((Resolve-Path $top).Path).TrimEnd('\','/') -ne ((Resolve-Path $Target).Path).TrimEnd('\','/')) {
  [Console]::Error.WriteLine("[k3dge] 当前目录在既有仓库里（toplevel=$top）但根不是目标目录 ⇒ 拒跑（会造嵌套仓，绕过外层闸口）")
  exit 1
}

$VenvPy = Join-Path $Target ".venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $VenvPy)) {
  $VenvPyUnix = Join-Path $Target ".venv/bin/python"
  if (-not (Test-Path -LiteralPath $VenvPyUnix)) {
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

# 不再单独探 `pip.exe`/`bin/pip`：探测不到就无条件当 Unix 路径用的兜底**从不验存在**（361）。
# 上面已验过的 `$PyVenv -m pip` 才是唯一入口。
$PyVenv = if (Test-Path -LiteralPath (Join-Path $Target ".venv/Scripts/python.exe")) {
  Join-Path $Target ".venv/Scripts/python.exe"
} else {
  Join-Path $Target ".venv/bin/python"
}
# venv 解释器必须真的在（.venv 目录残留会骗过 `Test-Path .venv`），且 pip 可用（坏 venv 的报错最难查，ocr-167）。
if (-not (Test-Path -LiteralPath $PyVenv -PathType Leaf)) {
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
  & $PyVenv -m pip install -q -e ".[dev]"
  if ($LASTEXITCODE -ne 0) { [Console]::Error.WriteLine("[k3dge] pip install 失败 (exit $LASTEXITCODE)"); exit 1 }
} else {
  $InstallFlags = @()
  if ([string]::IsNullOrWhiteSpace($env:K3DGE_SOURCE) -or $env:K3DGE_SOURCE -eq "pypi") {
    $InstallTarget = "k3dge[mcp]"
    Write-Host "[k3dge] Installing from package index (PyPI)..."
  } elseif (Test-Path -LiteralPath $env:K3DGE_SOURCE -PathType Container) {
    $InstallTarget = "$($env:K3DGE_SOURCE)[mcp]"
    $InstallFlags += "-e"
    Write-Host "[k3dge] Installing editable from local path: $env:K3DGE_SOURCE"
  } elseif ($env:K3DGE_SOURCE -match '^(git\+|https?://(github\.com|gitlab\.com|bitbucket\.org)|.*\.git)') {
    # pip 的 direct reference 要 PEP 440 形式 `git+<url>`：裸 `https://github.com/o/r` 会被 pip
    # 拒（分类正则放行≠语法合法，362）⇒ 归一化补 `git+`。
    $Src = $env:K3DGE_SOURCE
    if ($Src -notmatch '^git\+') { $Src = "git+$Src" }
    $InstallTarget = "k3dge[mcp] @ $Src"
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
  if ([string]::IsNullOrWhiteSpace($env:K3DGE_SOURCE) -and (Test-Path -LiteralPath (Join-Path $K3dgeHome "src/k3dge"))) {
    $InstallTarget = "$K3dgeHome[mcp]"
    $InstallFlags = @("-e")
    Write-Host "[k3dge] Installing editable from K3DGE_HOME: $K3dgeHome"
  }
  & $PyVenv -m pip install -q @InstallFlags $InstallTarget pre-commit pytest
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

$K3dgeExe = if (Test-Path -LiteralPath (Join-Path $Target ".venv/Scripts/k3dge.exe")) {
  Join-Path $Target ".venv/Scripts/k3dge.exe"
} else {
  Join-Path $Target ".venv/bin/k3dge"
}
# 兜底路径**必须验存在**：venv 里没有这个入口还继续 `&` 会抛 CommandNotFoundException
# （报错与真实原因无关），而它上游的退出码又没查 ⇒ 半初始化一路装完（361）。
if (-not (Test-Path $K3dgeExe -PathType Leaf)) {
  [Console]::Error.WriteLine("[k3dge] 找不到 k3dge 入口：$K3dgeExe ⇒ pip install 未落进本 venv，删 .venv 重跑 init")
  exit 1
}
Write-Host "[k3dge] k3dge sync"
& $K3dgeExe sync
if ($LASTEXITCODE -ne 0) { [Console]::Error.WriteLine("[k3dge] k3dge sync 失败 (exit $LASTEXITCODE)"); exit 1 }

$PreCommit = if (Test-Path -LiteralPath (Join-Path $Target ".venv/Scripts/pre-commit.exe")) {
  Join-Path $Target ".venv/Scripts/pre-commit.exe"
} else {
  Join-Path $Target ".venv/bin/pre-commit"
}
Write-Host "[k3dge] pre-commit install"
# 同 `$K3dgeExe`：兜底的 Unix 路径从不验存在 ⇒ `&` 抛的错与真实原因无关（361）
if (-not (Test-Path -LiteralPath $PreCommit -PathType Leaf)) {
  [Console]::Error.WriteLine("[k3dge] 找不到 pre-commit 入口：$PreCommit ⇒ hook 没装上就是假安全")
  exit 1
}
& $PreCommit install
if ($LASTEXITCODE -ne 0) { [Console]::Error.WriteLine("[k3dge] pre-commit install 失败 (exit $LASTEXITCODE)"); exit 1 }
& $PreCommit install --hook-type commit-msg
if ($LASTEXITCODE -ne 0) { [Console]::Error.WriteLine("[k3dge] pre-commit install commit-msg 失败 (exit $LASTEXITCODE)"); exit 1 }

Write-Host ""
Write-Host "[k3dge] Initialization complete for $Target"
