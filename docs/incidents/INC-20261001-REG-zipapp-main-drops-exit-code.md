---
type: REG
severity: P1
status: closed
---

# Incident: `.pyz` 分发件吞掉 `main()` 返回码——下游拿单件当闸时恒绿

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为 (Baseline)**：`dist/k3dge.pyz` 存在的意义＝下游无 venv 也能跑 k3dge 的**闸**
  （README：零依赖单件；M9 票 `2026-09-13-M9-feat-dist_singlefile`）。闸的语义是**退出码**
  （`k3dge check` 红＝非零），pip 安装的 console script 包装器正是 `sys.exit(main())`。
- **现存破损 (Treatment)**：`scripts/build-pyz.sh` 用 `zipapp -m "k3dge.cli.main:main"` 生成
  入口，而 zipapp 的模板是——实测产物内 `__main__.py`：
  ```python
  # -*- coding: utf-8 -*-
  import k3dge.cli.main
  k3dge.cli.main.main()
  ```
  **没有 `sys.exit`**，返回的 int 被丢。同一空目录、同一解释器、同一命令：
  `in-process rc=1` vs `pyz rc=0`。构建器冒烟只跑 `-h`（argparse 自己 SystemExit(0)），
  证明不了返回值到达进程 ⇒ 冒烟恒绿，缺陷穿过了它唯一的防线。
- **复现路径**（修复前）：
  ```bash
  PYTHON=python3 ./scripts/build-pyz.sh
  mkdir -p /tmp/notws && cd /tmp/notws && python3 <仓>/dist/k3dge.pyz check; echo $?  # 0（应为 1）
  ```

## 2. 根因剖析 (5 Whys)

1. 为什么吞码？zipapp `--main` 模板从来不调 sys.exit——这是 zipapp 的**文档化行为**，
   不是编译器 bug；用 `-m` 就等于选了"返回码不进进程"。
2. 为什么冒烟没拦住？冒烟判据（`-h` 退 0）与被验事实（入口能跑）**弱相关**：`--help`
   路径不经过 `main()` 的返回值。和 INC-20261001-AST（子串守卫）同一课：外壳像验证。
3. 为什么测试也没拦住？测试侧自己 inline `zipapp.create_archive(...)` 造了第二套打包路径
   （t-020 的指控），且唯一断言也是 `--help`（t-023②的指控）⇒ 两层都在验"起得来"，没人验"停得对"。
4. 为什么下游一直没炸出来？下游用 pyz 多跑 `init`/`where` 一类便利命令；拿它当**提交闸**
   的回路还没上量——闸类缺陷在低频路径上潜伏。
5. 深层：分发件的入口是**第二个 main 声明**，与仓内 `cli/main.py` 的 `if __name__` 形状
   不同源；两份入口各写各的退出语义。

## 3. 防退化动作清单

- `src/__main__.py`（仓内入口，`sys.exit(main())`）成为唯一入口形状；构建器**缺它拒构**，
  不再传 `-m`（写相代码＝仓内可 lint 的文件，不再是生成模板）。
- 构建器冒烟加第二条：空目录 `check` 必须**非零**（有界：这是构建期就验"停得对"）。
- 测试改驱动真构建器（暂存副本，产物不落仓），断言入口在包内、派生垃圾不入包、
  help 里 `check` 逐行匹配、空目录 `check` 退出非零（t-019..t-023 全部落在这条线上）。
- 顺带（t-020 实测面）：旧产物含 59 条 `__pycache__`；create_archive 加 filter，
  `.DS_Store` 从"拒建"改"过滤"（Finder 随手重建，拒建＝零收益摩擦）。

## 4. 经验灌入

- 冒烟判据必须覆盖**语义的失败面**：对"闸"来说，"能打印"不算数，"红时退出非零"才算。
- 生成式入口（`--main` 模板）＝看不见的代码；入口要成为仓内文件，进 lint、进 review。
