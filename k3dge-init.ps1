$ErrorActionPreference = "Stop"
& "$PSScriptRoot/scripts/init.ps1" @args
exit $LASTEXITCODE   # 把 init.ps1 的退出码传给调用方，失败不得被吞（ocr-134）
