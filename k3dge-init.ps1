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
# init.ps1 没有 param() 块，只有环境变量入口（K3DGE_SOURCE）⇒ 任何位置参数/开关都会落进
# init 的 `$args` 被静默丢弃，调用照样成功（fail-open，ocr-134/ocr3-036）。.sh 轨在 wrapper
# 里拒转发，ps1 轨补同一条。并取回退码：终止错误时 `exit` 不会执行、退出码交宿主，失败可能
# 被报成成功（承袭 `exit $LASTEXITCODE` 的旧坑）⇒ try 包住、catch 报 1，正常路径用 $LASTEXITCODE。
if ($args.Count -gt 0) {
  [Console]::Error.WriteLine("[k3dge] 用法：cd <目标项目>；K3DGE_SOURCE=<源> powershell -File .\\k3dge-init.ps1（不接受位置参数/开关：$args）⇒ 拒跑")
  exit 1
}
try {
  & $Init
  if ($null -ne $LASTEXITCODE) { $rc = [int]$LASTEXITCODE } elseif ($?) { $rc = 0 } else { $rc = 1 }
} catch {
  [Console]::Error.WriteLine("[k3dge] 初始化中断：$_")
  exit 1
}
exit $rc   # 把 init.ps1 的退出码传给调用方，失败不得被吞（ocr-134）
