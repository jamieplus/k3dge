"""便携性：k3dge 的协议文本进入下游后，ADR 引用不得指错靶。

背景（实测）：k3dit / k3che 的 AGENTS.md 各有 4 处 ADR 引用悬空（指向 k3dge 的编号，
但两仓只有自己的 0001-0006 / 0001-0003）；`[NEXT]` 的 pointers 亦然——
下游 ADR-0004/0005 存在但是另一件事（错靶），比悬空更糟。

修法：协议文本里的裸 ADR 引用自限定为 `k3dge ADR-NNNN`；scaffold 在写入时转换。
例外：`where ADR-NNNN` 是「如何访问本仓 ADR」的示例，不限定。
"""

import tempfile
import unittest
from pathlib import Path

from k3dge.engine.nextstep import GATE_NEXT, STATE_OPTIONS, next_for_rejection
from k3dge.templates.scaffold import _QUALIFY_ADR_RE, _qualify_adr_refs, scaffold

# 裸引用检测与限定转换**共用同一把正则**（t-309）：旧 `BARE_ADR_REF` 是
# `_QUALIFY_ADR_RE` 的手抄副本（同样的 `k3dge `/`where ` 后顾 + `ADR[ -]\d{4}`），
# 转换一旦放宽（`ADR-\d{4,5}`、容忍 `**k3dge** ADR-`…）副本就是过期定义——要么放过
# 新该限定的文本、要么把已限定的正文误判违规，双向都可能。直接复用生产常量，永不分叉。
BARE_ADR_REF = _QUALIFY_ADR_RE


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
            # 只扫 `.md`/`.toml` 会漏掉其他下发文本件（`scaffold()` 写 `.gitignore` 等，ocr2-127）。
            # 扫全部文件，读不出/非文本跳过（不硬编码后缀清单，免得下发新类型又漏）。
            targets = []
            for f in sorted(t.rglob("*")):
                if not f.is_file():
                    continue
                _rel = f.relative_to(t).as_posix()
                if "docs/specs" in _rel or "docs/generated" in _rel:
                    continue
                try:
                    f.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                targets.append(f)
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
        """下游自己的 adr/README 里 `ADR-0001` 指的是本仓 ADR，不该被限定。

        按**规则**断言而不是 grep 一个串（t-306）：README 今天全靠"模板写成
        `k3dge doc where ADR-0001`、被 `where ` 例外放过"——这是巧合级保护；
        模板换成别的形状（如普通句里裸 `ADR 0002`）就会被静默改写成指向 k3dge，
        旧断言（只 grep `k3dge ADR-0001`）看不见。现在：整文件无 `k3dge ADR` 前缀
        ＋限定变换作用在 README 上**恒等**（真有跑过、也不得改写本地例）。
        """
        with tempfile.TemporaryDirectory() as d:
            t = self._scaffolded(Path(d))
            readme = (t / "docs" / "adr" / "README.md").read_text(encoding="utf-8")
            self.assertIn("ADR-0001", readme)
            self.assertNotIn("k3dge ADR", readme)
            self.assertEqual(_qualify_adr_refs(readme), readme,
                             "限定变换改动了下游 README 的本地例——保护其实依赖巧合")


class TestNextStepPointersPortability(unittest.TestCase):
    """`[NEXT]` 的显示串不得含裸 ADR 引用。

    字段名用**真实在声明的那批**（t-307）：`note/ask/if_y/if_n` 早已从
    STATE_OPTIONS 退役——旧循环 5 个名字有 4 个永远取到 None，静默只查了
    `pointers`；真正面向下游的 `fact/question/options` 一次都没被门过。
    """

    @staticmethod
    def _strings(val):
        """把任意声明值**规范化成字符串列表**（t-308）。

        旧判据只认 `list`：`tuple`/嵌套 dict 会整个容器塞进 `BARE_ADR_REF.search()`
        ⇒ `TypeError`；而 `[val] if val else []` 又会让"非空但元素非串"的容器被
        真值判断静默略过。两种形状病都使守卫假绿/假崩。"""
        if val is None:
            return []
        if isinstance(val, str):
            return [val]
        if isinstance(val, dict):
            return [x for v in val.values() for x in TestNextStepPointersPortability._strings(v)]
        if isinstance(val, (list, tuple, set, frozenset)):
            return [x for v in val for x in TestNextStepPointersPortability._strings(v)]
        return [str(val)]

    def test_no_bare_refs_in_display_strings(self):
        scanned = 0
        for state, opt in STATE_OPTIONS.items():
            for field in ("fact", "fact_blocked", "fact_with_blockers",
                          "question", "options", "pointers"):
                items = self._strings(opt.get(field))
                for s in items:
                    scanned += 1
                    self.assertIsNone(
                        BARE_ADR_REF.search(s),
                        f"{state}.{field} 含裸 ADR 引用：{s}",
                    )
        # `[NEXT]` 事实还有一块经 `next_for_rejection()` 从 `REJECTION_FACTS` 投射的同显示面，
        # 只扫 `STATE_OPTIONS` 会漏（ocr2-128）。把每个 `GATE_NEXT` 码跑一遍真路由，扫出来的串。
        for _gid in GATE_NEXT:
            try:
                _ns = next_for_rejection("M7", "被拒", gate_id=_gid)
            except Exception:
                continue
            for s in self._strings([_ns.fact, _ns.reasons, _ns.pointers]):
                scanned += 1
                self.assertIsNone(BARE_ADR_REF.search(s), f"rejection({_gid}) 含裸 ADR 引用：{s}")
        self.assertGreater(scanned, 10, f"守卫空转：只扫到 {scanned} 条串")


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
