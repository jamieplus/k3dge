"""标记语法 v1：解析/scope 校验/边车/单主锚/结项判据/scan 兼容。"""
from __future__ import annotations

import pathlib
import tempfile
from tempfile import TemporaryDirectory

from k3dge.engine import markers as K
from k3dge.engine.milestone import scan_pending_findings

def _ws(files: dict) -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp())
    for rel, body in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8")
    return root

def test_three_hosts_and_counts():
    ws = _ws({
        "src/a.py": "# k3dit:pending A-1@line 未设超时\ndef f():\n    pass\n",
        "src/b.js": "// k3dit:fixnote F-2 顺手修了空指针\nvar x=1;\n",
        "docs/guide.md": "正文\n<!-- k3dit:disputed A-2 这不是缺陷 -->\n",
    })
    ms, problems = K.extract(ws)
    c = K.counts(ms)
    assert c["pending"] == 1 and c["fixnote"] == 1 and c["disputed"] == 1 and c["open"] == 3
    assert problems == [], problems
    ok, detail = K.closure_ok(ms)
    assert not ok and detail["blockers"]["disputed"] == 1

def test_scope_placement_rules():
    ws = _ws({"src/c.py": "# 许可头\n# k3dit:pending A-3@file 头级问题\n\ndef g():\n    pass\n",
              "src/d.py": "import os\n# k3dit:pending A-4@file 错位@file\n"})
    ms, problems = K.extract(ws)
    assert not [x for x in problems if "A-3" in x]
    assert [x for x in problems if "A-4" in x and "头部注释块" in x]


def test_prose_examples_never_self_match():
    """md 只认 <!-- --> 宿主：反引号示例绝不自触发（本仓初版栽过的坑钉成测试）。"""
    ws = _ws({"docs/w.md": "示例语法：`# k3dit:pending A-9@line 未设超时` 只是说明\n"
                           "本单涉及 `k3dit:pending T-ISO-1` 的历史证据\n"
                           "<!-- k3dit:pending A-9b 真批注 -->\n",
              "src/live.py": "def f():\n    return 1  # k3dit:pending A-10 行尾合法\n"})
    ms, _ = K.extract(ws)
    assert sorted(m.id for m in ms) == ["A-10", "A-9b"]

def test_repo_scope_only_in_sidecar_and_single_anchor():
    ws = _ws({"AUDIT.md": "## k3dit:pending A-5@repo 跨模块命名漂移\n- files: src/a.py, src/b.py\n",
              "src/a.py": "# k3dit:pending A-5 同 ID 第二锚\nx=1\n",
              "src/e.py": "# k3dit:pending A-6@repo 放错地方\ny=1\n"})
    ms, problems = K.extract(ws)
    assert [x for x in problems if "A-5" in x and "多主锚" in x]
    assert [x for x in problems if "A-6" in x and "AUDIT.md" in x]

def test_note_overflow_and_placeholder_not_matched():
    ws = _ws({"docs/x.md": "示例语法 `# k3dit:pending <ID>@line ...` 不算发现\n"
                           f"<!-- k3dit:pending A-7 {'很长' * 60} -->\n"})
    ms, problems = K.extract(ws)
    assert len(ms) == 1 and ms[0].id == "A-7"
    assert [x for x in problems if "note 超" in x]

def test_note_overflow_and_placeholder_not_matched():
    """§2.7 note 上限按 kind：pending≤500（120 放行）、其余≤80（leftover 120 报超）；占位符不自匹配。"""
    ws = _ws({"docs/x.md": "示例语法 `# k3dit:pending <ID>@line ...` 不算发现\n"
                           f"<!-- k3dit:pending A-7 {'很长' * 60} -->\n"          # 120 字 pending ≤500 → 放行
                           f"<!-- k3dit:leftover B-7 {'超长' * 60} -->\n"})         # 120 字 leftover >80 → 报超
    ms, problems = K.extract(ws)
    ids = {m.id for m in ms}
    assert {"A-7", "B-7"} <= ids and all("<" not in i for i in ids)  # 占位符不匹配
    overflow = [x for x in problems if "note 超" in x]
    assert len(overflow) == 1 and "超 80 字符" in overflow[0]        # 仅 leftover 触发（pending 未超 500）


def test_pending_note_up_to_500_ok():
    ws = _ws({"src/a.py": f"# k3dit:pending A-50 {'x' * 500}\nz=1\n"})
    ms, problems = K.extract(ws)
    assert ms and ms[0].id == "A-50" and not [p for p in problems if "note 超" in p]


def test_attrs_v2_parsed():
    """§2.7 判读四格：sev/prio/type 属性段解析回结构（闭集校验在 k3dit harvest，此处不复校）。"""
    from k3dge.engine.markers import parse_text

    ms, probs = parse_text("a.py", "code\n# k3dit:pending code-9 sev=高 prio=P1 type=复杂度 未设超时\n")
    assert ms[0].id == "code-9" and (ms[0].sev, ms[0].prio, ms[0].type) == ("高", "P1", "复杂度")
    assert ms[0].note == "未设超时" and not probs

    ms2, _ = parse_text("r.md", "<!-- k3dit:pending doc-3 sev=低 prio=P3 type=设计 摘要 -->\n")
    assert ms2[0].type == "设计" and ms2[0].note == "摘要" and ms2[0].sev == "低"


def test_scan_backward_shape_open_kinds_counted():
    ws = _ws({"src/a.py": "# k3dit:leftover A-8 有意留\nz=1\n",
              "src/f.py": "def h():\n    # k3dit:pending A-9 x\n    pass\n"})
    count, samples = scan_pending_findings(ws)
    assert count == 1 and samples == ["src/f.py#A-9"]   # leftover 不计；pending 计


def test_adjacent_pins_last_line_not_swallowed():
    from k3dge.engine.markers import parse_text

    text = "import ast\n# k3dit:pending P-1\n# k3dit:pending P-2 note here\n"
    ms, _ = parse_text("a.py", text)
    assert [(m.id, m.line) for m in ms] == [("P-1", 2), ("P-2", 3)]
    assert [m.note for m in ms] == ["", "note here"]  # note 是本行内容，不是下一行


def test_parse_text_note_cap_configurable():
    from k3dge.engine.markers import parse_text

    long_note = "x" * 120
    txt = f"# k3dit:leftover Q-1 {long_note}\n"
    _, problems = parse_text("a.py", txt)  # 默认 leftover ≤80
    assert any("超" in p for p in problems)
    _, problems2 = parse_text("a.py", txt, max_note=200)
    assert not any("超" in p for p in problems2)
