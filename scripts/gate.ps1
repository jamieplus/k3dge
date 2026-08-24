$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$cmdArgs = if ($args.Count -eq 0) { @("check") } else { $args }
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
