"""闸红文案与档位的**单一声明面**（B 线：自动 → 自主）。

零依赖（stdlib only）：`scripts/pre-commit` 与 engine 都要能加载，口径同
`pure_schema` / `pure_refs`（工具坏不得阻断所有提交）。

内容/流程解耦（用户裁定 2026-09-19；ADR-0026 §2.2/§2.3）：

    检查器   只产 (code, 结构化事实)      —— 不知道文案，不拼串
    本表     code → severity/fact/options/pointers —— 不知道检查器内部，只吃事实的键名
    渲染器   一份实现，两个投影：
             给进程     → `projection()`  闭集 dict（code + severity + 事实），可机械分支
             给判断主体 → `render()`      陈述式 fact + 成对 options + pointers

形态不变量（与 `nextstep.TestProjectionInvariants` 同口径，由 test_gate_facts 守）：
  1. `fact` / `options` 不得是疑问句——纯打印面无应答通道，且疑问句会把预设嵌进句式，
     变成带主观偏见的引导性话术（ADR-0026 §2.2 语法维）。
  2. `severity=block` 的 code 必须给 ≥2 个 options（只给一条路＝下令，不是给判断主体）。
  3. 档位是**声明**，不是代码分支：`block|warn|observe` 只在这里定义，
     消费者（hook / CLI / MCP）一律查表，不得自己写"WARN-only"这类散文档位。

未声明的 code 走 `DEFAULT_SEVERITY` 且由调用方自己的 message 兜底——**迁移是增量的**，
不要求一次把全部 code 搬进表（搬一个就少一处手拼串）。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

#: 档位闭集（唯一源）。block=拦提交/红闸；warn=显示但不拦；observe=观测建议，不判定。
SEVERITIES: tuple = ("block", "warn", "observe")
#: 档位 → 横幅标签。**消费者查这张表**，不得自己复制字面量字典（435）。
SEVERITY_TAGS = {"block": "GATE ERROR", "warn": "GATE WARN", "observe": "GATE NOTE"}


def severity_tag(severity: str) -> str:
    return SEVERITY_TAGS.get(severity, "GATE NOTE")
DEFAULT_SEVERITY = "block"

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


class _SafeFacts(dict):
    """缺失键原样留 `{key}`，不抛——文案模板不得因为少一个事实字段就崩掉渲染。"""

    def __missing__(self, key):  # noqa: D105
        return "{" + key + "}"


#: code → 声明。`fact`/`options`/`pointers` 支持 `{key}` 占位，由检查器给的 `facts` 填。
GATE_FACTS: Dict[str, Dict[str, Any]] = {
    # --- block：拦下并要求判断主体选一条路 ---
    "CONTRACT_DRIFT": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "k3dge sync（回写契约哈希 + 重生 docs/generated）",
        "fact": "公有接口变了，spec 的契约哈希没跟上（spec={expected_hash} ≠ code={actual_hash}）；"
                "哈希由 `k3dge sync` 回写，不手写",
        "options": [
            "k3dge sync（回写契约哈希 + 重生 docs/generated）",
            "接口本不该变 → 回退代码改动，再跑 k3dge check",
        ],
        "pointers": ["AGENTS.md Core Invariants 2", "k3dge sync"],
    },
    "DOC_INDEX_STALE": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "k3dge sync（重生 docs/generated/docs-index.json）",
        "fact": "`docs/generated/docs-index.json` 与重建结果不一致（{reason}）——它是**投影**，"
                "由 `k3dge sync` 重生，不手改",
        "options": [
            "k3dge sync（重生 docs-index + 回写契约哈希）",
            "索引本不该变 → 回退本轮 docs 改动，再跑 k3dge check",
        ],
        "pointers": ["k3dge sync", "docs/generated/", "AGENTS.md §12"],
    },
    "ARCH_STATE_DOC_DRIFT": {
        "severity": "block", "fix": "judgment",
        "fact": "`{path}` 没列全状态闭集（缺 `{missing}`）——`[NEXT]` 态与 task 态的**唯一源在代码**"
                "（`engine/nextstep.STATE_OPTIONS` / `engine/state_machine.py`），文档缺项会让新状态"
                "在架构总览里不存在",
        "options": ["在 `overview.md` §6.2/§6.3 的表里补上缺的态（反引号写标识符）",
                    "状态刚改名 → 同步改文档表；确属新增实验态 → 仍要写进表（闭集是给人看的）"],
        "pointers": ["docs/architecture/overview.md §6", "engine/nextstep.py", "engine/state_machine.py"],
    },
    "EXTRACTOR_PLUGIN_STALE": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "k3dge extractor sync（按 .agent/extractors.toml 重生 .agent/extractors/*.py）",
        "fact": "抽取器插件与配置不一致（{languages}）——插件是配置的**渲染物**，改了配置没 sync 就会"
                "用旧规则抽接口（契约哈希随之失真）",
        "options": ["k3dge extractor sync（重生插件）",
                    "配置本不该变 → 回退 .agent/extractors.toml 的改动"],
        "pointers": [".agent/extractors.toml", "k3dge extractor sync", "docs/specs/sync/spec.md"],
    },
    "DOCS_TOML_KEY_UNKNOWN": {
        "severity": "warn", "fix": "judgment",
        "fact": "`.agent/docs.toml` 的 `{key} = true` 没有落点——键表由 `scripts/generate-docs.sh` 的 `gen` 行持有，"
                "写下脚本不认识的键（或目标文件尚未生成）只会静默落空",
        "options": ["收尾时跑 `./scripts/generate-docs.sh`（按配置生成桩）",
                    "键写错了 → 改成脚本支持的键（见该脚本的 gen 行）"],
        "pointers": [".agent/docs.toml", "scripts/generate-docs.sh"],
    },
    "ARCH_TABLE_DRIFT": {
        "severity": "block", "fix": "judgment",
        "fact": "`{path}` 的域表与 `.agent/manifest.json` 不一致（`{domain}` 的 `{col}`）——表行是事实投影"
                "（域/源码/spec/tests/depends_on），描述列是散文不在本闸判据内。**方向要人判**：是文档过时，"
                "还是 manifest 改了没同步",
        "options": ["文档过时 → 按 manifest 改表行（或重跑 k3dge sync 后对照 docs/generated/domains.md）",
                    "manifest 才是错的 → 先改 manifest，再同步两张表与两张 Reference 表"],
        "pointers": ["docs/architecture/overview.md §1", "docs/architecture/encyclopedia.md §2",
                     ".agent/manifest.json", "k3dge sync"],
    },
    "SYMBOL_INDEX_STALE": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "k3dge index（重生 docs/generated/symbol-index.json）",
        "fact": "`docs/generated/symbol-index.json` 与重建结果不一致（{reason}）——它是 `k3dge where` "
                "的判据面，旧了会静默给出错的 file:line；投影不手改",
        "options": ["k3dge index（重生符号索引）", "索引本不该变 → 回退本轮 src/ 改动"],
        "pointers": ["k3dge index", "k3dge where", "docs/generated/"],
    },
    "DOCS_GENERATED_STALE": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "k3dge sync（重生 docs/generated/ 下的 api.md 与 domains.md）",
        "fact": "`{path}` 与 `k3dge sync` 的重建结果不一致（{reason}）——它是**投影**（api.md↔代码接口、"
                "domains.md↔manifest），不手改",
        "options": ["k3dge sync（重生 docs/generated/ 下的派生文档）", "内容本不该变 → 回退本轮改动"],
        "pointers": ["k3dge sync", "docs/generated/", "AGENTS.md §12"],
    },
    "MCP_JSON_PEER_MISSING": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "k3dge mcp sync（把声明 enabled 的 peer 合入 `.mcp.json`）",
        "fact": "`.mcp.json` 与 `.agent/pipeline.toml` 的 peer 声明不一致（peer={peer}）——外部 harness "
                "拿不到该工具面，而声明面说它可用",
        "options": ["k3dge mcp sync（合入缺的 peer / k3dge 自身条目）",
                    "peer 不该启用 → 在 pipeline.toml 里改 enabled"],
        "pointers": [".mcp.json", ".agent/pipeline.toml", "k3dge mcp sync"],
    },
    "CONTRACT_HASH_MISSING": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "k3dge sync（写入契约哈希）",
        "fact": "`{spec}` 没有 Contract Hash 行（域 {domain}）——契约哈希由 `k3dge sync` 写入，不手写",
        "options": [
            "k3dge sync（写入/回写契约哈希）",
            "该域本不该有契约 → 核对 .agent/manifest.json 的域声明与 spec 路径",
        ],
        "pointers": ["AGENTS.md Core Invariants 2", "k3dge sync", ".agent/manifest.json"],
    },
    "VERSION_MISMATCH": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "k3dge version bump（以 pyproject 为权威同步三处）",
        "fact": "版本号在三处各存一份、必须同值（pyproject.toml / .agent/manifest.json / "
                "src/k3dge/__init__.py）：{drift}。三处逐个写、非原子事务，半漂移由本闸暴露"
                "（有意留 BV-01，不引入跨文件原子）",
        "options": [
            "k3dge version bump（以 pyproject 为权威同步三处）",
            "本轮不该提版 → 把三处改回同值，再跑 k3dge check",
        ],
        "pointers": ["k3dge version show", "docs/reviews/LEFTOVERS.md（BV-01）"],
    },
    "TEMPLATE_DRIFT": {
        "fix": "judgment",
        "severity": "block",
        "fact": "字节锁两侧不一致：`{asset}` ≠ `{repo}`（PAIRS 见 engine/pairs.py）。"
                "**方向要靠意图判**：本仓改协议面 ⇒ 仓→资产；升级下游 ⇒ 资产→仓。"
                "进程不知道意图，故此码**不属确定性可修**",
        "options": [
            "本轮改的是仓内协议面 → 把仓内文件同步进 src/k3dge/templates/assets/",
            "本轮改的是模板资产 → 把资产同步进仓内文件",
            "两侧都该改 → 改完再跑 k3dge check",
        ],
        "pointers": ["src/k3dge/engine/pairs.py", "docs/guides/downstream.md"],
    },
    "DOC_NEW_UNSCREENED": {
        "fix": "judgment",
        "severity": "block",
        "fact": "新建受管文档 `{path}`（主观撰写类）未经重复/覆盖排查——首次提交拦一次，回执后不再提示。"
                "值不值得建由你判（进程判不了语义覆盖与子项关系），本闸只负责把排查送到动手这一刻",
        "options": [
            "并入既存 → 目标文档收编本节、删掉本文件、写并入说明，再 k3dge sync",
            "确认新建 → k3dge doc screen {path}",
            "指明并入目标 → k3dge doc screen {path} --into docs/<type>/<target>.md",
        ],
        "pointers": ["AGENTS.md §12", "docs/adr/AUTHORING.md「先并入，后新建」", "k3dge doc list --type <type>"],
    },
    "ARCHIVE_NO_DEST": {
        "fix": "judgment", "severity": "warn",
        "fact": "`{path}` 进了 `archive/` 但没写去向标记——归档是有意动作，「为什么归档」应留在文件里（ADR-0023 §2.2）",
        "options": ["补 `Superseded-by: <新文档>` 或 `Legacy note: <一句话>`",
                    "确属有意留（纯降权留档）→ 不处理，本条只观测不拦"],
        "pointers": ["docs/adr/0023-low-authority-archive-tier.md", "docs/*/AUTHORING.md"],
    },
    "INCIDENT_ID_REDUNDANT": {
        "fix": "deterministic", "fix_hint": "删掉 frontmatter 的 `id:` 行（身份唯一源＝文件名）",
        "severity": "block",
        "fact": "`{path}` 的 frontmatter 有 `id`，它是文件名的副本——没有任何消费者读它"
                "（卡片 id 取 `path.stem`，schema 也无 id 规则）⇒ 只能漂移",
        "options": ["删掉 `id:` 行（身份走文件名）", "文件名本身该改 → `git mv` 改名，别只改 id"],
        "pointers": ["docs/incidents/AUTHORING.md", "docs/incidents/README.md"],
    },
    # --- ADR 编号退役账本（obsolete/README.md 的表是唯一源）---
    "ADR_NUMBER_HOLE": {
        "fix": "judgment", "severity": "block",
        "fact": "`{path}` 所在号池有空洞——1 到最大号之间有的号既不是现役 ADR，也没有退役墓碑。"
                "下一号只能是 max(本仓 adr ∪ obsolete ∪ 账本)+1，不能跳去别的仓的号",
        "options": ["把跳号文件改成下一个空号（本仓 max+1），并改 H1 与全部引用",
                    "空洞是删掉的旧 ADR → 补 obsolete 墓碑或退役账本行，不要留一个没解释的号"],
        "pointers": ["docs/adr/AUTHORING.md「编号分配」", "docs/adr/obsolete/README.md"],
    },
    "ADR_NUMBER_REUSE": {
        "fix": "judgment", "severity": "block",
        "fact": "`{path}` 占了一个**已永久退役**的 ADR 号——`Numbers are never reused`："
                "号一次分配即永久绑定那一个决策，退役号不得再发出（否则旧引用静默指错）",
        "options": ["改用下一个安全号 = max(docs/adr ∪ obsolete ∪ 账本表)+1，并同步 H1 与 README Topics",
                    "这不是新决策 → 按「先并入，后新建」并入既存 ADR（写 Amended-by，不新开号）"],
        "pointers": ["docs/adr/obsolete/README.md（退役账本）", "docs/adr/AUTHORING.md「编号分配」"],
    },
    "ADR_RETIRED_NO_DEST": {
        "fix": "judgment", "severity": "block",
        "fact": "`{path}` 已移入 `obsolete/` 但没写去向——**合并没有自动化**（`reconcile_supersedes` "
                "只管 `Supersedes:` 与 `Rejected`），忘写就会变成「retired 但不知去哪」",
        "options": ["补 `merged-into: ADR-XXXX §Y`（并入宿主 ADR 时）",
                    "补 `superseded_by: ADR-XXXX`（被取代时）",
                    "该 ADR 是被否决的提议 → 写 `Status: Rejected`（从未生效即其去向）"],
        "pointers": ["docs/adr/obsolete/README.md（归档约定）", "docs/adr/AUTHORING.md「编号分配/删除/改名」"],
    },
    "ADR_REF_RETIRED": {
        "fix": "judgment", "severity": "block",
        "fact": "`{path}` 引用了已退役的 ADR 号——那条决策已被合并/改名，引用会静默指错对象",
        "options": ["改指去向（账本表里记了 merged-into / superseded-by 的小节）",
                    "确属历史陈述 → 去掉 `ADR-` 前缀写成事件（如「原 0020 harness 职责划分」）"],
        "pointers": ["docs/adr/obsolete/README.md（退役账本）", "k3dge doc list --type adr"],
    },
    # --- ADR amend/footnote 形态（pure_schema.check_amend，2026-09-24）---
    "ADR_AMEND_ORDER": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "`k3dge doc fix`：补 `🅰N |` 前缀 + 按 **append 序（升序）** 重排 Amended-by",
        "fact": "`{path}` 的 `Amended-by` 前缀缺失/号重复/非升序——纯格式，进程按固定规则修",
        "options": ["`k3dge doc fix` 自动修（幂等）", "确需非常规顺序 → 改 AUTHORING/schema（改声明，不改闸）"],
        "pointers": ["docs/adr/AUTHORING.md", "k3dge doc fix"],
    },
    "ADR_FOOTNOTE_TAIL": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "`k3dge doc fix`：把 `[^🅰…]:` 定义块整体移到文末",
        "fact": "`{path}` 的 ADR 脚注定义穿插在正文中——纯排版，进程可修",
        "options": ["`k3dge doc fix` 自动修", "定义该留在正文 → 改 AUTHORING（改声明，不改闸）"],
        "pointers": ["docs/adr/AUTHORING.md"],
    },
    "ADR_AMEND_MARKER_TEXT": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "`k3dge doc fix`：`（🅰N，…）` → 该 N 的唯一脚注引用",
        "fact": "`{path}` 正文用了带文字的括号标记，而不是脚注引用——固定写法，进程可修",
        "options": ["`k3dge doc fix` 自动修", "N 有多个脚注定义（歧义）→ 人/席指定用哪条"],
        "pointers": ["docs/adr/AUTHORING.md"],
    },
    "ADR_AMEND_REF": {
        "severity": "block", "fix": "judgment",
        "fix_hint": "在正文描述该改动的那句话尾补 `[^🅰N.M]`（位置需要读懂语义）",
        "fact": "`{path}` 的某条修订在正文没有任何引用——读者顺号找不到落点",
        "options": ["补引用（人/席判断落点）", "该修订不该留痕 → 从 Amended-by 删掉并说明"],
        "pointers": ["docs/adr/AUTHORING.md"],
    },
    "ADR_FOOTNOTE_ORPHAN": {
        "severity": "block", "fix": "judgment",
        "fix_hint": "定义了却没引用 ⇒ 删定义或补引用；引用了却没定义 ⇒ 补定义",
        "fact": "`{path}` 的脚注引用与定义不闭合（双向）",
        "options": ["补齐闭合（人/席）", "确属历史残留 → 删除该定义"],
        "pointers": ["docs/adr/AUTHORING.md"],
    },
    "ADR_FOOTNOTE_LINE": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "`k3dge doc fix`：把脚注定义的续行并回同一行",
        "fact": "`{path}` 的修订脚注定义折了行——Markdown 在换行处结束脚注，后文掉进正文",
        "options": ["`k3dge doc fix` 自动修（幂等）", "这行不是脚注续文 → 改到定义之外并空行隔开"],
        "pointers": ["docs/adr/AUTHORING.md「内联修订标记」", "k3dge doc fix"],
    },
    "ADR_FOOTNOTE_SEQ": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "`k3dge doc fix`：小标号按正文出现序改成 1..k",
        "fact": "`{path}` 的修订脚注小标号不从 1 连续（跳号，或用了条款号当小标号）",
        "options": ["`k3dge doc fix` 自动修（幂等；只改本文件的引用与定义）", "小标号有意指向别的编号体系 → 改 AUTHORING（改声明，不改闸）"],
        "pointers": ["docs/adr/AUTHORING.md「内联修订标记」", "k3dge doc fix"],
    },
    "ADR_AMEND_SPLIT": {
        "severity": "block", "fix": "judgment",
        "fix_hint": "同一个节被多条 Amended-by 各写一遍时，并成一个修订号，落点用 🅰N.1、🅰N.2",
        "fact": "`{path}` 把同一个节拆成了多条修订——一条修订是一个主题，不是一次补写",
        "options": ["并成一个 Amended-by 号；各处落点用从 1 连续的小标号，定义各占一行",
                    "后一次是另一个不变量 → 另开号，但不要再让好几条都只写同一个节"],
        "pointers": ["docs/adr/AUTHORING.md「内联修订标记」"],
    },
    "ADR_AMEND_DRAFT": {
        "severity": "block", "fix": "judgment",
        "fix_hint": "Draft/Proposed 把决定写进正文，`Amended-by: -`，删掉修订脚注；规范只在脚注里的，先收进正文",
        "fact": "`{path}` 还没 Accepted 就记了修订留痕——起草过程不是修订，一个主题不该拆成多个号",
        "options": ["规范收进正文后删 `Amended-by` 列表和脚注", "决策已经 Accepted → 把 Status 改为 Accepted（须先有 Landed-by）"],
        "pointers": ["docs/adr/AUTHORING.md「内联修订标记」"],
    },
    # --- markdown 完整性（pure_refs B3）---
    "MD_TRAILING_WS": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "删掉行尾空白（幂等，无需判断）",
        "fact": "`{path}` 有行尾空白——纯格式偏差，进程可按固定规则修",
        "options": ["删掉行尾空白后重新提交", "该文件不该进受管面 → 在 .schema.json/排查面里声明排除（改声明，不改闸）"],
        "pointers": ["docs/*/AUTHORING.md", "scripts/pre-commit"],
    },
    "MD_CRLF": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "CRLF → LF（幂等）",
        "fact": "`{path}` 用了 CRLF 行尾——纯格式偏差，进程可按固定规则修",
        "options": ["转成 LF 后重新提交", "确需 CRLF → 在 .gitattributes 声明（改声明，不改闸）"],
        "pointers": ["scripts/pre-commit"],
    },
    "MD_NO_FINAL_NEWLINE": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "文件末尾补一个换行（幂等）",
        "fact": "`{path}` 末尾缺换行——纯格式偏差，进程可按固定规则修",
        "options": ["补末尾换行后重新提交", "该文件是二进制/生成物 → 声明排除"],
        "pointers": ["scripts/pre-commit"],
    },
    "MD_FENCE_UNCLOSED": {
        "severity": "block", "fix": "judgment",
        "fact": "`{path}` 有未闭合的代码围栏（``` 或 ~~~ 数量为奇数）——补在哪、围哪段要读懂内容",
        "options": ["补上缺失的围栏（确认围住的是哪一段）", "删掉多余的围栏（若本不该有代码块）"],
        "pointers": ["docs/*/AUTHORING.md"],
    },
    "MD_CONFLICT_MARKER": {
        "severity": "block", "fix": "judgment",
        "fact": "`{path}` 里留着 git 冲突标记（<<<<<<< / >>>>>>>）——合并结果必须由人判",
        "options": ["解冲突：保留正确一侧并删标记", "放弃本次合并（git merge --abort）后重来"],
        "pointers": ["docs/branches/AUTHORING.md"],
    },
    "MD_ENCODING": {
        # 分类修正（2026-09-19）：曾标 deterministic，但**源编码判断不了**——猜错会损坏文件
        # （latin-1 解码永不失败，重编码成 UTF-8 会把非 ASCII 字节改义）⇒ 属判断类
        "severity": "block", "fix": "judgment",
        "fact": "`{path}` 不是合法 UTF-8——受管文档一律 UTF-8",
        "options": ["转成 UTF-8 后重新提交", "该文件不该是文本 → 移出 docs/ 或声明排除"],
        "pointers": ["scripts/pre-commit"],
    },
    # --- 票据一致性（pure_refs B2）---
    "TASK_BODY_META_REDUNDANT": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "删掉正文里复写 frontmatter 的元数据行（frontmatter 是唯一源）",
        "fact": "`{path}` 的正文复写了 frontmatter 已有的任务元数据——第二源只能漂移",
        "options": ["删掉正文的 `- **Status|Milestone|Priority|Date|Report**:` 行", "该字段确实只该在正文 → 改 docs/tasks/.schema.json 与 AUTHORING（改声明，不双写）"],
        "pointers": ["docs/tasks/AUTHORING.md"],
    },
    "TASK_CLOSURE_MISSING": {
        "fix": "judgment", "severity": "block",
        "fact": "`{path}` 已翻 done 但没有结案记录——票是自包含事实源，不留落地痕迹，"
                "后续就会出现「票里说待办、实际已做」的漂移",
        "options": ["补一个结案类段并写清落地情况（`## 结案` / `## 落地` / `## 关闭理由` / `## 收尾` / `## 回填` / `## 进度`）",
                    "票其实没做完 → 把 frontmatter status 改回 in-progress 并去掉 .done 后缀"],
        "pointers": ["docs/tasks/AUTHORING.md", "k3dge ADR-0012"],
    },
    "TASK_STATUS_MISMATCH": {
        "severity": "block", "fix": "judgment",
        "fact": "`{path}` 的 frontmatter `status` 与文件名 `.done.md` 后缀不一致——哪边是真的要人判",
        "options": ["票确实做完了 → `k3dge task done <path>`（它同时改名，别手改）", "票没做完 → 把 frontmatter status 改回 idea/in-progress 并去掉 .done 后缀"],
        "pointers": ["docs/tasks/AUTHORING.md", "k3dge task done"],
    },
    "TASK_MILESTONE_MISMATCH": {
        "severity": "block", "fix": "judgment",
        "fact": "`{path}` 的 frontmatter `milestone` 与文件名里的里程碑号不一致",
        "options": ["改 frontmatter 对齐文件名（文件名是归档/扫描的依据）", "改里程碑归属 → 连文件名一起改（`git mv`），别只改一边"],
        "pointers": ["docs/tasks/AUTHORING.md", "k3dge milestone status <id>"],
    },
    # --- ADR 一致性（pure_refs B2 / B1）---
    "ADR_NUMBER_MISMATCH": {
        "severity": "block", "fix": "judgment",
        "fact": "`{path}` 的文件名号与正文 H1/引用号不一致。**不得机械改号**：文档会老化，"
                "机械改会把对的一侧改错——要先判哪边是真号，并同步 README 索引与全部引用点",
        "options": ["以文件名为准 → 改 H1 与文内自引，并核对 README Topics", "以 H1 为准 → `git mv` 改文件名，并全仓改引用（`k3dge doc grep ADR-<号>`）"],
        "pointers": ["docs/adr/AUTHORING.md", "docs/adr/README.md", "k3dge doc grep"],
    },
    "ADR_SUPERSEDE_UNRECONCILED": {
        "severity": "block", "fix": "deterministic",
        "fix_hint": "k3dge sync（`adr_gate.reconcile_supersedes` 自动标记旧 ADR 并移入 obsolete/）",
        "fact": "`{path}` 声明了 Supersedes 但旧 ADR 未被标记/归档——这一步是机械的，由 sync 完成",
        "options": ["k3dge sync（自动 reconcile：改 frontmatter + 移入 obsolete/）", "Supersedes 写错了 → 改指向真正被取代的那条"],
        "pointers": ["docs/adr/AUTHORING.md「obsolete/ 归档闸」", "k3dge sync"],
    },
    "DANGLING_ADR_REF": {
        "severity": "block", "fix": "judgment",
        "fact": "`{path}` 引用了一个在 docs/adr/（含 obsolete/）找不到的 ADR 号——要么号写错，"
                "要么那条 ADR 已被物理删除（历史退役号见 obsolete/README.md）",
        "options": ["改成正确的 ADR 号（`k3dge doc list --type adr` 查现役）", "该决策已并入别条 → 改指宿主 ADR 与其小节", "确属历史陈述 → 去掉 `ADR-` 前缀写成事件描述（如「原 0020」）"],
        "pointers": ["k3dge doc list --type adr", "docs/adr/README.md"],
    },
    "DANGLING_REPORT_REF": {
        "severity": "block", "fix": "judgment",
        "fact": "`{path}` 的 `report:` 指针指向不存在的文件——票与报告的绑定断了",
        "options": ["补上报告（`k3dge milestone audit-submit <id>`）", "改指真正对应的那份报告", "这张票不该绑报告 → 删掉 frontmatter 的 report 字段"],
        "pointers": ["docs/reviews/", "k3dge ADR-0022"],
    },
    "DANGLING_FOOTNOTE": {
        "severity": "block", "fix": "judgment",
        "fact": "`{path}` 有 `[^X]` 引用但没有对应定义（行内 code span 里的字面量已排除）",
        "options": ["补上 `[^X]:` 定义（Amended-by 的内联修订标记见 docs/adr/AUTHORING.md）", "删掉这个引用（若本不需要脚注）"],
        "pointers": ["docs/adr/AUTHORING.md「内联修订标记」"],
    },
    # --- 结构（pure_schema）---
    "DOC_SCHEMA_INVALID": {
        "severity": "block", "fix": "judgment",
        "fact": "`{path}` 不符合该类型的 `.schema.json`（frontmatter/章节/文件名/索引）——"
                "缺的通常是**要写的内容**，不是格式，故不自动修",
        "options": ["按 docs/<type>/_template.md 与 AUTHORING.md 补齐缺的部分", "规则本身不对 → 改 docs/<type>/.schema.json（改声明，同步模板资产）"],
        "pointers": ["docs/*/AUTHORING.md", "docs/*/_template.md"],
    },
    "DOC_SECTION_ORDER": {
        "severity": "block", "fix": "judgment",
        "fact": "`{path}` 的编号章节没有升序（或有重号）——重排会移动散文，必须人判",
        "options": ["把编号改回升序（不移动内容）", "内容确需换序 → 连编号一起重排，并核对文内自引"],
        "pointers": ["docs/adr/AUTHORING.md「杂项」"],
    },
    # --- 环境/配置（evaluator）：都不是仓内文件的机械偏差，故一律 judgment ---
    "MANIFEST_INVALID": {
        "fix": "judgment", "severity": "block",
        "fact": "`.agent/manifest.json` 不可用（{reason}）——它是域划分的唯一源，坏了闸就没有判据",
        "options": ["修 manifest（JSON 语法 / 缺字段 / 字段类型）后重跑 k3dge check", "刚 init 的仓 → 按 docs/guides/downstream.md 补域声明（src/spec/tests 三件）"],
        "pointers": [".agent/manifest.json", "k3dge ADR-0005 §2.8"],
    },
    "NO_DOMAINS": {
        "fix": "judgment", "severity": "block",
        "fact": "manifest.domains 是空的——没有任何域被登记，闸无从保护这个仓",
        "options": ["登记至少一个域（src / spec / tests 三件齐）", "本仓确实无代码域 → 在 manifest 里显式声明 ignore，而不是留空"],
        "pointers": [".agent/manifest.json", "k3dge ADR-0005 §2.8"],
    },
    "GIT_UNAVAILABLE": {
        "fix": "judgment", "severity": "block",
        "fact": "拿不到 git 改动集（{reason}）——闸靠 diff 定范围，没有它就只能全量或失败",
        "options": ["在 git 仓里重跑（浅克隆需 --unshallow 或 fetch-depth: 0）", "CI 里指定基线 → 导出 K3DGE_BASE_SHA", "本就想全量 → k3dge check --force-full"],
        "pointers": ["k3dge check --help", "docs/guides/downstream.md"],
    },
    "TEST_ENV_MISSING": {
        "fix": "judgment", "severity": "block",
        "fact": "域 {domain} 要跑测试但 pytest 不可用——这是**环境**缺失，不是仓内文件偏差，故不自动修",
        "options": ["装 dev 依赖（.venv/bin/pip install -e '.[dev]'）后重跑", "本轮不跑测试 → 去掉 --with-tests（硬闸仍跑静态部分）"],
        "pointers": ["scripts/init.sh", "k3dge check --with-tests"],
    },
    "TEST_FAILURE": {
        "fix": "judgment", "severity": "block",
        "fact": "域 {domain} 的测试未过（{reason}）——改代码还是改测试要人判\n{pytest_tail}",
        "options": ["修代码让测试过（测试是契约）", "测试本身过期 → 改测试并同轮更新 spec 的 Verification Matrix", "确实卡住 → 按 AGENTS.md §12 转 docs/branches/ 并 stash，不第四次重试"],
        "pointers": ["docs/specs/<domain>/spec.md", "AGENTS.md §12"],
    },
    "PIPELINE_SCHEMA_INVALID": {
        "fix": "judgment", "severity": "block",
        "fact": "`.agent/pipeline.toml` 语义校验未过（{reason}）——它声明角色/peer/传输链，坏了出向编排就没有依据",
        "options": ["按 docs/protocols/peer_contract.md 修声明（角色→peer→actions→transports）", "刚继承自模板 → 对照 src/k3dge/templates/assets/pipeline.toml.template"],
        "pointers": [".agent/pipeline.toml", "docs/protocols/peer_contract.md"],
    },
    "AUDIT_TRAIL_APPEND_ONLY": {
        "fix": "judgment", "severity": "block",
        "fact": "`{path}` 违反审计留痕 append-only（{reason}）——改史必须人判，进程不代改",
        "options": ["恢复被改写/删除的历史行（append-only：只增不改）", "确需更正 → 追加新行说明更正，不动旧行"],
        "pointers": ["k3dge ADR-0025", "docs/reviews/AUTHORING.md"],
    },
    "DOCS_ROOT_DISALLOWED": {
        "fix": "judgment", "severity": "block",
        "fact": "`{path}` 直接躺在 docs/ 根上——受管文档必须住在 docs/<type>/ 里（每个 type 有 README + AUTHORING + .schema.json）",
        "options": ["移进合适的 docs/<type>/（`k3dge doc list` 看现有类型）", "确属新类型 → 建 docs/<type>/ 并补齐 README.md + AUTHORING.md（+ .schema.json）"],
        "pointers": ["docs/README.md", "AGENTS.md「Docs — locate, then load」"],
    },
    "UNREGISTERED_DOMAIN": {
        "fix": "judgment", "severity": "block",
        "fact": "`{path}` 在 package_root 下但没有域映射它——新代码域未登记，闸与契约都看不见它",
        "options": ["补 manifest 域声明 + docs/specs/<domain>/spec.md + tests/，再 k3dge sync 回写契约哈希", "它属既有域 → 调整该域的 src 路径使其覆盖", "确不该纳管 → 在 manifest 的 ignore 里显式声明"],
        "pointers": [".agent/manifest.json", "k3dge ADR-0005 §2.8", "k3dge sync"],
    },
    # --- spec / 契约（evaluator）---
    "SPEC_NOT_FOUND": {
        "fix": "judgment", "severity": "block",
        "fact": "域 {domain} 的 spec 找不到（{spec}）——零假设纪律要求 manifest → spec → src，缺 spec 就没有判据",
        "options": ["按 docs/specs/_template/spec.md 补写该域 spec", "manifest 里的 spec 路径写错 → 改路径", "该域已废弃 → 从 manifest 删域声明"],
        "pointers": ["docs/specs/_template/spec.md", ".agent/manifest.json"],
    },
    "SPEC_DECODE_FAILED": {
        "fix": "judgment", "severity": "block",
        "fact": "域 {domain} 的 spec 不是合法 UTF-8（{reason}）——无法解析即无判据",
        "options": ["转成 UTF-8", "文件已损坏 → 从 git 历史恢复（git show <sha>:<path>）"],
        "pointers": ["docs/specs/<domain>/spec.md"],
    },
    "SPEC_MISSING_SECTION": {
        "fix": "judgment", "severity": "block",
        "fact": "域 {domain} 的 spec 缺必需章节（{reason}）——缺的是**要写的内容**，不是格式，故不自动修",
        "options": ["按 docs/specs/_template/spec.md 补齐缺的章节", "该域契约形态确实不同 → 改模板与 spec_schema（改声明，同步资产）"],
        "pointers": ["docs/specs/_template/spec.md", "src/k3dge/engine/spec_schema.py"],
    },
    "MISSING_TEST_FILE": {
        "fix": "judgment", "severity": "block",
        "fact": "域 {domain} 的 Verification Matrix 引用了不存在的测试 `{ref}`——矩阵行必须可解析到具体测试（ADR-0001 决策点 6）",
        "options": ["补上该测试文件", "测试已改名/移动 → 更新矩阵行", "该场景不再验 → 删掉矩阵行（并说明为何不再需要）"],
        "pointers": ["docs/specs/<domain>/spec.md", "k3dge ADR-0001 §2"],
    },
    "MATRIX_TEST_UNRESOLVED": {
        "fix": "judgment", "severity": "block",
        "fact": "域 {domain} 的 Verification Matrix 行绑到 `{ref}` 但解析不到具体测试（{reason}）——文件在、场景不在＝红",
        "options": ["把矩阵行细化到真实存在的测试（文件::用例）", "补上缺的那个测试场景", "跨域引用是有意为之 → 标注清楚，别让它冒充本域验证面"],
        "pointers": ["docs/specs/<domain>/spec.md", "k3dge ADR-0001 §2"],
    },
    "ASSERT_TAUTOLOGY": {
        "fix": "judgment", "severity": "block",
        "fact": "`{path}` 第 {line} 行的断言，真值已经写在表达式里——被测代码无论怎么改，这一行都过",
        "options": [
            "改成被测代码能让它失败的断言",
            "这里没有可失败的检查 → 删掉这个测试",
        ],
        "pointers": ["tests/"],
    },
    "CONTRACT_EXTRACT_FAILED": {
        "fix": "judgment", "severity": "block",
        "fact": "域 {domain} 的公有符号抽取失败（{reason}）——抽不出接口就算不出契约哈希",
        "options": ["修抽取器配置（.agent/extractors.toml / .agent/extractors/）后 k3dge extractor sync", "该语言的抽取器缺失 → 按 docs/specs/sync/spec.md 补一个并注册", "spec 的接口块格式不对 → 对照模板修正"],
        "pointers": [".agent/extractors.toml", "k3dge extractor sync", "docs/specs/sync/spec.md"],
    },
    "DOMAIN_IMPORT_VIOLATION": {
        "fix": "judgment", "severity": "block",
        "fact": "域 {domain} 反向 import 了 `{target}` 但未声明 depends_on——**方向要人判**：是依赖该声明，还是这次耦合本就不该存在",
        "options": ["确属正当依赖 → 在 manifest 的该域 depends_on 里声明，再 k3dge sync", "不该耦合 → 把共用的东西下沉到叶子模块，或反转依赖方向", "边界划错了 → 按 .agent/rules/08-design-discipline.md 重划事实归属（走 ADR）"],
        "pointers": [".agent/manifest.json", ".agent/rules/08-design-discipline.md", "k3dge ADR-0001 §2"],
    },
    # --- warn：显示但不拦（孤儿＝可能是有意的新增，判定归人）---
    "ORPHAN_SCAN": {
        "fix": "judgment",
        "severity": "warn",
        "fact": "孤儿扫描（spec/test/adr 零引用）自身异常：{path}",
        "options": [
            "按提示修 manifest/权限/JSON 后重跑 `k3dge check`",
            "确认工具故障 → 本条只观测不拦（工具坏不得阻断提交）",
        ],
        "pointers": ["src/k3dge/engine/doc_gate.py", "k3dge ADR-0012"],
    },
    "ORPHAN_TEST": {
        "fix": "judgment",
        "severity": "warn",
        "fact": "`{path}` 没有被任何 Verification Matrix 行引用——测试存在但不在验证面上",
        "options": [
            "在对应 spec 的 Verification Matrix 里补一行引用它",
            "确认是有意留（探索性/临时测试）→ 不处理，本条只观测不拦",
        ],
        "pointers": ["docs/specs/<domain>/spec.md", "k3dge ADR-0005 §2.5"],
    },
    "ORPHAN_SPEC": {
        "fix": "judgment",
        "severity": "warn",
        "fact": "`{path}` 没有被 manifest 的任何域引用——spec 存在但不是任何域的判据",
        "options": [
            "在 .agent/manifest.json 的域里补 spec 指针",
            "确认是有意留（跨域说明/模板）→ 不处理，本条只观测不拦",
        ],
        "pointers": [".agent/manifest.json", "k3dge ADR-0005 §2.8"],
    },
    "TASK_MILESTONE_AFTER_BOUNDARY": {
        "fix": "judgment", "severity": "warn",
        "fact": "`{path}` 在 `{milestone}` 的边界（`tag <M> = <B>`）那一版里**还不存在**，"
                "却挂在 `{milestone}` 上——按 ADR-0004 §2.1.9，边界之后的改动归下一个里程碑",
        "options": ["重挂到它实际所属的里程碑：`k3dge milestone reassign {milestone} --to <目标>`",
                    "确认它确实属于 `{milestone}`（边界 tag 立错/补记）→ 不处理，本条只观测不拦"],
        "pointers": ["k3dge ADR-0004 §2.1.9", "k3dge milestone reassign"],
    },
    # --- observe：观测建议，不阻断、不裁决（service 角色；peer 不可达即无提示）---
    "DUP_CHECK": {
        "fix": "judgment",
        "severity": "observe",
        "fact": "新建票据与集存内容可能重复（候选见下）——是不是真重复由你判，本条不阻断、不裁决",
        "options": [
            "确属重复 → 并入既存票据（`k3dge task done <旧票>` 记关闭理由），不新开",
            "确属新事 → 保留本票，无需动作",
        ],
        "pointers": ["docs/tasks/AUTHORING.md", "k3dge task list --json"],
    },
    "ORPHAN_ADR": {
        "fix": "judgment",
        "severity": "warn",
        "fact": "`{path}` 未列入 docs/adr/README.md 的 Topics——决策存在但索引找不到它",
        "options": [
            "在 README 的 Topics 里补一行（按类归入）",
            "该 ADR 已退役 → 移入 docs/adr/obsolete/（reconcile 由 k3dge sync 跑）",
        ],
        "pointers": ["docs/adr/README.md", "docs/adr/AUTHORING.md"],
    },
}


#: 可修性闭集（唯一源）。deterministic = 进程可按固定规则改（幂等、无需判断）；
#: judgment = 必须人/agent 判（方向不明、要读懂语义、或会改史）。
FIX_KINDS: tuple = ("deterministic", "judgment")


def fix_kind(code: str) -> str:
    """该 code 的修复性质。

    未声明的 code 按 `judgment` 兜底（保守：不假装能自动修）；但**已进表的 code 必须
    显式写 `fix`**——由 test_gate_facts 守，防止靠默认值蒙混过关（那份"进程能不能修"
    的清单是本表的主要产出之一，默认值会让它失真）。
    """
    return str((GATE_FACTS.get(code) or {}).get("fix") or "judgment")


def is_declared(code: str) -> bool:
    """该 code 是否已进声明表（未进 ⇒ 调用方用自己的 message 兜底）。"""
    return code in GATE_FACTS


def severity(code: str) -> str:
    """档位唯一源：查表；未声明按 `DEFAULT_SEVERITY`。消费者不得自己判档位。"""
    decl = GATE_FACTS.get(code) or {}
    sev = str(decl.get("severity") or DEFAULT_SEVERITY)
    return sev if sev in SEVERITIES else DEFAULT_SEVERITY


def fill(template: str, facts: Optional[Dict[str, Any]]) -> str:
    """把 `{key}` 用检查器给的结构化事实填上；缺失键原样留着（不抛）。"""
    if not template:
        return ""
    if not facts:
        return template
    try:
        return template.format_map(_SafeFacts({k: v for k, v in facts.items() if v is not None}))
    except (ValueError, IndexError):  # 模板里有非占位的花括号
        # 兜底路径与主路径同口径：值为 None 视作"事实缺失"，留字面 `{key}`；
        # 直接 str(None) 会把 "None" 印进闸文（且与 _SafeFacts 不一致，ocr-245）。
        usable = {k: val for k, val in facts.items() if val is not None}
        return _PLACEHOLDER.sub(lambda m: str(usable.get(m.group(1), m.group(0))), template)


def render(code: str, facts: Optional[Dict[str, Any]] = None, *, where: str = "",
           detail: str = "") -> str:
    """给**判断主体**的投影：陈述式 fact + 成对 options + pointers（不出疑问句）。

    `where`  = 位置（文件/域），挂在首行末尾，与 `[GATE ERROR] … [path]` 的旧形状兼容。
    `detail` = 检查器给出的具体事实（哪一行/哪个值不一致）。**过渡约定**：检查器尚未
               结构化为 `facts` 的，用它把细节带出来，避免为了单源而丢掉信息；
               检查器迁到结构化事实后本参数可空。
    """
    decl = GATE_FACTS.get(code)
    if not decl:
        return ""
    lines = [f"fact: {fill(str(decl.get('fact', '')), facts)}"]
    if detail:
        lines.append(f"detail: {detail}")
    if decl.get("fix") == "deterministic":
        lines.append(f"fix: 确定性可修——{fill(str(decl.get('fix_hint', '')), facts)}")
    for opt in decl.get("options") or []:
        lines.append(f"option: {fill(str(opt), facts)}")
    ptrs = [fill(str(p), facts) for p in (decl.get("pointers") or [])]
    if ptrs:
        lines.append("pointers: " + " | ".join(ptrs))
    head = f"[{code}]" + (f" {where}" if where else "")
    # 事实值本身可含换行（如 TEST_FAILURE 的 `\n{pytest_tail}`）⇒ 只给逻辑行加缩进会让
    # 续行顶到第 0 列，破坏渲染块结构（ocr-246）。
    return head + "\n" + "\n".join(
        "\n".join("  " + sub for sub in ln.split("\n")) for ln in lines)


def projection(code: str, facts: Optional[Dict[str, Any]] = None) -> dict:
    """给**进程**的投影：闭集（code + severity + 事实），无文案、无分支余地。"""
    return {
        "code": code,
        "severity": severity(code),
        "declared": is_declared(code),
        "facts": dict(facts or {}),
    }


def facts_of(code: str) -> List[str]:
    """声明里用到的占位键名（供守卫测试核对检查器是否真给了这些事实）。"""
    decl = GATE_FACTS.get(code) or {}
    keys: List[str] = []
    # `render()` 也会对 `fix_hint` 与 `pointers` 填占位 ⇒ 守卫面必须一起扫，否则
    # "声明要的事实、检查器没给"只在部分字段上被兜住（423）
    texts = [str(decl.get("fact", "")), str(decl.get("fix_hint", ""))]
    texts += [str(o) for o in (decl.get("options") or [])]
    texts += [str(x) for x in (decl.get("pointers") or [])]
    for text in texts:
        for m in _PLACEHOLDER.finditer(text):
            if m.group(1) not in keys:
                keys.append(m.group(1))
    return keys
