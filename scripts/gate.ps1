$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
# 布局假设校验（与 gate.py:13-15 / gate.sh 同口径）：被复制/软链到别的深度会指错根，
# 政策/收据/venv 全在错根上算，且以"没声明政策"静默放行（ocr2-349）。
if (-not (Test-Path (Join-Path $Root ".agent"))) {
  [Console]::Error.WriteLine("[k3dge] gate.ps1: 推断的仓根 '$Root' 里没有 .agent/ ⇒ 布局假设不成立，拒跑")
  exit 1
}
Set-Location $Root
$cmdArgs = if ($args.Count -eq 0) { @("check") } else { $args }

# K3DGE_SOURCE 统管校验：环境声明的源 vs 本 venv 的装时落盘，不一致即拦。
# 优先级与 gate.sh / gate.py 同：环境 > 本仓 pyproject [tool.k3dge].source；都没有 = legacy。
$srcFile = Join-Path $Root ".venv/k3dge-source.txt"
# 环境值先 Trim（空白-only 视为未声明），与 gate.py 的 `.strip()` 同口径（ocr2-093）。
$want = if ($null -eq $env:K3DGE_SOURCE) { "" } else { "$($env:K3DGE_SOURCE)".Trim() }
if ([string]::IsNullOrWhiteSpace($want) -and (Test-Path (Join-Path $Root "pyproject.toml"))) {
  # 原生命令 + Stop 下 `2>$null` 会抛 NativeCommandError ⇒ 临时降为 Continue（WinPS 5.1），失败按"取不到"处理（ocr-144/147）。
  $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
  # 绝对路径喂子进程：`Set-Location` 改的是 provider location，不保证同步原生进程的 CWD
  # ⇒ 相对 `pyproject.toml` 可能打不开（375）
  try {
    $env:K3DGE_PYPROJECT = (Join-Path $Root "pyproject.toml")
    $want = ((& python3 -c 'import os,tomllib;print(tomllib.load(open(os.environ["K3DGE_PYPROJECT"],"rb")).get("tool",{}).get("k3dge",{}).get("source",""))' 2>$null) | Out-String).Trim()
  }
  catch { $want = "" }
  finally { $ErrorActionPreference = $prev }
  if ([string]::IsNullOrWhiteSpace($want)) {
    $inSec = $false
    $sawSec = $false
    foreach ($ln in (Get-Content -LiteralPath (Join-Path $Root "pyproject.toml"))) {
      if ($ln -match '^\s*\[\s*tool\.k3dge\s*\]\s*(#.*)?$') { $inSec = $true; $sawSec = $true; continue }   # 容忍缩进/表头空白/行尾注释（ocr-144/ocr2-569，与 gate.py 文本回退同口径）
      if ($inSec -and $ln -match '^\s*\[') { break }
      # .NET `-match` 不认 POSIX `[[:space:]]`（会退化成匹配字面 `[`,`:`,`s`,`p`,`a`,`c`,`e`），用 `\s`（ocr2-006）。
      if ($inSec -and ($ln -match '^\s*source\s*=\s*[\x22\x27]([^\x22\x27]*)[\x22\x27]')) {
        $want = $Matches[1]; break                                                   # 两种引号 + 允许缩进
      }
    }
    # 段落存在却没解析到 source ⇒ 政策**声明了但读不懂**，静默按 legacy 跑就是假通过（344/ocr2-094）。
    # 与"收据缺失"同等拒跑，逼调用方修好写法，而不是放行未校验的闸。
    if ($sawSec -and [string]::IsNullOrWhiteSpace($want)) {
      [Console]::Error.WriteLine("[k3dge-source] pyproject 有 [tool.k3dge] 段但没解析出 source ⇒ 拒跑；请检查该行写法")
      exit 2
    }
  }
}

function Resolve-PhysPath([string]$p) {
  # 只对真实目录取物理路径（与 gate.py 的 _norm_path 同口径）；pypi / URL 保持原样。
  if ($p -and (Test-Path -LiteralPath $p -PathType Container)) {
    return (Resolve-Path -LiteralPath $p).Path.TrimEnd('\','/')
  }
  return $p
}

if ($want) {
  if (-not (Test-Path -LiteralPath $srcFile)) {
    # 政策存在而收据缺失 ⇒ 无法证明 venv 来源一致（删收据/手建 venv 都会溜过，ocr-150 家族）。
    [Console]::Error.WriteLine("[k3dge-source] 政策已声明但 .venv/k3dge-source.txt 缺失：无法证明来源一致 ⇒ 拒跑")
    exit 2
  }
  # UTF8 读 + Trim：去 BOM 与首尾空白；比较两侧**同一套**归一化；`-cne` 大小写敏感（源一致性是字面比较）。
  $rec = ((Get-Content -LiteralPath $srcFile -Encoding UTF8 -TotalCount 1) | Out-String).Trim()
  if ([string]::IsNullOrWhiteSpace($rec)) {
    # 空/仅空白/BOM-only 收据 ⇒ 无证据：与"收据缺失"同等拒跑，不能跳过比较静默放行（ocr2-007）。
    [Console]::Error.WriteLine("[k3dge-source] 政策已声明但 .venv/k3dge-source.txt 为空/仅空白：无证据 ⇒ 拒跑")
    exit 2
  }
  $w = Resolve-PhysPath $want
  $r = if ($rec) { Resolve-PhysPath $rec } else { "" }
  if ($r -and ($w -cne $r)) {
    [Console]::Error.WriteLine("[k3dge-source] MISMATCH: want='$w' (env>pyproject) but installed from '$r'. 重装或改政策后再跑闸.")
    exit 2
  }
}

$venvExe = Join-Path $Root ".venv/Scripts/k3dge.exe"
if (Test-Path -LiteralPath $venvExe -PathType Leaf) {
  & $venvExe @cmdArgs        # 与守卫同一路径（不再用相对且无扩展名的调用，ocr-146）
  exit $LASTEXITCODE
}
$k3dge = Get-Command k3dge -ErrorAction SilentlyContinue
if ($k3dge) {
  if ($want) {
    # 收据只覆盖 `.venv`；全局那份来源未经校验。默认**拒跑**（与 gate.py:138-142 / gate.sh:91-94
    # 同口径）——删 .venv 二进制比伪造收据省事，出声回落＝把来源校验变噪音（ocr3）。
    if ($env:K3DGE_ALLOW_GLOBAL -cne "1") {
      [Console]::Error.WriteLine("[k3dge-source] 政策已声明但 .venv/Scripts/k3dge.exe 缺失：全局 k3dge 来源未经校验 ⇒ 拒跑（K3DGE_ALLOW_GLOBAL=1 可强制回落）")
      exit 2
    }
    [Console]::Error.WriteLine("[k3dge-source] WARN: 政策已声明但 .venv/Scripts/k3dge.exe 缺失 ⇒ 回落全局 k3dge（其来源未经收据校验）：$($k3dge.Source)")
  }
  # 走解析到的那一条（`Get-Command` 可能命中 function/alias/.ps1 垫片；裸名 `& k3dge`
  # 会**二次解析**，两次未必同一个 ⇒ 且调用没发生时 $LASTEXITCODE 是上一句的陈旧值）（475）。
  # 非原生命令（function/alias）**不刷新** `$LASTEXITCODE` ⇒ 直接取会拿到前面 `python3` 留下的 0，
  # 把失败的闸报成通过（ocr2-014）。只对 Application 取码，其余用 `$?` 定 0/1。
  $rc = 0
  try {
    & $k3dge.Source @cmdArgs
    if ($k3dge.CommandType -eq "Application") { $rc = $LASTEXITCODE } else { $rc = if ($?) { 0 } else { 1 } }
  }
  catch { [Console]::Error.WriteLine("[k3dge] 无法执行 $($k3dge.Source)：$_"); exit 127 }
  exit $rc
}
[Console]::Error.WriteLine("k3dge not found. Run ./k3dge-init.ps1")
exit 1
