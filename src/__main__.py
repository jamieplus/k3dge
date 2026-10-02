"""zipapp 入口：`src/__main__.py` 必须在仓（build-pyz.sh 缺它即拒构）。

为何不走 zipapp 的 `--main`：它生成的模板是 `import mod; mod.main()`，**不 `sys.exit`**
⇒ `main()` 返回的 int 被吞 ⇒ 下游 `k3dge.pyz check` 恒 0 退出＝分发件把闸读成常绿
（t-023 实测：同一空目录下 in-process rc=1、`.pyz` rc=0）。

本文件在 `src/` 顶层、不在 `k3dge` 包内：wheel 不收（hatch `packages=["src/k3dge"]`），
pytest 也不会把它当测试模块收集；只有 zipapp 打包与解释器脚本入口用它。
"""
import sys

from k3dge.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
