"""`ADR-0008` 审计痕迹只可追加：静态扫 `src/**` 的覆写式写入。自 `ConsistencyEngine` 拆出。"""

import ast
from pathlib import Path
from typing import List

from k3dge.engine.models import Violation


def _logs_literal(node) -> bool:
    # 只看**写入目标**侧的字面量：`Path("README.md").write_text("logs")` 的内容参数含 "logs"
    # 并不代表写进 logs/；旧实现扫整个调用节点的全部字符串常量 ⇒ 误报（ocr-241）。
    # 调用方也会传非 Call 的表达式（BinOp/Constant 目标）⇒ 先收类型再取 .func。
    def _hits(expr) -> bool:
        for sub in ast.walk(expr):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                v = sub.value.replace("\\", "/")
                if "logs" in v.split("/") or v.startswith("logs/"):
                    return True
        return False

    if not isinstance(node, ast.Call):
        return _hits(node)                   # 传进来的可能直接就是目标表达式
    f = node.func
    if isinstance(f, ast.Attribute):           # Path("...").write_text(...) / open(...).write(...)
        return _hits(f.value)
    if isinstance(f, ast.Name) and f.id == "open":
        return bool(node.args) and _hits(node.args[0])
    return False


def _logs_overwrite(node) -> str:
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else "")
    if name == "write_text" and _logs_literal(node):
        return "对 logs/ 的 write_text 覆写：审计痕迹只可追加（ADR-0008），改用追加写入。"
    if name == "open" and node.args:
        target = node.args[0]
        mode = node.args[1] if len(node.args) > 1 else None
        if mode is None:
            mode = next((kw.value for kw in node.keywords if kw.arg == "mode"), None)
        wr = isinstance(mode, ast.Constant) and isinstance(mode.value, str) and any(c in mode.value for c in "wx")
        if _logs_literal(target) and wr:
            return "对 logs/ 的 open(...,'w') 覆写：审计痕迹只可追加（ADR-0008），改用 'a'。"
    return ""


def check_audit_trail(workspace: Path) -> List[Violation]:
    """`ADR-0008`：审计痕迹只可追加。静态扫 `src/**` 里对 `logs/` 的**覆写式**写入（write_text / open 'w'）。

    只判盘上事实（AST 字符串常量 + 写模式），不跑进程。追加式（`open(...,'a')` / 无 `write_text`）不报。
    """
    src = workspace / "src"
    out: List[Violation] = []
    if not src.is_dir():
        return out
    for path in src.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError):
            continue
        rel = path.relative_to(workspace).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            msg = _logs_overwrite(node)
            if msg:
                out.append(Violation("AUDIT_TRAIL_APPEND_ONLY", msg, file_path=rel,
                                     detail={"path": rel, "reason": msg}))
    return out
