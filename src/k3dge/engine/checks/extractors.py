"""`.agent/extractors/<lang>.py` 与 `extractors.toml` 的当前渲染一致性。自 `ConsistencyEngine` 拆出。"""

from pathlib import Path
from typing import List

from k3dge.engine.models import Violation


def check_extractor_plugins(workspace: Path) -> List[Violation]:
    """`.agent/extractors/<lang>.py` 必须是 `.agent/extractors.toml` 的**当前渲染**（改了配置没 sync ⇒ 静默用过时插件）。"""
    try:
        from k3dge.engine import extractor_gen

        ws = workspace
        if not ((ws / ".agent" / "extractors.toml").is_file() or (ws / ".agent" / "extractors").is_dir()):
            return []
        missing = []
        for name, row in extractor_gen.resolve_languages(ws).items():
            dest = ws / extractor_gen.PLUGDIR_REL / f"{name}.py"
            want = extractor_gen.render_plugin(name, row)
            got = dest.read_text(encoding="utf-8") if dest.is_file() else None
            if got != want:
                missing.append(name)
        if not missing:
            return []
        return [
            Violation(
                "EXTRACTOR_PLUGIN_STALE",
                f"plugin drift: {missing}",
                file_path=extractor_gen.PLUGDIR_REL,
                detail={"path": extractor_gen.PLUGDIR_REL, "languages": missing},
            )
        ]
    except Exception as exc:
        return [
            Violation(
                "EXTRACTOR_PLUGIN_STALE",
                f"extractor plugin check crashed: {exc}",
                file_path=".agent/extractors",
                detail={"path": ".agent/extractors", "languages": "（校验崩溃，未定位）",
                        "reason": str(exc)},
            )
        ]
