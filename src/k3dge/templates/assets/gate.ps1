$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$cmdArgs = if ($args.Count -eq 0) { @("check") } else { $args }
# K3DGE_SOURCE 统管校验：环境声明的源 vs 本 venv 的装时落盘，不一致即拦。
$srcFile = Join-Path $Root ".venv/k3dge-source.txt"
$want = $env:K3DGE_SOURCE
if ([string]::IsNullOrWhiteSpace($want) -and (Test-Path (Join-Path $Root "pyproject.toml"))) {
  try { $want = (python3 -c 'import tomllib;print(tomllib.load(open("pyproject.toml","rb")).get("tool",{}).get("k3dge",{}).get("source",""))' 2>$null).Trim() } catch { $want = "" }
  if ([string]::IsNullOrWhiteSpace($want)) {
    $inSec = $false
    foreach ($ln in (Get-Content (Join-Path $Root "pyproject.toml"))) {
      if ($ln -match '^\[tool\.k3dge\]$') { $inSec = $true; continue }
      if ($inSec -and $ln -match '^\[') { break }
      if ($inSec -and ($ln -match '^source\s*=\s*"([^"]+)"')) { $want = $Matches[1]; break }
    }
  }
}
if ($want -and (Test-Path $srcFile)) {
  $rec = ((Get-Content $srcFile | Select-Object -First 1) -replace '\s','')
  if ($want -ne $rec) {
    Write-Error "[k3dge-source] MISMATCH: want='$want' (env>pyproject) but installed from '$rec'. 重装或改政策后再跑闸."
    exit 2
  }
}
if (Test-Path ".venv/Scripts/k3dge.exe") {
  & .venv/Scripts/k3dge @cmdArgs
  exit $LASTEXITCODE
}
$k3dge = Get-Command k3dge -ErrorAction SilentlyContinue
if ($k3dge) {
  & k3dge @cmdArgs
  exit $LASTEXITCODE
}
Write-Error "k3dge not found. Run ./k3dge-init.ps1"
exit 1
