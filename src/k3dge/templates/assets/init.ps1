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

$self = ((Resolve-Path $K3dgeHome).Path -eq (Resolve-Path $Target).Path)
if ($self) {
  Write-Host "[k3dge] pip install -e .[dev] (self)"
  & $Pip install -q -e ".[dev]"
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
    $InstallTarget = "$($env:K3DGE_SOURCE)[mcp]"
    Write-Host "[k3dge] Installing from source/package: $env:K3DGE_SOURCE"
  }
  if ([string]::IsNullOrWhiteSpace($env:K3DGE_SOURCE) -and (Test-Path (Join-Path $K3dgeHome "src/k3dge"))) {
    $InstallTarget = "$K3dgeHome[mcp]"
    $InstallFlags = @("-e")
    Write-Host "[k3dge] Installing editable from K3DGE_HOME: $K3dgeHome"
  }
  & $Pip install -q @InstallFlags $InstallTarget pre-commit pytest
}

Write-Host "[k3dge] generating harness scaffolding in $Target ..."
& $PyVenv -m k3dge.templates.scaffold $Target

$K3dgeExe = if (Test-Path (Join-Path $Target ".venv/Scripts/k3dge.exe")) {
  Join-Path $Target ".venv/Scripts/k3dge.exe"
} else {
  Join-Path $Target ".venv/bin/k3dge"
}
Write-Host "[k3dge] k3dge sync"
& $K3dgeExe sync

$PreCommit = if (Test-Path (Join-Path $Target ".venv/Scripts/pre-commit.exe")) {
  Join-Path $Target ".venv/Scripts/pre-commit.exe"
} else {
  Join-Path $Target ".venv/bin/pre-commit"
}
Write-Host "[k3dge] pre-commit install"
& $PreCommit install
& $PreCommit install --hook-type commit-msg

Write-Host ""
Write-Host "[k3dge] Initialization complete for $Target"
