"""闸核不得 import 生命周期（T-02 依赖方向：evaluate 及其检查只出 Violation）。"""

import ast
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[3] / "src" / "k3dge" / "engine"
# 根漂移的失败模式要**指名道姓**（t-129）：否则第一条报错是 "missing gate module
# evaluator.py"——把"路径算错了"误写成"被测件没了"。rglob 落空时守卫还会整体空转。
assert ENGINE.is_dir(), f"engine 目录不在：{ENGINE}（parents[3] 漂了？）"

# Form-gate cluster: disk → Violation / hash. Must not pull writers or the facade.
_GATE = frozenset({
    "evaluator.py",
    "assert_tautology.py",
    "contract.py",
    "diff.py",
    "spec_schema.py",
    "manifest.py",
    "pairs.py",
    "models.py",
    "gates.py",
    "pipeline_schema.py",
    "mcp_json.py",
    "pure_schema.py",
    "pure_refs.py",
    "extractor_gen.py",
})

# Mutators + outbound + the compatibility facade (importing it pulls the graph).
# 这份名单在 allowlist 测里**不再当判据用**（denylist 会随引擎生长静默腐烂，t-128）；
# 保留为词表：任何被登记成 helper 的模块都不得出现在这里（下面有一条不相交断言）。
_LIFECYCLE = frozenset({
    "k3dge.engine.milestone",
    "k3dge.engine.align",
    "k3dge.engine.seal",
    "k3dge.engine.seal_flow",
    "k3dge.engine.task_write",
    "k3dge.engine.audit_flow",
    "k3dge.engine.worktree",
    "k3dge.engine.pipeline_runner",
    "k3dge.engine.milestone_audit",
    "k3dge.engine.doc_audit",
    "k3dge.engine.changelog",
    "k3dge.engine.review_archive",
    "k3dge.engine.prompt",
})

# 闸核可导入的 engine 邻居——**逐个登记并写许可由**（allowlist，t-128）。
# 新增 engine 模块默认**拒**：要进闸核必须先在这里登记，登记就得说清它不是写侧/编排。
_ENGINE_HELPER_OK = {
    "doc_catalog": "docs 目录只读查询（索引投影）",
    "events": "观测件 append（ADR-0026 D 线：状态可见，非编排）",
    "gate_facts": "闸红文案声明面（纯表）",
    "generated_docs": "投影渲染（写盘由调用方做）",
    "nextstep": "STATE_OPTIONS 声明表（纯数据）",
    "search": "受控搜索（只读）",
    "state_machine": "task 状态定义（枚举/迁移表）",
    "version": "只用 validate_versions（bump_version 在 seal 线里跑）",
}


def _imported_modules(path: Path, package: str = "k3dge.engine") -> set[str]:
    """解析出**被导入的完整模块名**。

    旧实现只记 `node.module`，于是本仓最主流的两种写法全部漏判（t-127）：
    `from k3dge.engine import milestone` 记成 `"k3dge.engine"`（不是生命周期模块），
    `from . import milestone` / `from .milestone import x` 因为 `node.module` 为 None/裸名而不匹配。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:                                   # 相对导入 ⇒ 按本模块所在包展开
                base = package if not node.module else f"{package}.{node.module}"
                found.add(base)
                for alias in node.names:
                    if alias.name != "*":
                        found.add(f"{base}.{alias.name}")
            elif node.module:
                found.add(node.module)                        # `from k3dge.engine import milestone`
                for alias in node.names:
                    if alias.name != "*":
                        found.add(f"{node.module}.{alias.name}")
    return found


class TestGateClusterImports(unittest.TestCase):
    def test_gate_cluster_imports_are_allowlisted(self) -> None:
        """闸核的 engine 内依赖必须逐个登记（allowlist，t-128）。

        denylist 只对**列出来的**名字生效——新长出的 mutator/outbound 面默认放行，
        守卫随引擎生长静默腐烂。这里反过来：闸核文件里每一个 `k3dge.*` 导入必须落在
        `_GATE` ∪ `_ENGINE_HELPER_OK`，其余一律红；跨出 engine（`k3dge.cli.*`）同样拒。
        """
        allowed_engine = {Path(n).stem for n in _GATE} | set(_ENGINE_HELPER_OK)
        offenders = []
        for name in sorted(_GATE):
            path = ENGINE / name
            self.assertTrue(path.is_file(), f"missing gate module {name}")
            for mod in _imported_modules(path):
                if not mod.startswith("k3dge."):
                    continue                      # stdlib/第三方：本测不管（另一不变量）
                parts = mod.split(".")
                if parts[1] != "engine":
                    offenders.append(f"{name} imports {mod}（闸核不得跨出 k3dge.engine）")
                    continue
                if len(parts) >= 3 and parts[2] not in allowed_engine:
                    offenders.append(f"{name} imports {mod}——未登记进 allowlist"
                                     "（新邻居：先证明它不是写侧/编排，再进 _ENGINE_HELPER_OK）")
        self.assertEqual(offenders, [], "\n  ".join(offenders))

    def test_allowlist_and_lifecycle_vocabulary_are_disjoint(self) -> None:
        """两张表不得互相拆台：登记成 helper 的模块不能同时是生命周期成员。"""
        lifecycle_names = {m.split(".")[-1] for m in _LIFECYCLE}
        overlap = sorted(lifecycle_names & set(_ENGINE_HELPER_OK))
        self.assertEqual(overlap, [], f"既是 _LIFECYCLE 又被 allow 的模块：{overlap}")


def test_facts_of_covers_every_rendered_field() -> None:
    """`facts_of` 必须等于 render() 填占位四个字段的并集（423；t-130）。

    旧写法三病：`next()` 无 default（表一变即 `StopIteration` 裸炸，不报是哪张表）；
    兜底分支挑一条"恰好有 fix_hint"的码，而它可能**根本没有** `{path}` ⇒ 尾断言靠
    `or` 后支自证通过；且只验 'path' 一个键、不验四字段完整性。
    现在逐 code 对账占位键集合，全表扫描＋"至少扫到过一个占位"的正向控制。
    """
    import re

    from k3dge.engine import gate_facts

    pat = re.compile(r"\{(\w+)\}")
    scanned = 0
    for code, decl in gate_facts.GATE_FACTS.items():
        texts = [str(decl.get("fact", "")), str(decl.get("fix_hint", ""))]
        texts += [str(x) for x in (decl.get("options") or [])]
        texts += [str(x) for x in (decl.get("pointers") or [])]
        want: set = set()
        for t in texts:
            want.update(pat.findall(t))
        scanned += len(want)
        got = set(gate_facts.facts_of(code))
        assert got == want, f"{code}: facts_of={sorted(got)} 渲染面={sorted(want)}"
    assert scanned > 0, "整张表没有任何占位符——本测在空转，先去看声明面发生了什么"


def test_generated_docs_fence_survives_backticks_in_iface(tmp_path, monkeypatch) -> None:
    """docstring 里出现三反引号会提前关围栏 ⇒ 投影形状坏（426）。"""
    from k3dge.engine import contract
    from k3dge.engine.generated_docs import render_manual_docs_content
    from k3dge.engine.manifest import Manifest

    nasty = "def f():\n    pass\n\n# doc: 例 ```py\nx\n```\n"
    monkeypatch.setattr(contract, "collect_domain_interface", lambda *a, **k: nasty)
    ws = _mini_ws(tmp_path)
    content = render_manual_docs_content(ws, Manifest.load(ws))
    # 先证"页面还在、键还是 Path 形状"（t-131），再看围栏——否则 `[0]`/`.name` 抛
    # IndexError/AttributeError，把渲染器改名伪装成"本测的回归消息"。
    api_pages = [(k, v) for k, v in content.items() if getattr(k, "name", None) == "api.md"]
    assert api_pages, f"render_manual_docs_content 没再产出 api.md（键形状/页面名变了？）：{list(content)}"
    api = api_pages[0][1]
    assert "````python" in api, api[-500:]


def _mini_ws(tmp_path: Path) -> Path:
    (tmp_path / ".agent").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".agent" / "manifest.json").write_text(
        '{"package_root":"src","domains":{"demo":{"src":"src/demo","spec":"docs/specs/demo/spec.md"}}}',
        encoding="utf-8")
    (tmp_path / "src" / "demo").mkdir(parents=True)
    (tmp_path / "src" / "demo" / "__init__.py").write_text("def f():\n    pass\n", encoding="utf-8")
    return tmp_path
