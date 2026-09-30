"""便携性：k3dge 的协议文本进入下游后，ADR 引用不得指错靶。

背景（实测）：k3dit / k3che 的 AGENTS.md 各有 4 处 ADR 引用悬空（指向 k3dge 的编号，
但两仓只有自己的 0001-0006 / 0001-0003）；`[NEXT]` 的 pointers 亦然——
下游 ADR-0004/0005 存在但是另一件事（错靶），比悬空更糟。

修法：协议文本里的裸 ADR 引用自限定为 `k3dge ADR-NNNN`；scaffold 在写入时转换。
例外：`where ADR-NNNN` 是「如何访问本仓 ADR」的示例，不限定。
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.nextstep import STATE_OPTIONS
from k3dge.templates.scaffold import _qualify_adr_refs, scaffold

# 裸引用 = ADR-NNNN / ADR NNNN，且前面不是 `k3dge ` 或 `where `
BARE_ADR_REF = re.compile(r"(?<!k3dge )(?<!where )ADR[ -]\d{4}")


class TestScaffoldProtocolPortability(unittest.TestCase):
    """下游仓出生即不得带裸 ADR 引用。"""

    def _scaffolded(self, d: Path) -> Path:
        t = d / "r"
        t.mkdir()
        scaffold(t, name="r")
        return t

    def test_protocol_texts_have_no_bare_adr_refs(self):
        with tempfile.TemporaryDirectory() as d:
            t = self._scaffolded(Path(d))
            # 旧清单只列 3 份，而 `scaffold()` 实际对**十余份**下发件跑 `_qualify_adr_refs`
            # （docs.toml / pipeline.toml / guides/{mcp-bridge,downstream} / protocols/*3 /
            # architecture/overview / adr/README…）⇒ 覆盖洞（t-305）。改成扫整棵下发树。
            targets = [f for f in sorted(t.rglob("*"))
                       if f.is_file() and f.suffix in {".md", ".toml"}
                       and "docs/specs" not in f.relative_to(t).as_posix()
                       and "docs/generated" not in f.relative_to(t).as_posix()]
            assert len(targets) >= 12, f"下发面缩水，本测试失去覆盖：{len(targets)}"
            for f in targets:
                text = f.read_text(encoding="utf-8")
                for m in BARE_ADR_REF.finditer(text):
                    seg = text[max(0, m.start() - 30) : m.end() + 10].replace("\n", " ")
                    self.fail(f"{f.relative_to(t)}: 裸 ADR 引用 …{seg}…（下游会指错靶）")

    def test_where_command_example_stays_bare(self):
        """`k3dge doc where ADR-0001` 是访问本仓 ADR 的示例，不该被限定。"""
        with tempfile.TemporaryDirectory() as d:
            t = self._scaffolded(Path(d))
            self.assertIn("where ADR-0001", (t / "AGENTS.md").read_text(encoding="utf-8"))

    def test_adr_readme_local_example_untouched(self):
        """下游自己的 adr/README 里 `ADR-0001` 指的是本仓 ADR，不该被限定。"""
        with tempfile.TemporaryDirectory() as d:
            t = self._scaffolded(Path(d))
            readme = (t / "docs" / "adr" / "README.md").read_text(encoding="utf-8")
            self.assertIn("ADR-0001", readme)
            self.assertNotIn("k3dge ADR-0001", readme)


class TestNextStepPointersPortability(unittest.TestCase):
    """`[NEXT]` 的显示串（pointers/note/ask/if_y/if_n）不得含裸 ADR 引用。"""

    def test_no_bare_refs_in_display_strings(self):
        for state, opt in STATE_OPTIONS.items():
            for field in ("pointers", "note", "ask", "if_y", "if_n"):
                val = opt.get(field)
                items = val if isinstance(val, list) else ([val] if val else [])
                for s in items:
                    self.assertIsNone(
                        BARE_ADR_REF.search(s),
                        f"{state}.{field} 含裸 ADR 引用：{s}",
                    )


class TestQualifyTransform(unittest.TestCase):
    def test_qualifies_design_refs(self):
        self.assertEqual(_qualify_adr_refs("见 ADR-0006 §2"), "见 k3dge ADR-0006 §2")
        self.assertEqual(_qualify_adr_refs("（ADR 0010）"), "（k3dge ADR 0010）")

    def test_qualifies_backticked_design_ref(self):
        """反引号包着的设计引用也要限定（与命令示例不同）。"""
        self.assertEqual(_qualify_adr_refs("（`ADR-0012`）"), "（`k3dge ADR-0012`）")

    def test_skips_where_command(self):
        s = "`k3dge doc where ADR-0001`"
        self.assertEqual(_qualify_adr_refs(s), s)

    def test_no_double_qualify(self):
        s = "k3dge ADR-0006"
        self.assertEqual(_qualify_adr_refs(s), s)

    def test_idempotent(self):
        once = _qualify_adr_refs("a ADR-0001 b ADR 0002 c")
        self.assertEqual(_qualify_adr_refs(once), once)


if __name__ == "__main__":
    unittest.main()
