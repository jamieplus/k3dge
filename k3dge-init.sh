#!/usr/bin/env bash
set -euo pipefail
# 支持经 PATH 裸名调用（`$0` 无目录）⇒ 用 command -v 解析出真实路径再取目录（ocr-135）。
SELF="$0"
case "$SELF" in
  */*) ;;
  *) SELF="$(command -v -- "$SELF" 2>/dev/null || printf '%s' "$SELF")" ;;
esac
HERE="$(cd "$(dirname "$SELF")" && pwd)"
INIT="$HERE/scripts/init.sh"
# 目标必须**是 k3dge 自己的** init.sh：下游仓若已有同名 `scripts/init.sh`，`_write_if_missing`
# 不会覆盖它，而这里会不加判断地执行那个外来脚本（静默跑错东西，364）。
if [ ! -f "$INIT" ]; then
  echo "[k3dge] 找不到 $INIT ⇒ 这里不是 k3dge 初始化入口所在的项目根" >&2
  exit 1
fi
# `grep -q "k3dge"` 太弱：前 5 行里任何顺口一提（含警告散文）都算数（ocr2-105）。
# 认 k3dge 自家头注释里的固定串（下游自有脚本不会有这句）。
if ! head -5 "$INIT" | grep -q "k3dge-governed project"; then
  echo "[k3dge] $INIT 不是 k3dge 下发的初始化脚本（缺 k3dge 标记）⇒ 拒跑，请检查是否与自有脚本同名冲突" >&2
  exit 1
fi
# init.sh 不接受位置参数（TARGET 恒为 pwd，安装源走 K3DGE_SOURCE 环境变量）：
# 旧实现 `exec ... "$@"` 让 `./k3dge-init.sh /path/to/repo` 看起来生效而实际被忽略（365）。
# WARN 后继续 ⇒ 脚手架铺进**错的仓**（fail-open，ocr2-106）。直接拒，不铺。
if [ "$#" -gt 0 ]; then
  echo "[k3dge] 用法：cd <目标项目> && K3DGE_SOURCE=<源> ./k3dge-init.sh（本脚本不接受位置参数：$*）⇒ 拒跑" >&2
  exit 1
fi
exec "$INIT"
