# Rule 12: Introduction Discipline

> Protocol slice for tools that look under `.agent/rules/` (ADR-0010).
> Live agent protocol is repo-root `AGENTS.md`. If this file disagrees, `AGENTS.md` wins; fix this file in the same task.
> This file is the procedure (not duplicated in AGENTS.md). AGENTS.md §12 points here when a new mechanism is proposed.

Read when proposing any new mechanism: module, registry, declaration file, command,
or abstraction layer. Counterpart of Rule 02 (which removes); this one gates what gets built.

## 1. The policy (one rule, two clauses)

1. **方案必须完整，且必须有实测正向作用。**
2. **不单独扩基建** —— 扩基建的前提是已满足第 1 条。

第 2 条是第 1 条的推论：基建不是目标，是手段。手段只在它所服务的方案成立时才允许存在。

## 2. 什么算「实测正向作用」

必须是**可复跑的命令 + 输出**，证明危害此刻真实存在。

| 算 | 不算 |
|---|---|
| 运行时复现的 bug（E39：首次封板被拒） | 推论（"应该会更省"） |
| 真实仓里的实例（k3dit/k3che 各 4 处悬空引用） | 类比（"别的工具都这么做"） |
| 改前/改后的对照测量 | 审美（"更优雅"、"分形之美"） |
| 静默失效的功能（E44：从不被调用） | 频率推测（"以后会常遇到"） |

「完整」＝端到端解决那个已实测的危害，不需要再补一次改动才生效。

## 3. 扩基建前的三个筛子（按序问，任一不过即不扩）

1. **现有机制能否完整解决？**
   实例：E39 的完整解＝把一个条目移个通道；E43＝一个校验器。两者都不需要新注册表。
2. **接入点是活的吗？**
   实例：`grep 'k3dge commit' AGENTS.md .agent/rules/*.md` → 零命中
   ⇒ 编排器即使做出来也接到没人用的插座上。
3. **危害实例可复跑吗？**
   拿不出「命令 + 输出」⇒ 那是设想，不是问题。

## 4. 本仓的反例集（都被上面筛掉，勿重提）

| 提案 | 死在哪 |
|---|---|
| `FIXERS` 注册表 + 编排器 | 筛子 1（E39/E43 的完整解不需要它）+ 筛子 2（接入点空） |
| 判定式统一形状（bool / `(code,msg)` / `Violation` 三合一） | 第 2 节：三种返回形状各服务其消费者，无有害实例 |
| ② 载体边界检查 | 第 2 节：找不到缺载体的实例 ⇒ 建出来永不红（空转） |
| 大编排器（Step/Flow/Pipeline） | 筛子 1 + 归属未明（见 memo S6：agent 工作流不可被编排） |

## 5. Checklist

- [ ] 能写出可复跑命令证明危害存在（贴进 task 的证据链段）
- [ ] 已确认现有机制不能完整解决（写出**为什么不能**）
- [ ] 接入点被使用或被声明（grep 出至少一处消费者）
- [ ] 若仍要扩基建：它服务的方案已满足第 1 条
- [ ] task 里显式列出**筛掉的替代方案**及理由（防下轮重提）

## 6. 机检状态：prose-only（有意留）

本规则的判据是「决策质量」，不是文件事实，无法做成闸。

曾试过把筛子 2 做成机检（「每个子命令必须在 AGENTS.md/rules/guides 有到达路径」）：
实测 20 个子命令中 13 个未被提及（65% 误报），不可用。
登记于 `docs/reviews/LEFTOVERS.md`。
