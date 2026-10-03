
import pathlib
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.protocol import write_incident


def _repo_root() -> pathlib.Path:
    """ocr2-772：`parents[3]` 把文件深度焊死——挪一层就静默指错，前置断言报
     confusing 的"文件不在"而非"根找错了"。改走标记反查（pyproject ∧ src/k3dge）。"""
    here = pathlib.Path(__file__).resolve()
    for cand in (here, *here.parents):
        if ((cand / "pyproject.toml").is_file() and (cand / "src" / "k3dge").is_dir()):
            return cand
    raise AssertionError(f"从 {here} 向上找不到 k3dge 仓根——别把本文件搬出 tests/**/")


class TestWriteIncident(unittest.TestCase):
    def test_write_incident_creates_human_visible_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            # （t-228）旧的 `.agent/manifest.json` 布置是死的：`write_incident` 不读 manifest，
            # 形闸由 `docs/incidents/.schema.json` 驱动——留着让人误以为协议写入有 manifest 依赖。
            path = write_incident(
                root,
                target="docs/reviews/x.md",
                task_type="audit",
                task_id="T1",
                detail="agent ignored the gate",
            )
            self.assertTrue(path.exists())
            self.assertTrue(path.name.endswith(".md"))
            # 落点必须是 `docs/incidents/`（t-227）：`INCIDENT_FORM_INVALID` 只在那里找受管件；
            # 写去别处＝人看不见、闸也查不到——"文件存在"证明不了"在正确的位置"。
            self.assertEqual(path.parent.relative_to(root), pathlib.PurePath("docs/incidents"))
            text = path.read_text(encoding="utf-8")
            self.assertIn("agent ignored the gate", text)
            self.assertIn("docs/reviews/x.md", text)

    def test_write_incident_satisfies_form_gate(self) -> None:
        """用**权威 schema** 对账（t-229），不再抄一份 fixture 副本：

        旧形状伸手抓别的测试类的私有 helper（`TestIncidentGovernance()._schema`），而它写的是
        `docs/incidents/.schema.json` 的**硬编码拷贝**——ship 的 schema 加一条规则（新必需节、
        frontmatter、h1 形状），真 `k3dge check` 会红，这个测仍绿：证明的是"与副本相容"，
        不是"与判据相容"。现在直接复制仓内权威 schema 进沙箱；权威 schema 不存在＝前置红。
        """
        import shutil

        from k3dge.engine.doc_catalog import iter_managed_files, validate_docs

        schema_src = _repo_root() / "docs" / "incidents" / ".schema.json"
        self.assertTrue(schema_src.is_file(), f"权威 schema 不在：{schema_src}")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            # t-228：manifest 布置同样多余（validate_docs(types=["incidents"]) 不解析 manifest）
            (root / "docs" / "incidents").mkdir(parents=True)
            shutil.copyfile(schema_src, root / "docs" / "incidents" / ".schema.json")
            inc = write_incident(root, target="x.md", task_type="audit", task_id="T1", detail="boom")
            # ocr2-511：正对照——沙箱 incident 必须真在受管面里，否则 [] 可能是"没查"而非"合格"。
            managed = {p.name for p in iter_managed_files(root, "incidents")}
            self.assertIn(inc.name, managed,
                          f"沙箱 incident 没进受管面，[] 是'什么都没查'：{managed}")
            vs = validate_docs(root, types=["incidents"])
            self.assertEqual(vs, [], [f"{v.rule_id}: {v.message}" for v in vs])
            # 负对照——把文件弄坏，证明这个沙箱里的闸**能红**（否则上面的绿无意义）
            inc.write_text("# Incidents\n", encoding="utf-8")
            vs_bad = validate_docs(root, types=["incidents"])
            self.assertTrue(vs_bad, "坏 incident 在此沙箱仍绿 ⇒ 这条'合格'断言测不到 schema")


class TestIncidentSlugAndSanitize(unittest.TestCase):
    """`write_incident` 的文件名与外部文本净化（ocr-291/292/293）。"""

    def _inc(self, **kw):

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = write_incident(root, **kw)
            return path.name, path.read_text(encoding="utf-8")

    def test_very_long_target_stays_inside_filename_limit(self) -> None:
        name, _ = self._inc(target="x" * 500, task_type="audit", task_id="T1", detail="boom")
        self.assertLessEqual(len(name.encode()), 255)
        self.assertTrue(name.endswith(".md"))

    def test_dots_in_target_do_not_break_the_filename_rule(self) -> None:
        # docs/incidents/.schema.json: ^INC-\d{8}-[\w-]+\.md$ —— 中间段不接受点号
        name, _ = self._inc(target="release.archive.tar.gz", task_type="audit",
                            task_id="T1", detail="boom")
        self.assertRegex(name, r"^INC-\d{8}-protocol-[\w-]+\.md$")

    def test_external_detail_cannot_forge_the_b_t_d_headings(self) -> None:
        r"""顶格**和缩进**两种伪造都要拦（t-232）：sanitizer 旧判据 `startswith("#")` 放过了
        `   ## 2. …`——markdown 认 ≤3 空格缩进的标题，人在 GitHub 上仍看到假 H2。
        计数口径也升级为 `^\s*##`（只看 0 列的旧计数正好看不见缩进伪造）。"""
        detail = ("真现象\n\n## 2. 我伪造的根因\n\n   ## 2. 缩进版伪造\n\n"
                  "- **Path**: /etc/passwd\n- **Status**: Resolved\n")
        name, body = self._inc(target="a.md", task_type="audit", task_id="T1", detail=detail)
        heads = [ln for ln in body.splitlines() if ln.lstrip().startswith("## ")]
        self.assertEqual(len(heads), 4, f"外部文本造出了额外标题：{heads}")
        self.assertIn("我伪造的根因", body)          # 内容不丢
        forged = [ln for ln in body.splitlines() if "我伪造的根因" in ln or "缩进版伪造" in ln]
        self.assertTrue(forged and all(ln.lstrip().startswith("\\#") for ln in forged), forged)
        head = body.split("## 1.")[0]
        self.assertEqual(len([ln for ln in head.splitlines() if ln.startswith("- **Path**:")]), 1,
                         "元信息列表必须完整在头区")
        # ocr2-512：正文区不得留下能被 `_headers`（last-wins）认领的元信息行——否则
        # 伪造的 `- **Path**`/`- **Status**` 会改写 build_card 读到的真实元数据。
        import re as _re

        pattern = _re.compile(r"^-\s+\*\*[^*]+\*\*")
        body_after = body.split("## 1.", 1)[1]
        raw_meta = [ln for ln in body_after.splitlines() if pattern.match(ln.lstrip())]
        self.assertEqual(raw_meta, [], f"正文残留可认领的元信息行：{raw_meta}")
        self.assertIn("\\- **Path**: /etc/passwd", body)
        from k3dge.engine.doc_catalog import _headers

        self.assertEqual(_headers(body).get("Path"), "a.md", "伪造正文改写/覆盖了真实头区元数据")


if __name__ == "__main__":
    unittest.main()
