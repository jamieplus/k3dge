$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$cmdArgs = if ($args.Count -eq 0) { @("check") } else { $args }
# K3DGE_SOURCE 统管校验：环境声明的源 vs 本 venv 的装时落盘，不一致即拦。
$srcFile = Join-Path $Root ".venv/k3dge-source.txt"
if ($env:K3DGE_SOURCE -and (Test-Path $srcFile)) {
  $rec = ((Get-Content $srcFile) | Where-Object { $_ -match '^RESOLVED=' } | Select-Object -First 1) -replace '^RESOLVED=', ''
  $rec = ($rec -split ' ')[0]
  $want = $env:K3DGE_SOURCE
  if ($want -ne $rec) {
    Write-Error "[k3dge-source] MISMATCH: K3DGE_SOURCE='$want' but this venv was installed from '$rec'. 重装或 unset 后再跑闸。"
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
