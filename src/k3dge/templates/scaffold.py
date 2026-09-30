"""Scaffold generator, invoked by `k3dge-init.sh`."""

from __future__ import annotations

import json
import re
import stat
import sys
from importlib import resources
from pathlib import Path
from typing import Optional, Sequence


def _asset(*parts: str) -> str:
    node = resources.files(__package__) / "assets"
    for part in parts:
        node = node / part
    return node.read_text(encoding="utf-8")


AGENTS_TEMPLATE = _asset("agents.md")

# 协议文本里的裸 `ADR-NNNN` → 自限定为 `k3dge ADR-NNNN`。
# 这些文本会原样进入下游仓；裸引在那里会指向下游【自己的】同名 ADR（错靶）
# 或不存在（悬空）。例外：`where ADR-NNNN` 是「如何访问本仓 ADR」的示例，不限定。
_QUALIFY_ADR_RE = re.compile(r"(?<!k3dge )(?<!where )ADR([ -])(\d{4})")


def _qualify_adr_refs(text: str) -> str:
    """把协议文本里的裸 ADR 引用自限定为 k3dge 的（下游不自带 k3dge 的 ADR）。"""
    return _QUALIFY_ADR_RE.sub(lambda m: f"k3dge ADR{m.group(1)}{m.group(2)}", text)

SPEC_TEMPLATE = _asset("spec.md.template")

GATE_SH_TEMPLATE = _asset("gate.sh")

GATE_PY_TEMPLATE = _asset("gate.py")

GATE_PS1_TEMPLATE = _asset("gate.ps1")

K3DGE_INIT_SH_TEMPLATE = _asset("init.sh")

K3DGE_INIT_WRAPPER = _asset("k3dge-init-wrapper.sh")

K3DGE_INIT_PS1_WRAPPER = _asset("k3dge-init-wrapper.ps1")

INIT_PS1_TEMPLATE = _asset("init.ps1")

DOCS_TOML_TEMPLATE = _asset("docs.toml.template")

PIPELINE_TOML_TEMPLATE = _asset("pipeline.toml.template")

GENERATE_DOCS_SH_TEMPLATE = _asset("generate-docs.sh")

GENERATE_DOCS_PS1_TEMPLATE = _asset("generate-docs.ps1")

PRE_COMMIT_TEMPLATE = _asset("pre-commit.yaml.template")
PRE_COMMIT_HOOK_TEMPLATE = _asset("pre-commit")
COMMIT_MSG_HOOK_TEMPLATE = _asset("commit-msg")

ARCHITECTURE_TEMPLATE = _asset("architecture.md.template")

REVIEWS_README_TEMPLATE = _asset("reviews-readme.md")

MCP_BRIDGE_TEMPLATE = _asset("mcp-bridge.md.template")

GITIGNORE_TEMPLATE = _asset("gitignore.template")

ADR_README_TEMPLATE = _asset("adr-readme.md.template")

DOWNSTREAM_GUIDE_TEMPLATE = _asset("downstream.md")

PROTOCOL_TEMPLATE = _asset("protocols/audit_default.md")
VERIFY_PROTOCOL_TEMPLATE = _asset("protocols/verify_default.md")
QUALITY_PROTOCOL_TEMPLATE = _asset("protocols/quality_default.md")

TASKS_README_TEMPLATE = _asset("tasks-readme.md")

BRANCHES_README_TEMPLATE = _asset("branches-readme.md")

MEMO_README_TEMPLATE = _asset("memo-readme.md")

RULE_ASSETS = (
    "00-core-discipline.md",
    "01-docs-structure.md",
    "02-simplification.md",
    "03-self-contained.md",
    "04-milestone.md",
    "05-branches.md",
    "06-memo.md",
    "07-audit.md",
    "08-design-discipline.md",
    "09-absorption.md",
    "10-structure-over-prose.md",
    "11-next-sidecar.md",
    "12-introduction-discipline.md",
)

def _slug(raw: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]+", "_", raw.strip()).strip("_").lower()
    if not s:
        s = "app"
    if s[0].isdigit():
        s = "p_" + s
    return s


def _first_domain_manifest(name: str) -> dict:
    return {
        "name": name,
        "version": "0.1.0",
        "self_hosting": False,
        "package_root": "src",
        "domains": {
            name: {
                "src": f"src/{name}",
                "spec": f"docs/specs/{name}/spec.md",
                "tests": f"tests/unit/{name}",
                "description": name,
            }
        },
        "ignore": [],
    }


def _write_if_missing(path: Path, content: str, executable: bool = False) -> bool:
    if path.exists():
        # 已存在也要**补执行位**：跨文件系统拷贝/checkout 丢 mode/umask 之后，重复跑 init
        # 永远修不回 `scripts/gate.sh`、两个 hook、`k3dge-init.sh`（368）。
        if executable:
            try:
                path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except OSError as exc:
                print(f"[k3dge scaffold] WARN: 补执行位失败 {path}（{exc}）", file=sys.stderr)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return True


def ensure_mcp_config(target: Path) -> bool:
    """Idempotently merge k3dge (and pipeline-enabled peers) into .mcp.json.

    Returns True if config is valid/merged, False if existing file is corrupted (with stderr warning).
    Public API for cli.mcp sync; templates spec contracts this symbol.

    Write-side parse stays here: templates ↛ engine (ADR-0001). Read-side host is
    `k3dge.engine.mcp_json` (cli + engine).
    """
    import sys

    mcp_path = target / ".mcp.json"
    # Load existing or start empty; corrupted JSON or non-dict root must not silently destroy peers
    data: dict = {}
    if mcp_path.is_file():
        try:
            raw = mcp_path.read_text(encoding="utf-8")
            loaded = json.loads(raw)
            if not isinstance(loaded, dict):
                print(f"[WARN] .mcp.json is not a JSON object ({mcp_path}), skipped to avoid overwriting peers", file=sys.stderr)
                return False
            data = loaded
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"[WARN] .mcp.json corrupted ({mcp_path}): {exc}, skipped to avoid overwriting peers", file=sys.stderr)
            return False
    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
        data["mcpServers"] = {}
    # k3dge is always present (framework); peers from pipeline.toml are merged
    # on demand via `k3dge mcp sync` (not scaffold time).
    if "k3dge" not in data["mcpServers"]:
        if (target / "src" / "k3dge").is_dir():
            data["mcpServers"]["k3dge"] = {
                "command": "python",
                "args": ["-m", "k3dge.cli.mcp"],
                "env": {"PYTHONPATH": "src"},
            }
        else:
            data["mcpServers"]["k3dge"] = {
                "command": "python",
                "args": ["-m", "k3dge.cli.mcp"],
            }
        # Atomic write via temp file
        tmp = mcp_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(mcp_path)
    return True


def _pipeline_servers(target: Path) -> set:
    """Server names the generated pipeline references（`roles.*.bind` ∪ `[peers.*]`，除 k3dge）。"""
    import sys

    p = target / ".agent" / "pipeline.toml"
    if not p.is_file():
        return set()
    try:
        if sys.version_info >= (3, 11):
            import tomllib as _toml
        else:
            import tomli as _toml  # type: ignore
    except ImportError as exc:
        print(f"[k3dge scaffold] WARN: 无 TOML 解析器（{exc}）⇒ peer stubs 不写，出生即红有线索（369）",
              file=sys.stderr)
        return set()
    try:
        data = _toml.loads(p.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"[k3dge scaffold] WARN: 读不到 {p}（{exc}）⇒ peer stubs 不写", file=sys.stderr)
        return set()
    except UnicodeDecodeError as exc:
        print(f"[k3dge scaffold] WARN: {p} 不是 UTF-8（{exc}）⇒ peer stubs 不写", file=sys.stderr)
        return set()
    except ValueError as exc:      # TOML 语法错：静默空集 = 下游出生即红且无线索（369）
        print(f"[k3dge scaffold] WARN: {p} 解析失败（{exc}）⇒ peer stubs 不写", file=sys.stderr)
        return set()
    except Exception as exc:  # pragma: no cover - 解析器实现差异
        print(f"[k3dge scaffold] WARN: {p} 解析异常（{type(exc).__name__}: {exc}）⇒ peer stubs 不写",
              file=sys.stderr)
        return set()
    names = set()
    for r in (data.get("roles") or {}).values():
        b = r.get("bind") if isinstance(r, dict) else None
        if isinstance(b, str) and b:
            names.add(b)
    names |= set((data.get("peers") or {}).keys())
    names.discard("k3dge")
    return names


def _ensure_peer_stubs(target: Path) -> None:
    """把 pipeline 绑定的 peer 以 stub 写进 `.mcp.json`，使 scaffold 出生不因 peer 未登记而红。

    只声明（command=python/`-m <peer>.mcp`/PYTHONPATH=../<peer>/src）；真接线由 `k3dge mcp sync`。
    不替下游决定绑谁——stub 仅消除「pipeline 绑定 vs .mcp.json 未登记」的出生红。
    """
    names = _pipeline_servers(target)
    if not names:
        return
    mcp_path = target / ".mcp.json"
    if mcp_path.is_file():
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return          # 损坏 ⇒ 不覆盖（否则静默清空对端 MCP 配置，ocr-136）
        if not isinstance(data, dict):
            return
    else:
        data = {"mcpServers": {}}
    servers = data.setdefault("mcpServers", {})
    changed = False
    for name in sorted(names):
        if name in servers:
            continue
        servers[name] = {"command": "python", "args": ["-m", f"{name}.mcp"],
                         "env": {"PYTHONPATH": f"../{name}/src"}}
        changed = True
    if changed:
        tmp = mcp_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(mcp_path)


def _ensure_first_domain(target: Path, name: str, today: str) -> list:
    """Write or upgrade an empty manifest so the gate has at least one domain.

    返回**问题清单**（空＝没问题）：以前解析失败静默 `return` ⇒ init 报成功而域脚手架没铺（370）。
    """
    path = target / ".agent" / "manifest.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            msg = f".agent/manifest.json 读不出（{type(exc).__name__}: {exc}）⇒ 不猜内容，域脚手架未铺"
            print(f"[k3dge scaffold] FAIL: {msg}", file=sys.stderr)
            return [msg]
        if not isinstance(data, dict):
            msg = f".agent/manifest.json 顶层不是对象（{type(data).__name__}）⇒ 不动它，域脚手架未铺"
            print(f"[k3dge scaffold] FAIL: {msg}", file=sys.stderr)
            return [msg]
        if data.get("domains"):
            return []
        fresh = _first_domain_manifest(name)
        # **保用户键**：旧实现整份覆盖 ⇒ `package_root`/`ignore`/`version`/`self_hosting`
        # 被默认值抹掉（下游按 docs 改过一次 init 就丢，371）
        merged = dict(data)
        merged.setdefault("package_root", fresh["package_root"])
        merged.setdefault("ignore", fresh["ignore"])
        merged.setdefault("version", fresh["version"])
        merged.setdefault("self_hosting", fresh["self_hosting"])
        # `name` 走调用方意图（`--name`/目录名）：这条路只在"没有任何域"时进，且 init 的
        # 语义＝"我要把这个项目命名/铺成 name"；其余用户键一律保留（371）
        merged["name"] = name
        merged["domains"] = fresh["domains"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    else:
        _write_if_missing(path, json.dumps(_first_domain_manifest(name), indent=2) + "\n")
    spec = SPEC_TEMPLATE.replace("<domain>", name)
    spec = re.sub(r"(\*\*Last Updated\*\*:).*", rf"\1 {today}", spec)
    _write_if_missing(target / "src" / name / "__init__.py", f'__version__ = "0.1.0"\n')
    _write_if_missing(target / "docs" / "specs" / name / "spec.md", spec)
    _write_if_missing(
        target / "tests" / "unit" / name / "test_smoke.py",
        'def test_smoke() -> None:\n    assert True\n',
    )
    return []


def scaffold(target: Path, name: str | None = None) -> list:
    """铺脚手架。返回**问题清单**（空＝干净）；调用方（`k3dge init`）据此决定退出码。"""
    import datetime

    target.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    slug = _slug(name or target.name)

    _write_if_missing(target / "AGENTS.md", _qualify_adr_refs(AGENTS_TEMPLATE))
    problems: list = list(_ensure_first_domain(target, slug, today))
    for rule_file in RULE_ASSETS:
        _write_if_missing(
            target / ".agent" / "rules" / rule_file,
            _qualify_adr_refs(_asset("rules", rule_file)),
        )
    _write_if_missing(target / ".agent" / "README.md", _qualify_adr_refs(_asset("agent-readme.md")))
    _write_if_missing(target / ".agent" / "extractors" / "README.md", _asset("extractors-readme.md"))
    _write_if_missing(
        target / ".agent" / "extractors.toml",
        "# Extractor plugins: enabled languages (builtin table in engine/extractor_gen.py).\n"
        "# Custom languages: add [languages.<name>] table (see .agent/extractors/README.md).\n"
        'enable = ["typescript"]\n',
    )
    _write_if_missing(target / ".agent" / "milestone", "M0\n")
    # 5 个此前缺治理件的类型（doc-gate 要求每个 docs/<type>/ 齐 README + AUTHORING）
    for _type in ("specs", "guides", "protocols", "architecture", "generated"):
        _d = target / "docs" / _type
        _d.mkdir(parents=True, exist_ok=True)
        _write_if_missing(_d / "README.md", _asset(f"{_type}/README.md"))
        _write_if_missing(_d / "AUTHORING.md", _asset(f"{_type}/AUTHORING.md"))
    _write_if_missing(
        target / "docs" / "specs" / "_template" / "spec.md",
        SPEC_TEMPLATE,
    )
    _write_if_missing(target / ".pre-commit-config.yaml", PRE_COMMIT_TEMPLATE)
    _write_if_missing(target / "scripts" / "gate.sh", GATE_SH_TEMPLATE, executable=True)
    _write_if_missing(target / "scripts" / "gate.py", GATE_PY_TEMPLATE, executable=True)
    _write_if_missing(target / "scripts" / "gate.ps1", GATE_PS1_TEMPLATE)
    _write_if_missing(target / "scripts" / "init.sh", K3DGE_INIT_SH_TEMPLATE, executable=True)
    _write_if_missing(target / "scripts" / "init.ps1", INIT_PS1_TEMPLATE)
    _write_if_missing(target / "k3dge-init.sh", K3DGE_INIT_WRAPPER, executable=True)
    _write_if_missing(target / "k3dge-init.ps1", K3DGE_INIT_PS1_WRAPPER)

    (target / "docs" / "adr").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "adr" / "README.md", ADR_README_TEMPLATE)
    _write_if_missing(target / "docs" / "adr" / "AUTHORING.md", _asset("adr/AUTHORING.md"))
    _write_if_missing(target / "docs" / "adr" / ".schema.json", _asset("adr/.schema.json"))
    (target / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "tasks" / "README.md", TASKS_README_TEMPLATE)
    _write_if_missing(target / "docs" / "tasks" / "AUTHORING.md", _asset("tasks/AUTHORING.md"))
    _write_if_missing(target / "docs" / "tasks" / ".schema.json", _asset("tasks/.schema.json"))
    _write_if_missing(target / "docs" / "tasks" / "_template.md", _asset("tasks/_template.md"))
    _write_if_missing(target / "docs" / "memo" / "_template.md", _asset("memo/_template.md"))
    _write_if_missing(target / "docs" / "branches" / "_template.md", _asset("branches/_template.md"))
    _write_if_missing(target / "docs" / "adr" / "_template.md", _asset("adr/_template.md"))
    (target / "docs" / "adr" / "obsolete").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "guides").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "guides" / "mcp-bridge.md", _qualify_adr_refs(MCP_BRIDGE_TEMPLATE))
    _write_if_missing(target / "docs" / "guides" / "downstream.md", _qualify_adr_refs(DOWNSTREAM_GUIDE_TEMPLATE))
    (target / "docs" / "protocols").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "protocols" / "audit_default.md", _qualify_adr_refs(PROTOCOL_TEMPLATE))
    _write_if_missing(target / "docs" / "protocols" / "verify_default.md", _qualify_adr_refs(VERIFY_PROTOCOL_TEMPLATE))
    _write_if_missing(target / "docs" / "protocols" / "quality_default.md", _qualify_adr_refs(QUALITY_PROTOCOL_TEMPLATE))
    (target / "docs" / "generated").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "branches").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "branches" / "README.md", BRANCHES_README_TEMPLATE)
    _write_if_missing(target / "docs" / "branches" / "AUTHORING.md", _asset("branches/AUTHORING.md"))
    _write_if_missing(target / "docs" / "branches" / ".schema.json", _asset("branches/.schema.json"))
    (target / "logs").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "reviews").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "reviews" / "README.md", REVIEWS_README_TEMPLATE)
    _write_if_missing(target / "docs" / "reviews" / "AUTHORING.md", _asset("reviews/AUTHORING.md"))
    _write_if_missing(target / "docs" / "reviews" / "LEFTOVERS.md", _asset("reviews/LEFTOVERS.md"))
    _write_if_missing(target / ".gitignore", GITIGNORE_TEMPLATE)
    (target / "docs" / "memo").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "memo" / "archive").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "memo" / "README.md", MEMO_README_TEMPLATE)
    _write_if_missing(target / "docs" / "memo" / "AUTHORING.md", _asset("memo/AUTHORING.md"))
    _write_if_missing(target / "docs" / "memo" / ".schema.json", _asset("memo/.schema.json"))
    _write_if_missing(target / "docs" / "architecture" / "overview.md", _qualify_adr_refs(ARCHITECTURE_TEMPLATE))
    _write_if_missing(target / ".agent" / "docs.toml", DOCS_TOML_TEMPLATE)
    _write_if_missing(target / ".agent" / "pipeline.toml", PIPELINE_TOML_TEMPLATE)
    if not ensure_mcp_config(target):   # 旧实现丢掉这个 bool ⇒ `.mcp.json` 没合并也报成功（372）
        problems.append(".mcp.json 未合并（已有文件损坏/形状不对，见上方 WARN）")
    _ensure_peer_stubs(target)
    # git hooks：这两件此前**不在资产里** ⇒ 下游 init 后照 AGENTS.md 激活 hooks 会被 git 静默跳过
    _write_if_missing(target / "scripts" / "pre-commit", PRE_COMMIT_HOOK_TEMPLATE, executable=True)
    _write_if_missing(target / "scripts" / "commit-msg", COMMIT_MSG_HOOK_TEMPLATE, executable=True)
    _write_if_missing(target / "scripts" / "generate-docs.sh", GENERATE_DOCS_SH_TEMPLATE, executable=True)
    _write_if_missing(target / "scripts" / "generate-docs.ps1", GENERATE_DOCS_PS1_TEMPLATE)
    return problems


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="k3dge.templates.scaffold")
    parser.add_argument("target", nargs="?", default=".", help="target project root")
    parser.add_argument("--name", dest="name", default=None, help="project/domain slug (default: directory name)")
    args = parser.parse_args(argv)
    problems = scaffold(Path(args.target).resolve(), name=args.name)
    if problems:
        print(f"[k3dge init] 完成但有 {len(problems)} 项未落：", file=sys.stderr)
        for m in problems:
            print(f"  - {m}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
