"""脚手架镜像漂移：assets ↔ 本仓文件字节一致（仅 self_hosting，ADR-0001）。自 `ConsistencyEngine` 拆出。"""

import re
from pathlib import Path
from typing import List

from k3dge.engine.manifest import Manifest
from k3dge.engine.models import Violation
from k3dge.engine.pairs import PAIRS

_PIN_LINE_RE = re.compile(
    r"^[ \t]*(?:#|//|<!--)[ \t]*k3dit:(?:pending|leftover|disputed|fixnote|fixed)\b"
)


def _without_pins(text: str) -> str:
    """Drop whole-line k3dit marker lines so transient audit pins don't trip TEMPLATE_DRIFT.

    Pins live at the finding's location on the audit line and are harvested out by Hall before
    merge (peer_contract §8 / ADR-0025 §2.7). A pin on a byte-locked PAIRS file is an audit-time
    artifact, not drift (ADR-0004 §2.1.6), so normalize both sides before comparing.
    """
    return "\n".join(ln for ln in text.splitlines() if not _PIN_LINE_RE.match(ln))


def check_template_drift(workspace: Path, manifest: Manifest) -> List[Violation]:
    """脚手架镜像漂移：assets ↔ 本仓文件一致（仅 self_hosting=true，ADR-0001）。"""
    out: List[Violation] = []
    try:
        is_self_host = bool(getattr(manifest, "self_hosting", False))
        if is_self_host:
            # Prefer installed package assets, fallback to workspace assets for editable install
            try:
                assets_root = Path(__file__).resolve().parents[2] / "templates" / "assets"
                if not assets_root.is_dir():
                    assets_root = workspace / "src/k3dge/templates/assets"
            except Exception:
                assets_root = workspace / "src/k3dge/templates/assets"
            for asset, rel in PAIRS:
                try:
                    asset_path = assets_root / asset
                    repo_path = workspace / rel
                    # 任一侧缺失都报漂移：PAIRS 是字节锁对，"文件没了"正是门控要抓的（ocr-073）。
                    if not asset_path.is_file():
                        out.append(Violation(
                            "TEMPLATE_DRIFT", f"assets/{asset} 缺失（PAIRS 已注册）", file_path=rel,
                            detail={"asset": f"src/k3dge/templates/assets/{asset}", "repo": rel}))
                        continue
                    if not repo_path.is_file():
                        out.append(Violation(
                            "TEMPLATE_DRIFT", f"{rel} 缺失（PAIRS 已注册）", file_path=rel,
                            detail={"asset": f"src/k3dge/templates/assets/{asset}", "repo": rel}))
                        continue
                    asset_text = _without_pins(asset_path.read_text(encoding="utf-8")).rstrip("\n")
                    repo_text = _without_pins(repo_path.read_text(encoding="utf-8")).rstrip("\n")
                    if asset_text != repo_text:
                        out.append(
                            Violation(
                                "TEMPLATE_DRIFT",
                                f"assets/{asset} != {rel}",
                                file_path=rel,
                                detail={"asset": f"src/k3dge/templates/assets/{asset}", "repo": rel},
                            )
                        )
                except (OSError, UnicodeDecodeError) as exc:
                    # 读不出/坏编码就 `continue` ⇒ 锁对的那一半静默失守，漂移闸假绿（ocr2-248）。
                    out.append(Violation(
                        "TEMPLATE_DRIFT", f"{rel} 不可读（{type(exc).__name__}）⇒ 无法比对字节锁",
                        file_path=rel,
                        detail={"asset": f"src/k3dge/templates/assets/{asset}", "repo": rel}))
                    continue
            # Budget warning: AGENTS.md microkernel should stay <80 lines (self-host only, not a gate)
            try:
                agent_tpl = assets_root / "agents.md"
                if agent_tpl.is_file():
                    n_lines = len(agent_tpl.read_text(encoding="utf-8").splitlines())
                    if n_lines > 80:
                        import sys

                        print(
                            f"[WARN] AGENTS.md template exceeds micro-kernel budget: {n_lines} > 80 lines",
                            file=sys.stderr,
                        )
            except Exception:
                pass
    except Exception as exc:
        out.append(
            Violation(
                "TEMPLATE_DRIFT",
                f"check failed: {exc}",
                file_path="src/k3dge/engine/pairs.py",
                detail={"asset": "src/k3dge/templates/assets/", "repo": f"比对未完成：{exc}"},
            )
        )
    return out
