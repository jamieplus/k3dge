#!/usr/bin/env bash
set -euo pipefail
# 支持经 PATH 裸名调用（`$0` 无目录）⇒ 用 command -v 解析出真实路径再取目录（ocr-135）。
SELF="$0"
case "$SELF" in
  */*) ;;
  *) SELF="$(command -v -- "$SELF" 2>/dev/null || printf '%s' "$SELF")" ;;
esac
exec "$(cd "$(dirname "$SELF")" && pwd)/scripts/init.sh" "$@"
