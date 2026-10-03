$ErrorActionPreference = "Stop"
# `$PSScriptRoot` 在"内容被管道/`iex` 执行""从 stdin 读"等场景是**空串** ⇒ 拼出的路径退化成
# 驱动器根下的相对路径，报 FileNotFound 与真实原因无关（363）。
$Here = if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { "" }
if (-not $Here) {
  [Console]::Error.WriteLine("[k3dge] 无法定位本脚本所在目录（管道/iex 调用没有路径）⇒ 请用文件路径运行：powershell -File .\k3dge-init.ps1")
  exit 1
}
$Init = Join-Path $Here "scripts/init.ps1"
if (-not (Test-Path -LiteralPath $Init -PathType Leaf)) {
  [Console]::Error.WriteLine("[k3dge] 找不到 $Init ⇒ 这不是 k3dge 初始化入口所在的项目根（或在别处复制了同名脚本）")
  exit 1
}
# 只验存在不够：同名外来 `init.ps1` 会被静默执行（与 .sh 轨同场景，ocr2-104）。认自家头注释固定串。
if (-not (Get-Content -LiteralPath $Init -TotalCount 5 | Select-String "k3dge-governed project" -Quiet)) {
  [Console]::Error.WriteLine("[k3dge] $Init 不是 k3dge 下发的初始化脚本（缺 k3dge 标记）⇒ 拒跑，请检查是否与自有脚本同名冲突")
  exit 1
}
& $Init @args
exit $LASTEXITCODE   # 把 init.ps1 的退出码传给调用方，失败不得被吞（ocr-134）
