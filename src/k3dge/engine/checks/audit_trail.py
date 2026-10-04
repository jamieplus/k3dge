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
    if isinstance(func, ast.Attribute) and func.attr == "write_text":
        if _logs_literal(node):
            return "对 logs/ 的 write_text 覆写：审计痕迹只可追加（ADR-0008），改用追加写入。"
        return ""
    # `open` 两种形态：`Path(...).open(...)`（Attribute，路径在**接收者** `func.value`）与
    # `open(...)`（Name，路径在 args[0] 或 `file=`）。旧实现一律取 `node.args[0]` ⇒ 前者把
    # 模式串当路径、后者 `open(file=...)` 因 args 为空被跳过，都漏报（ocr3）。
    if isinstance(func, ast.Attribute) and func.attr == "open":
        target = func.value
        mode = (node.args[0] if node.args else None) or \
            next((kw.value for kw in node.keywords if kw.arg == "mode"), None)
    elif isinstance(func, ast.Name) and func.id == "open":
        target = (node.args[0] if node.args else None) or \
            next((kw.value for kw in node.keywords if kw.arg == "file"), None)
        mode = (node.args[1] if len(node.args) > 1 else None) or \
            next((kw.value for kw in node.keywords if kw.arg == "mode"), None)
    else:
        return ""
    if target is None:
        return ""
    m = mode.value if isinstance(mode, ast.Constant) and isinstance(mode.value, str) else None
    # 覆写/独占创建（仅 'a' 才按追加算）：写入模式含 'w' 或独占 'x' 都算非追加写入。
    # 故 'x' 与 'w' 同属标红（测试 test_flags_logs_exclusive_mode_x 钉正）。'x' 虽能防重写已有
    # 文件，但它仍写了一个新文件并跳过追加语义，仍视为对审计痕迹的非追加入侵。
    if m is not None and any(c in m for c in "wx") and _logs_literal(target):
        return "对 logs/ 的 open(...,'w' 或 独占 'x')写入：审计痕迹只可追加（ADR-0008），改用 'a'。"
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
