"""k3dge 文档/结构闸（原 `scripts/pre-commit` 的三层实现，2026-09-21 迁入 engine）。

**为什么迁**：这三层此前只活在 k3dge 自己仓的 hook 脚本里 ⇒ ① 无法单测（只能整体跑脚本）
② `k3dge init` 下发的仓根本拿不到 hooks（脚本不在资产里）⇒ 本仓的 doc-gate / 引用闸 / 排查闸
**从未到达下游**（实测：init 后照 AGENTS.md 激活 hooks，`git commit` 因脚本缺失被 git 静默跳过）。

三层，从便宜到贵：
1. doc-gate：每个 `docs/<type>/` 必须有 README.md + AUTHORING.md。
2. schema gate：staged 受管文档过 `.schema.json` + `pure_refs`（悬空引用 / 名实一致 /
   markdown 完整性 / 归档去向 / orphan）。
3. screen gate：新建受管文档的 `DOC_NEW_UNSCREENED` 排查（阻断一次）。

一致性闸（`k3dge check`）不在这里：那是**进程**动作，由薄壳 hook 在"有代码/规格改动"时调
`scripts/gate.py`（本模块只出 `relevant_for_check()` 判据）。

调用面：本仓与下游的 `scripts/pre-commit`（薄壳、PAIRS 字节锁）→ `main()`；
测试 → 各层函数 + `set_workspace()`。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

AUTHORING = "AUTHORING.md"


def _detect_workspace() -> Path:
    """git 顶层（hook 从仓库内任意目录被调都能工作）；不在 git 仓里则退回 CWD。"""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except OSError:
        pass
    return Path.cwd().resolve()


#: 工作区（单源）。薄壳 hook 在启动时 `set_workspace()`；测试也用它切临时仓。
WS: Path = _detect_workspace()


def set_workspace(workspace: Path) -> None:
    """显式指定工作区（下游 hook / 测试用；不传则用 git 顶层）。"""
    global WS
    WS = Path(workspace).resolve()


# Fallback aux set when pure modules are unavailable (kept in sync by test).
_AUX_FALLBACK = frozenset({
    "README.md", "_template.md", "AUTHORING.md", "summary.md",
    "SUMMARY.md", "LEFTOVERS.md", "leftovers.md",
})


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        cwd=WS, capture_output=True, text=True,
    )
    return [p for p in out.stdout.splitlines()]


def staged_added() -> list[str]:
    """本次提交**新增**的文件（`--no-renames`：改名算 A+D，新路径须重新排查）。"""
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A", "--no-renames"],
        cwd=WS, capture_output=True, text=True,
    )
    return [p for p in out.stdout.splitlines() if p.strip()]


# k3dge check only matters when code / spec / agent-config / templates change.
_CHECK_PREFIXES = ("src/", "docs/specs/", ".agent/", "src/k3dge/templates/")
_CHECK_SUFFIXES = (".py", "manifest.json", "pyproject.toml", ".toml")


def relevant_for_check(files: list[str]) -> bool:
    return any(
        f.startswith(_CHECK_PREFIXES) or f.endswith(_CHECK_SUFFIXES) for f in files
    )


def check_one(rel: str) -> list[str]:
    parts = Path(rel).parts
    domain = parts[1] if len(parts) > 1 else ""
    type_dir = WS / "docs" / domain
    errs: list[str] = []
    rm = type_dir / "README.md"
    am = type_dir / AUTHORING
    if not rm.exists():
        errs.append(f"{rm.relative_to(WS)}: missing — every docs subdir must have a README.md")
    if not am.exists():
        errs.append(f"{am.relative_to(WS)}: missing — every docs subdir must have AUTHORING.md")
    return errs


def _load_pure():
    """Import zero-dependency check modules from the `src/` tree (no venv).

    Returns (pure_schema, pure_refs) or (None, None) with a WARN — the hook
    must never block commits just because its own tooling failed to load.
    """
    try:
        sys.path.insert(0, str(WS / "src"))
        from k3dge.engine import pure_refs, pure_schema
        return pure_schema, pure_refs
    except Exception as exc:
        print(f"[k3dge schema] WARN: pure checks unavailable ({exc}); legacy gate only")
        return None, None


def _load_gate_facts():
    """闸红文案/档位的声明面（零依赖）。不可用 ⇒ None，消费者回落自带文案。"""
    try:
        sys.path.insert(0, str(WS / "src"))
        from k3dge.engine import gate_facts
        return gate_facts
    except Exception as exc:  # 工具坏不得阻断所有提交
        print(f"[k3dge screen] WARN: gate_facts unavailable ({exc}); 回落简式输出")
        return None


def _staged_bytes(rel: str) -> bytes | None:
    """Staged blob content (what will actually commit), not the worktree."""
    out = subprocess.run(["git", "show", f":{rel}"], cwd=WS, capture_output=True)
    return out.stdout if out.returncode == 0 else None


def _type_of(rel: str) -> str:
    parts = Path(rel).parts
    return parts[1] if len(parts) > 1 else ""


def _is_aux(name: str, aux: frozenset) -> bool:
    return name in aux


#: 本轮渲染时"声明要的事实、检查器没给"的 `(code, missing)`（自检信号，见 `missing_declared_facts`）
_MISSING_FACTS: set = set()


def missing_declared_facts(code: str, facts: dict, gate_facts=None) -> list:
    """声明里用到的占位键中，调用方**没给**的那些。

    这是"声明面 ↔ 产出点"漂移的早期信号：代码表里写了 `{peer}` 而检查器不传 `peer`，渲染出来就是
    字面 `{peer}`（`_SafeFacts` 只保证不崩，不保证正确）。消费者＝`_add()`（累积）+ 闸尾统一 WARN。
    """
    if gate_facts is None:
        return []
    return [k for k in gate_facts.facts_of(code) if k not in facts]


def run_schema_gate(files: list[str], pure_schema, pure_refs, gate_facts=None) -> tuple[list[str], list[str]]:
    """Returns (blocking, non_blocking). Staged content only.

    **档位由 `gate_facts` 声明面决定**，不由"append 到哪个列表"隐式决定；未声明的 code
    一律 block（保守：新码默认拦，降级必须显式声明）。已声明且有结构化事实的 code 走
    单一渲染器（fact + 成对 options + pointers）；未迁移的 code 保持旧串（增量迁移）。
    """
    errs: list[str] = []
    warns: list[str] = []

    def _add(code: str, msg: str, where: str = "", facts: dict | None = None) -> None:
        sev = gate_facts.severity(code) if gate_facts else "block"
        text = ""
        if gate_facts is not None and gate_facts.is_declared(code):
            # `path` 由调用方显式给（不使用 `msg.split(":")` —— 那是对散文的解析）
            f: dict = {}
            if where:
                f["path"] = where
            f.update(facts or {})
            for miss in missing_declared_facts(code, f, gate_facts):
                _MISSING_FACTS.add((code, miss))
            # 检查器原文作为 detail 带出（过渡约定：尚未结构化的检查器不丢信息）
            text = gate_facts.render(code, f, where=where, detail=msg)
        line = text or (f"{where}: [{code}] {msg}" if where else f"[{code}] {msg}")
        (warns if sev != "block" else errs).append(line)
    aux = getattr(pure_schema, "AUX_NAMES", _AUX_FALLBACK)
    doc_files = [
        f for f in files
        if f.startswith("docs/") and f.endswith(".md")
        and not _is_aux(Path(f).name, aux)
        and "archive" not in Path(f).parts
    ]
    if not doc_files:
        return errs, warns
    schemas: dict[str, object] = {}
    for rel in doc_files:
        typ = _type_of(rel)
        if typ not in schemas:
            schemas[typ] = _load_type_schema(typ, pure_schema)
        schema, schema_err = schemas[typ]
        raw = _staged_bytes(rel)
        if raw is None:
            continue
        # B3 bytes first: undecodable files cannot be text-checked
        for code, msg in pure_refs.check_markdown_bytes(raw, rel):
            _add(code, msg, where=rel)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if schema_err:
            errs.append(f"{schema_err}")   # schema 文件本身坏：无 code 可查，直接拦
            continue
        if schema is not None:
            # A-part: file-local structure
            violations, ident, ok = pure_schema.check_file(
                schema, Path(rel).name, text, schema_rel=f"docs/{typ}/.schema.json")
            for code, msg, scope in violations:
                loc = f"docs/{typ}/.schema.json" if scope == "schema" else rel
                _add(code, msg, where=loc)
            if ok and schema.get("index"):
                idx_path = WS / "docs" / typ / schema["index"]
                idx_text = idx_path.read_text(encoding="utf-8") if idx_path.is_file() else ""
                for code, msg, _s in pure_schema.check_index_ref(
                        idx_text, ident, schema.get("codes") or {}, schema["index"], Path(rel).name):
                    _add(code, msg, where=rel)
        # B1 dangling refs (block)
        for code, msg in pure_refs.check_dangling_adr(WS, rel, text):
            _add(code, msg, where=rel)
        for code, msg in pure_refs.check_adr_ref_retired(WS, rel, text):
            _add(code, msg, facts={"path": rel})
        for code, msg in pure_refs.check_adr_number_reuse(WS, rel):
            _add(code, msg, facts={"path": rel})
        for code, msg in pure_refs.check_retired_adr_dest(rel, text):
            _add(code, msg, facts={"path": rel})
        for code, msg in pure_refs.check_incident_id_redundant(rel, text):
            _add(code, msg, facts={"path": rel})
        for code, msg in pure_refs.check_report_pointer(WS, rel, text):
            _add(code, msg, where=rel)
        for code, msg in pure_refs.check_footnotes(rel, text):
            _add(code, msg, where=rel)
        # B2 name/content consistency (block)
        for code, msg in pure_refs.check_task_consistency(rel, text):
            _add(code, msg, where=rel)
        for code, msg in pure_refs.check_adr_consistency(rel, text):
            _add(code, msg, where=rel)
        for code, msg in pure_refs.check_supersede_unreconciled(WS, rel, text):
            _add(code, msg, where=rel)
        # B3 text markdown
        for code, msg in pure_refs.check_markdown_text(text, rel):
            _add(code, msg, where=rel)
    # B4 orphans：档位查表（声明为 warn），不在这里写死"WARN-only"
    if any(f.startswith(("docs/", "tests/")) or f == ".agent/manifest.json" for f in files):
        for code, msg, facts in _orphan_warnings(pure_refs):
            _add(code, msg, facts=facts)
    # 归档去向标记（warn 档，ADR-0023 §2.2）：只对本轮 staged 增量
    for code, msg in pure_refs.find_unguarded_archives(WS, files):
        _add(code, msg, facts={"path": msg})
    return errs, warns


def run_screen_gate(added: list[str], pure_refs, gate_facts=None) -> list[tuple[str, str]]:
    """新建受管文档的首次排查闸。返回 [(severity, 渲染文本)]。

    判「值不值得建 / 是否与既存文档覆盖」是判断主体的事——进程只负责把它送到动手那一刻。
    确定性流程生成的文档（generated/specs/tasks/reviews）与 aux 不在排查面。
    **档位与文案一律查 `gate_facts` 声明面**（hook 里不写死"WARN-only"这类散文档位）。
    """
    if not added:
        return []
    try:
        refs = pure_refs.find_unscreened_new_docs(WS, added)
    except Exception as exc:  # 工具坏不得阻断所有提交（与 schema gate 同口径）
        print(f"[k3dge screen] WARN: 排查闸不可用（{exc}）；跳过")
        return []
    out = []
    for code, fact in refs:
        sev = gate_facts.severity(code) if gate_facts else "block"
        text = gate_facts.render(code, {"path": fact}) if gate_facts else ""
        out.append((sev, text or f"[{code}] {fact}"))
    return out


def _load_type_schema(typ: str, pure_schema):
    """Returns (schema_dict|None, error_str|None). None schema = no gate (downstream-safe)."""
    sp = WS / "docs" / typ / ".schema.json"
    if not sp.is_file():
        return None, None
    try:
        schema = pure_schema.parse_doc_schema(sp.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"docs/{typ}/.schema.json: cannot read ({exc})"
    if schema is None:
        return None, None
    if schema.get("_invalid"):
        return None, f"docs/{typ}/.schema.json: not a JSON object"
    return schema, None


def _orphan_warnings(pure_refs) -> list[tuple[str, str, dict]]:
    """返回 [(code, 事实摘要, 结构化事实)]；档位与文案由 `gate_facts` 声明面决定。"""
    out: list[tuple[str, str, dict]] = []
    try:
        mp = WS / ".agent" / "manifest.json"
        spec_paths: list[str] = []
        if mp.is_file():
            data = json.loads(mp.read_text(encoding="utf-8"))
            for cfg in (data.get("domains") or {}).values():
                if isinstance(cfg, dict) and cfg.get("spec"):
                    spec_paths.append(str(cfg["spec"]))
        for code, fact in pure_refs.find_orphan_specs(WS, spec_paths):
            out.append((code, fact, {"path": fact}))
        for code, fact in pure_refs.find_orphan_tests(WS):
            out.append((code, fact, {"path": fact}))
        for code, fact in pure_refs.find_orphan_adrs(WS):
            out.append((code, fact, {"path": fact}))
    except Exception as exc:
        out.append(("ORPHAN_SCAN", f"skipped ({exc})", {}))
    return out


def main() -> int:
    if "--scan" in sys.argv:
        missing: list[str] = []
        for d in sorted(p for p in (WS / "docs").iterdir() if p.is_dir()):
            if not (d / "README.md").exists():
                missing.append(f"{d.relative_to(WS)}/README.md: missing")
            if not (d / AUTHORING).exists():
                missing.append(f"{d.relative_to(WS)}/{AUTHORING}: missing")
        if missing:
            print("[k3dge doc-gate] FAIL: docs subdirs missing README/AUTHORING.md:")
            for m in missing:
                print(f"  - {m}")
            return 1
        total = len([p for p in (WS / "docs").iterdir() if p.is_dir()])
        print(f"[k3dge doc-gate] PASS: {total} docs subdirs have README + AUTHORING.md")
        return 0

    rc = 0
    files = staged_files()
    doc_files = [f for f in files if f.startswith("docs/") and f.endswith(".md") and not f.endswith("/README.md")]

    # doc-gate: only when docs actually changed
    if doc_files:
        errs: list[str] = []
        for f in doc_files:
            errs.extend(check_one(f))
        if errs:
            print("[k3dge doc-gate] FAIL: type README/AUTHORING.md missing -> commit blocked")
            for e in errs:
                print(f"  - {e}")
            print("[k3dge doc-gate] add docs/<type>/README.md and AUTHORING.md, then commit")
            rc = 1
        else:
            print(f"[k3dge doc-gate] PASS: {len(doc_files)} managed doc(s) — README + AUTHORING.md present")
    else:
        print("[k3dge doc-gate] skipped (no docs changed in this commit)")

    # schema gate (stdlib-only pure checks): staged docs content
    if doc_files:
        pure_schema, pure_refs = _load_pure()
        if pure_schema is not None and pure_refs is not None:
            schema_errs, schema_warns = run_schema_gate(files, pure_schema, pure_refs, _load_gate_facts())
            for w in schema_warns:
                print(f"[k3dge schema] WARN (non-blocking): {w}")
            if schema_errs:
                print("[k3dge schema] FAIL: staged docs violate structure -> commit blocked")
                for e in schema_errs:
                    print(f"  - {e}")
                rc = 1
            else:
                print(f"[k3dge schema] PASS: {len(doc_files)} staged doc(s) structurally clean")

    # screen gate: 新增受管文档须先排查重复/覆盖（阻断一次；回执后放行）
    if doc_files:
        _ps, _pr = _load_pure()
        if _pr is not None:
            _gf = _load_gate_facts()
            screen_out = run_screen_gate(staged_added(), _pr, _gf)
            blocking = [txt for sev, txt in screen_out if sev == "block"]
            for sev, txt in screen_out:
                if sev != "block":
                    print(f"[k3dge screen] {sev.upper()}: {txt}")
            if blocking:
                print("[k3dge screen] FAIL: 新建受管文档未排查 -> commit blocked")
                for e in blocking:
                    print(f"  - {e}")
                rc = 1
            else:
                print("[k3dge screen] PASS (无待排查的新建受管文档)")

    if _MISSING_FACTS:
        # 工具自检：声明要的事实没给全 ⇒ 渲染会留字面 `{key}`。**不阻断提交**（这是我们的 bug，不是仓的）
        by_code: dict = {}
        for code, key in sorted(_MISSING_FACTS):
            by_code.setdefault(code, []).append(key)
        print("[k3dge facts] WARN: 声明要的事实未提供（渲染会留占位符；检查器或 gate_facts 需对齐）:")
        for code, keys in by_code.items():
            print(f"  - {code}: 缺 {', '.join(keys)}")
        _MISSING_FACTS.clear()

    # 一致性闸（`k3dge check`）**不在这里**：进程动作由薄壳 hook 看 `relevant_for_check()` 自己调
    # `scripts/gate.py`（本模块只出判据、不替调用方起进程）。
    return rc


if __name__ == "__main__":
    sys.exit(main())
