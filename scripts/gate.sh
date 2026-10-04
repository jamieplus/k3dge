#!/usr/bin/env bash
set -euo pipefail

# Locate the repo root relative to this script (works from any cwd).
# ROOT 只能由"本脚本在 <root>/scripts/ 下"这一布局假设推出：经符号链接调用、复制到别的
# 深度都会指错，而后续所有路径（政策/收据/venv）都在错根上算（352）。
# `pwd -P` 取**物理**路径；再用 gate.py 这个治理件是否存在来验根，验不过就拒跑。
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [ ! -f "$ROOT/scripts/gate.py" ] || [ ! -d "$ROOT/.agent" ]; then
  echo "[k3dge] gate.sh: 推断的仓根 '$ROOT' 缺 scripts/gate.py 或 .agent/ ⇒ 布局假设不成立，拒跑" >&2
  exit 1
fi
cd "$ROOT"

# Forward all args to k3dge; default to 'check' when none given.
if [ $# -eq 0 ]; then
  set -- check
fi
# 用 `${1+"$@"}` 而不是 `"$@"`：bash <4.4（macOS 自带）在 `set -u` 下把空位置列表的
# `"$@"` 当未定义变量报错，exec 静默死于 126/1（ocr2-355）。

# K3DGE_SOURCE 统管校验：环境声明的源 vs 本 venv 的装时落盘，不一致即拦。
# （装时真相 vs 现行政策，打架必须出声——重装或 unset 再走。）
# 政策读取：K3DGE_SOURCE 环境（显式覆盖，最高）> 本仓 pyproject [tool.k3dge].source（入库政策）；
# 都没有 = legacy（落盘收据即真相，老 venv）。
_WANT="$(printf '%s' "${K3DGE_SOURCE:-}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
if [ -z "$_WANT" ] && [ -f "$ROOT/pyproject.toml" ]; then
  _WANT="$(python3 -c 'import tomllib;print(tomllib.load(open("pyproject.toml","rb")).get("tool",{}).get("k3dge",{}).get("source",""))' 2>/dev/null || true)"
  if [ -z "$_WANT" ]; then
    # 与 gate.py 同口径：允许 tab、单/双引号、行尾注释。表头也容忍空白/行尾注释（ocr2-145）。
    # 1) 不用 `head -1`：`set -o pipefail` 下上游 SIGPIPE（141）会让整段 bootstrap 静默中止（ocr2-145）；
    #    取首个匹配改用参数展开。
    # 2) 不用 GNU BRE 的 `\?` 可选组：BSD/macOS sed 不认 ⇒ 合法 `source = "x"`（无行尾注释）匹配失败，
    #    政策被当"读不懂"而拒跑（ocr2-145）。行尾注释/多余字符由 `.*$` 吸收。
    _WANT="$(sed -n '/^\[[[:space:]]*tool\.k3dge[[:space:]]*\]/,/^\[/p' pyproject.toml 2>/dev/null \
             | sed -n "s/^[[:space:]]*source[[:space:]]*=[[:space:]]*[\"']\([^\"']*\)[\"'].*$/\1/p")"
    _WANT="${_WANT%%$'\n'*}"
    # 段里写了 `source =` 却没解析出值（值非字符串/写法畸形）≠ 没声明政策：拒跑，别静默当 legacy
    # 放行一个未校验的判定核（ocr2-356，与 gate.ps1 同口径）。
    # 单条 awk + END 退出码：不用 `awk | grep -q`（grep 首匹配即关管道 ⇒ awk 收 SIGPIPE 141，
    # `set -o pipefail` 下整段判据静默为假 ⇒ fail-open，ocr3）。
    if [ -z "$_WANT" ] && awk '
        /^\[[[:space:]]*tool\.k3dge[[:space:]]*\]/ {f=1; next}
        /^\[/ {f=0}
        f && /^[[:space:]]*source[[:space:]]*=/ {found=1}
        END {exit(found?0:1)}
      ' pyproject.toml 2>/dev/null; then
      echo "[k3dge-source] pyproject 有 [tool.k3dge].source 但没解析出值 ⇒ 拒跑；请检查该行写法" >&2
      exit 2
    fi
    # `[tool]` 下写 `k3dge = <非表>`（字符串/数组/数字）也是非法政策形状：与 gate.py 同口径拒跑。
    if [ -z "$_WANT" ] && awk '
        /^\[[[:space:]]*tool[[:space:]]*\]/ {f=1; next}
        /^\[/ {f=0}
        f && /^[[:space:]]*k3dge[[:space:]]*=/ && $0 !~ /\{/ {bad=1}
        END {exit(bad?0:1)}
      ' pyproject.toml 2>/dev/null; then
      echo "[k3dge-source] pyproject 的 [tool] 下 k3dge 不是表（非法政策形状）⇒ 拒跑" >&2
      exit 2
    fi
  fi
fi
_SRC_FILE="$ROOT/.venv/k3dge-source.txt"
if [ -n "$_WANT" ]; then
  if [ ! -f "$_SRC_FILE" ]; then
    # 政策存在而收据缺失 ⇒ 无法证明本 venv 来源与政策一致（删收据/手建 venv 都会溜过）——拒跑，不再静默放行。
    echo "[k3dge-source] 政策已声明但 .venv/k3dge-source.txt 缺失：无法证明来源一致 ⇒ 拒跑" >&2
    echo "  重跑 ./k3dge-init.sh 落盘，或 unset K3DGE_SOURCE/改 pyproject 政策。" >&2
    exit 2
  fi
  # `read` 在"末行无换行"时返回非零但仍已赋值；`|| _REC=""` 会把有效收据清空（ocr2-098）。
  # 只压住 `set -e`，保留读到的值；空文件则 _REC 为空，下一步拒跑。
  IFS= read -r _REC < "$_SRC_FILE" || :
  _REC="${_REC#$'\xef\xbb\xbf'}"                    # 去 BOM（旧 init.ps1 写的 BOM 会让比较恒不等）
  _REC="${_REC%$'\r'}"                              # 只去行尾 CR（`tr -d ' \t'` 会吞路径里的空格，ocr-156）
  _REC="$(printf '%s' "$_REC" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  if [ -z "$_REC" ]; then
    # 空/仅空白/BOM-only 收据 ⇒ 无证据：与"收据缺失"同等拒跑，不能跳过比较静默放行（ocr2-016/099）。
    echo "[k3dge-source] 政策已声明但 .venv/k3dge-source.txt 为空/仅空白：无证据 ⇒ 拒跑" >&2
    exit 2
  fi
  # 只对真实目录取物理路径；pypi/URL 保持原样。用显式 if：`[ -d ] && X="$(cd … && pwd -P)"` 在
  # `-d` 成立而 `cd` 失败（权限/被并发替换/NFS 卡）时，命中的是最后一条命令，`set -e` 会无消息中止（ocr2-147）。
  if [ -d "$_WANT" ]; then
    _WANT="$(cd "$_WANT" && pwd -P)" || { echo "[k3dge-source] 无法进入声明的源目录：$_WANT" >&2; exit 2; }
  fi
  if [ -d "$_REC" ]; then
    _REC="$(cd "$_REC" && pwd -P)" || { echo "[k3dge-source] 无法进入收据记录的源目录：$_REC" >&2; exit 2; }
  fi
  if [ "$_WANT" != "$_REC" ]; then
    echo "[k3dge-source] MISMATCH: want='$_WANT'（env>pyproject） but installed from '$_REC'." >&2
    echo "  重装或改政策后再跑闸。" >&2
    exit 2
  fi
fi

# Prefer the project-local venv so no manual activation is required.
if [ -x "$ROOT/.venv/bin/k3dge" ]; then
  exec "$ROOT/.venv/bin/k3dge" ${1+"$@"}
fi

# Fall back to a globally installed k3dge (pipx / pip)：收据只覆盖 `.venv`，全局那份来源不受政策约束
# ⇒ 政策存在时至少出声（别让人以为跑的是刚校验过的那个二进制，ocr-158）。
if command -v k3dge >/dev/null 2>&1; then
  # 政策已声明却没有 .venv 判定核：全局 k3dge 来源未经收据校验 ⇒ 默认拒跑（与相邻分支
  # 的 fail-closed 同口径，ocr2-357）；K3DGE_ALLOW_GLOBAL=1 保留便利回落。
  if [ -n "$_WANT" ] && [ "${K3DGE_ALLOW_GLOBAL:-}" != "1" ]; then
    echo "[k3dge-source] 政策已声明但 .venv/bin/k3dge 缺失：全局 k3dge 来源未经校验 ⇒ 拒跑（K3DGE_ALLOW_GLOBAL=1 可强制回落）" >&2
    exit 2
  fi
  if [ -n "$_WANT" ]; then
    echo "[k3dge-source] WARN: 政策已声明但 .venv/bin/k3dge 缺失 ⇒ 回落全局 k3dge（其来源未经收据校验）：$(command -v k3dge)" >&2
  fi
  exec k3dge ${1+"$@"}
fi

echo "k3dge not found. Run the one-time init first:" >&2
echo "  ./k3dge-init.sh" >&2
echo "See README.md for details." >&2
exit 1
