#!/usr/bin/env bash
set -euo pipefail
# 支持经 PATH 裸名调用（`$0` 无目录）⇒ 用 command -v 解析出真实路径再取目录（ocr-135）。
# 裸名不在 PATH 时**拒跑**：旧实现的 `printf '%s' "$SELF"` 会退化到 CWD，可能 exec 别的
# 项目的同名 init.sh（ocr2-378）。
_resolve_dir() {
  # 跟随符号链接求脚本**真实**所在目录（ocr2-378）：`dirname "$SELF"` 只给链接所在目录，
  # `ln -s .../k3dge-init.sh ~/bin` 后会去 `~/bin/scripts/init.sh` 找错地方。
  local target="$1" dir link
  while [ -L "$target" ]; do
    dir="$(cd "$(dirname "$target")" && pwd -P)"
    link="$(readlink "$target")"
    case "$link" in
      /*) target="$link" ;;
      *) target="$dir/$link" ;;
    esac
  done
  cd "$(dirname "$target")" && pwd -P
}
SELF="$0"
case "$SELF" in
  */*) ;;
  *)
    SELF="$(command -v -- "$SELF" 2>/dev/null || true)"
    if [ -z "$SELF" ]; then
      echo "[k3dge] 无法定位本脚本（裸名不在 PATH 上）⇒ 拒跑，请用绝对/相对路径调用" >&2
      exit 1
    fi
    ;;
esac
HERE="$(_resolve_dir "$SELF")"
INIT="$HERE/scripts/init.sh"
# 目标必须**是 k3dge 自己的** init.sh：下游仓若已有同名 `scripts/init.sh`，`_write_if_missing`
# 不会覆盖它，而这里会不加判断地执行那个外来脚本（静默跑错东西，364）。
if [ ! -f "$INIT" ]; then
  echo "[k3dge] 找不到 $INIT ⇒ 这里不是 k3dge 初始化入口所在的项目根" >&2
  exit 1
fi
# `grep -q "k3dge"` 太弱：前 5 行里任何顺口一提（含警告散文）都算数（ocr2-105）。
# 认 k3dge 自家头注释里的固定串（下游自有脚本不会有这句）。
# 不用管道（`head|grep -q` 在 `set -o pipefail` 下会让上游收 SIGPIPE(141)，把真
# k3dge 脚本误判成外来，ocr2-380）：先把头 5 行读进变量，再做字面匹配。
_first5="$(sed -n '1,5p' "$INIT" 2>/dev/null || true)"
case "$_first5" in
  *"k3dge-governed project"*) ;;
  *)
    echo "[k3dge] $INIT 不是 k3dge 下发的初始化脚本（缺 k3dge 标记）⇒ 拒跑，请检查是否与自有脚本同名冲突" >&2
    exit 1
    ;;
esac
# init.sh 不接受位置参数（TARGET 恒为 pwd，安装源走 K3DGE_SOURCE 环境变量）：
# 旧实现 `exec ... "$@"` 让 `./k3dge-init.sh /path/to/repo` 看起来生效而实际被忽略（365）。
# WARN 后继续 ⇒ 脚手架铺进**错的仓**（fail-open，ocr2-106）。直接拒，不铺。
if [ "$#" -gt 0 ]; then
  echo "[k3dge] 用法：cd <目标项目> && K3DGE_SOURCE=<源> ./k3dge-init.sh（本脚本不接受位置参数：$*）⇒ 拒跑" >&2
  exit 1
fi
# 直接用 bash 执行目标：exec 位丢失（Windows checkout/归档/拷贝常丢）或 shebang 坏/C 行尾
# 时，`exec "$INIT"` 只给 bash 的 `Permission denied`/`cannot execute binary file`（126/127），
# 不可诊断（ocr2-379）。先验语法，再用 bash 跑，绕开 exec 位。
if ! bash -n "$INIT" 2>/dev/null; then
  echo "[k3dge] $INIT 语法校验未通过（bash -n）⇒ 拒跑，脚本可能损坏" >&2
  exit 1
fi
exec bash "$INIT"
