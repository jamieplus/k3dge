"""硬闸契约：**声明面只有一处** ＝ `.agent/pipeline.toml`（`[checks.*]` + `[gates.*]`）。

- `[checks.<op>]`：编排单元 —— `preconditions`（闸 id）/ `actions`（内部动作 id）/
  `stages_<phase>`（外部 peer action ref）。两类 id 不混一张词表（ADR-0026 §2.1）。
- `[gates.<name>]`：阈值/开关（`audit_trigger` / `search` / `markers` / `output`）。

单一源与缺省：缺省值在 `DEFAULTS`（代码内，**必须完整**）；仓内声明按段覆盖；
文件缺失或解析失败 ⇒ 回落缺省（**闸不因配置坏而失效**，ADR-0026 §2.7）。
契约只承载数据，不含逻辑/表达式。机制见 ADR-0001 §2 第 8 条。

历史：曾有两个配置文件（`.agent/gates.toml` + `.agent/pipeline.toml` 的 `[pipelines.*]`），
后者只有校验没有执行者、前者本仓已删 ⇒ 收敛到 pipeline.toml 一处。
`.agent/gates.toml` 若仍存在，由 `pipeline_schema` 红一次逼迁移（不静默忽略）。
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict


class Rejection(str):
    """结构化拒绝：消息文本（str 兼容）+ 闭集 `gate_id`（机器分支用）。

    为何是 str 子类：拒绝消息已经流经 `(ok, msg)` / `print(msg)` / 测试断言；
    携带 id 不必改任何返回元数（规则 02）。消费方（`nextstep.next_for_rejection`）
    读 `gate_id` 查表派发；**不得**再从消息文本里搜关键词（memo §S7：投影给进程的
    判定必须是闭集，散文无法机械分支）。

    不在 `gate_id` 词表里的 id 由消费方兜底为 `rejected`（原文照登，不猜）。
    """

    __slots__ = ("gate_id",)

    def __new__(cls, gate_id: str, message: str) -> "Rejection":
        self = super().__new__(cls, message)
        self.gate_id = gate_id
        return self

    def __repr__(self) -> str:  # pragma: no cover - 调试可读性
        return f"Rejection({self.gate_id!r}, {str.__str__(self)!r})"


def rejection(message: Any, fallback_gate_id: str) -> Rejection:
    """把动作/闸的失败返回值正规化为 `Rejection`（已是 Rejection 则原样透传）。"""
    if isinstance(message, Rejection):
        return message
    gid = getattr(message, "gate_id", None) or fallback_gate_id
    text = "" if message is None else str(message)
    if not text.strip():
        # `Rejection` 是 str 子类：空消息对象本身 falsy ⇒ `if out:`（nodes.run_phase 前置闸分支、
        # seal 的 `not e` 判定）会把"失败但没带原因"读成**通过**。永不留空（ocr-248）。
        text = f"({fallback_gate_id} 判定为失败，但未给出原因)"
    return Rejection(gid, text)

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

REL = ".agent/pipeline.toml"        #: 声明面唯一入口
LEGACY_REL = ".agent/gates.toml"    #: 已废；存在即红（pipeline_schema 出迁移守卫）

#: 内部拒绝 id（不由 pipeline.toml 声明，但同样进 `nextstep.GATE_NEXT` 闭集）。
INTERNAL_GATE_IDS: tuple = (
    "unknown_gate_id",       # 契约引用了未实现的闸 id（配置错）
    "unknown_action_id",     # 契约引用了未实现的动作 id（配置错）
    "audit_report_missing",  # 无 12 列报告（审计腿未落盘）
    "audit_open_declined",   # 待修>0 且 agent 拒绝修复
    "audit_noop",            # 审计跳被跳过/失败（空转不得当闭环，ADR-0004 §2.1.11）
    "audit_degraded_unsigned",  # 降级到 manual 但报告无署名/来源
    "milestone_id_invalid",
    "no_tasks",
    "invalid_task_status",
    "align_failed",
    "archive_failed",
)

#: 各闸的缺省阈值/开关（唯一源，必须完整）。仓内 `.agent/pipeline.toml` 可覆盖。
DEFAULTS: Dict[str, Any] = {
    "audit_trigger": {"c2_nesting_max": 5, "volume_max": 8},
    "search": {"context_max": 3},
    "markers": {"max_note": 80, "max_note_pending": 500},
    "output": {"default_lines": 10},
    # 编排单元：preconditions（闸 id，全绿才继续）+ actions（**内部**动作 id）
    #            + stages_*（**外部** peer action ref，交 run_action 走传输链）。
    # 两类 id 不混一张词表（ADR-0026 §2.1：席位原子调用 vs k3dge 自身的步）。
    # 见 ADR-0001 §2 第 8 条。
    "checks": {
        # 耐久＝闸（ADR-0022 §2.2 🅰1.4）：docs 规约化必须在封板**之前**做完
        # 预审＝进**审计**的门槛（ADR-0004 §2.1.9 相位 1）：形式闸在此，不卡在封板收尾。
        # `align_pass` 虽在列，却由本单元第一个动作 `full_matrix` 满足（`[nodes.*].satisfies`）
        # ⇒ 清单显示 ⚙️，不要求人预先手跑 align。
        # 已移出（ADR-0004 §2.1.3/§2.1.9/§2.1.10）：报告存在性（`audit_closed`/`evidence_chain`）
        # 与基线新鲜度（`audit_fresh`）——报告降为可选产物，边界由 `tag <M>=<B>` 表达。
        "seal": {"preconditions": ["tasks_all_done", "align_pass", "guides_filled",
                                   "adrs_all_accepted", "adr_landed", "adr_amend_format",
                                   "docs_normalized"],
                 "actions": ["full_matrix", "audit", "archive", "version_bump",
                             "closure_note", "seal_record", "prune"]},
        "align": {"preconditions": ["tasks_all_done"], "actions": ["full_matrix"]},
        # sync 链：顺序＝声明序；各步性质（投影/事实源）见 nodes.NODE_DEFAULTS
        "sync": {"actions": ["sync_extractors", "reconcile_adrs", "sync_domains",
                             "sync_manual_docs", "sync_docs_index"]},
        # 审计腿默认**无外部步**：k3dit 是本地命令行工具（和 `git` 同层），由 bundle 腿按 argv 调用 +
        # 读包 + 落树 + 落账；自证走工具子命令。仍有对等 harness 的仓**显式**声明 stages_*（用角色名
        # audit.*，不写死 peer 名）；这里留空 = 缺省就不声明一个解析不到的 action。
        # 审计**默认没有外部步**：k3dit 是本地命令行工具（和 `git` 同层）⇒ bundle 腿按 argv 调用它、
        # 读包、落树、落账（ADR-0025 §2.9.6）。仍有对等 harness 的仓可自行声明 stages_*（显式覆盖）。
        "audit": {"stages_produce": [],
                  "stages_verify": []},
    },
}


def _merge_section(data: Dict[str, Any], raw: Dict[str, Any]) -> None:
    """段内覆盖；`checks.<kind>` 逐键覆盖（下游只改一个 op 不必抄全表）。"""
    for section, vals in (raw or {}).items():
        if not isinstance(vals, dict):
            # 写成标量/列表 ⇒ 下游 `get()` 会 `5.get(key)` AttributeError、`nodes.decl()` 会
            # `merged.update("fact")` ValueError。忽略该覆盖并出声（ocr-249）。
            import sys

            print(f"[gates] WARN: 段 '{section}' 不是表（{type(vals).__name__}）⇒ 忽略该覆盖", file=sys.stderr)
            continue
        if section == "checks":
            for kind, decl in vals.items():
                if isinstance(decl, dict):
                    data.setdefault("checks", {}).setdefault(kind, {}).update(decl)
        else:
            data.setdefault(section, {}).update(vals)


def load(workspace: Path) -> Dict[str, Any]:
    """缺省 ∪ `.agent/pipeline.toml` 的 `[gates.*]` + `[checks.*]`；缺失/坏 ⇒ 缺省。"""
    data: Dict[str, Any] = copy.deepcopy(DEFAULTS)  # 深拷贝：覆盖不得回写 DEFAULTS
    p = Path(workspace) / REL
    if not p.is_file():
        return data
    try:
        raw = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # 坏 TOML/权限/编码：回落缺省但**必须出声**（静默放宽 preconditions/阈值 = 假绿，ocr-250）
        import sys

        print(f"[gates] WARN: {REL} 不可读/解析失败（{type(exc).__name__}: {exc}）⇒ 按缺省跑，"
              "仓内声明的覆盖未生效", file=sys.stderr)
        return data
    if not isinstance(raw, dict):
        return data
    # [gates.<name>] 的内容即阈值段本身（audit_trigger/search/markers/output），平铺合并
    if isinstance(raw.get("gates"), dict):
        _merge_section(data, raw["gates"])
    # [nodes.<id>]：编排节点的属性声明（kind/on_error/on_rerun/needs/produces）
    if isinstance(raw.get("nodes"), dict):
        _merge_section(data, {"nodes": raw["nodes"]})
    if isinstance(raw.get("checks"), dict):
        _merge_section(data, {"checks": raw["checks"]})
    return data


def legacy_config_present(workspace: Path) -> bool:
    """已废的 `.agent/gates.toml` 是否还在（在 ⇒ 迁移守卫红一次，不静默忽略）。"""
    return (Path(workspace) / LEGACY_REL).is_file()


def get(workspace: Path, section: str, key: str) -> Any:
    """读某闸的某阈值（含缺省）。调用方普遍 `int(gates.get(...))` ⇒ 绝不返回 None（ocr-247）。"""
    sec = load(workspace).get(section)
    sec = sec if isinstance(sec, dict) else {}
    val = sec.get(key, DEFAULTS.get(section, {}).get(key))
    if val is None:
        import sys

        print(f"[gates] WARN: '{section}.{key}' 无值且缺省也没有 ⇒ 返回 0", file=sys.stderr)
        return 0
    return val


def preconditions(workspace: Path, kind: str) -> list:
    """某编排单元（`check`/`align`/`seal`）的前置闸 id 列表。"""
    return list(load(workspace).get("checks", {}).get(kind, {}).get("preconditions", []))


def stages(workspace: Path, kind: str, phase: str) -> list:
    """某编排单元某相位的**外部 peer 步**（action ref 列表）。

    `phase` ∈ {produce, verify}（读 `stages_<phase>`）。与 `actions()` 分型：
    actions 是 k3dge 内部动作 id（注册表），stages 是外部 peer 的 action ref
    （交 `run_action` 走 mcp→cli→manual/skip 传输链）。
    """
    decl = load(workspace).get("checks", {}).get(kind, {})
    return list(decl.get(f"stages_{phase}", []))


def all_stage_refs(workspace: Path) -> list:
    """全部已声明的外部步 ref（供 schema 交叉校验：声明了就必须能解析）。"""
    checks = load(workspace).get("checks", {})
    out: list = []
    for kind, decl in checks.items():
        if not isinstance(decl, dict):
            continue
        for key, val in decl.items():
            if key.startswith("stages_") and isinstance(val, list):
                out.extend(str(v) for v in val)
    return out


def actions(workspace: Path, kind: str) -> list:
    """某编排单元的**内部**动作 id 列表。"""
    return list(load(workspace).get("checks", {}).get(kind, {}).get("actions", []))
