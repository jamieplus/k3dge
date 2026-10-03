"""受管路径必须能验；缺行必须红。不开豁免。"""

import re
import os
import subprocess
from pathlib import Path

from k3dge.engine.attest import PREFIX, append_to_message, verify_commit


def _git_env(extra: "dict | None" = None) -> dict:
    """夹具的 git 环境钉死（t-069）：`commit.gpgsign`/`core.hooksPath`/`alias.*`/include.path
    这些宿主 globalconfig 会让 init/commit 在开发机与 CI 上表现不一（签名缺失直接红）。
    `GIT_CONFIG_GLOBAL=devnull + NOSYSTEM` 把两层配置全关掉；仓库身份仍由各命令的 `-c` 给。"""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG")}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    if extra:
        env.update(extra)
    return env


def _gitc(ws: Path, *args: str, env_extra: "dict | None" = None) -> str:
    r = subprocess.run(["git", *args], cwd=str(ws), check=True,
                       capture_output=True, text=True, env=_git_env(env_extra))
    return r.stdout


def _head(ws: Path) -> str:
    """取 HEAD **必须查返回码**（t-073）：失败回空串时 `verify_commit(ws, "")` 报的是
    "提交标识不合法"——前置崩了伪装成产品结论，missing/replay 两条测全部误导性红。
    """
    h = _gitc(ws, "rev-parse", "HEAD").strip()
    assert h, "rev-parse 回了空——本测的前提（有提交）没建立"
    return h


def _repo(base: Path) -> Path:
    # ocr2-722：旧写法裸 `mkdtemp()` + `atexit(shutil.rmtree, ws, True)`——清理失败
    # （权限/磁盘满/只读位）全吞，且目录在整个 pytest 会话期常驻、跨测累积。
    # 收进 fixture 管内：随测回收、失败可见（pytest 清理报错不再是静默磁盘占用）。
    ws = base / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    _gitc(ws, "init", "-q")
    _gitc(ws, "-c", "user.name=t", "-c", "user.email=t@t",
          "commit", "-q", "--allow-empty", "--no-verify", "-m", "chore: init")
    return ws


def test_appended_line_verifies(tmp_path):
    ws = _repo(tmp_path)
    (ws / "a.txt").write_text("x\n", encoding="utf-8")
    _gitc(ws, "add", "-A")
    msg = append_to_message(ws, "feat: x", who="t")
    assert PREFIX in msg
    # 作者时间**钉在署名行的分钟上**（t-070）：`append_to_message` 内部取 now()，
    # `git commit` 是稍后的另一个进程——两者之间跨过分界时 author 分钟 = 行分钟+1，
    # 而 windows() 只容同分钟与更早一分钟 ⇒ 慢 CI 上间歇红。钉死日期，把挂钟运气
    # 从断言里拿掉。
    m = re.search(r"@ (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z", msg)
    assert m, msg
    _gitc(ws, "-c", "user.name=t", "-c", "user.email=t@t",
          "commit", "-q", "--no-verify", "-m", msg,
          env_extra={"GIT_AUTHOR_DATE": m.group(1) + "Z",
                     "GIT_COMMITTER_DATE": m.group(1) + "Z"})
    ok, out = verify_commit(ws, _head(ws))
    assert ok, out


def test_missing_line_is_refused(tmp_path):
    ws = _repo(tmp_path)
    ok, out = verify_commit(ws, _head(ws))
    assert not ok
    assert "missing attestation line" in out


def test_line_replayed_onto_other_commit_is_refused(tmp_path):
    """一条合法行不能原样搬到另一提交（同树）：必须与本提交的作者时间同窗（ocr-005）。"""
    from k3dge.engine.attest import token

    ws = _repo(tmp_path)
    old = "2020-01-01T00:00:00Z"
    ln = f"{PREFIX}t @ {old} #{token(ws, old)}"
    _gitc(ws, "-c", "user.name=t", "-c", "user.email=t@t",
          "commit", "-q", "--allow-empty", "--no-verify", "-m", f"feat: x\n\n{ln}")
    ok, out = verify_commit(ws, _head(ws))
    assert not ok
    assert "timestamp mismatch" in out
def test_attestation_stays_inside_existing_trailer_block(tmp_path) -> None:
    """另起一段会把封版四键挤成倒数第二段 ⇒ `%(trailers)` 只读回署名（ocr-308）。

    （原来这行串落在 `ws = _repo()` **之后** ⇒ 只是被丢弃的表达式语句，不是 docstring：
    `__doc__` 为 None，`pytest -vv`/collect-only 里看不到本测的意图。t-071）
    """
    ws = _repo(tmp_path)
    msg = ("chore: seal\n\n"
           "Seal-milestone: M11\nAudit-baseline: a7259c2\nAudit-seat: k3dit\nAudit-result: closed")
    out = append_to_message(ws, msg, who="k3dge-process")
    last = out.strip().split("\n\n")[-1]
    assert len(last.splitlines()) == 5, out
    assert last.startswith("Seal-milestone:"), out


def test_prose_body_still_gets_own_paragraph(tmp_path) -> None:
    out = append_to_message(_repo(tmp_path), "feat: x\n\n正文说明", who="w")
    assert "\n\nk3dge-commit:" in out


def test_verify_commit_rejects_option_shaped_and_blank_ids(tmp_path) -> None:
    """`h` 来自 CI 参数：以 `-` 开头会被 git 当选项（注入面），空/含空白同样拒（393）。

    工作区用**独立临时目录**而不是 `Path(".")`（t-072）：今天靠"校验先短路"侥幸惰性——
    一旦 attest.py:135-140 的校验被重排/放宽，旧夹具就在**开发者真仓**里起 git 进程，
    回归表现为环境相关；在空目录里则必然确定性失败。
    """
    assert not (tmp_path / ".git").exists()
    for bad in ("", "  ", "--output=cmd", "a b"):
        ok, msg = verify_commit(tmp_path, bad)
        assert not ok and "不合法" in msg, (bad, msg)


def test_verify_commit_passes_ref_names_through_validation(tmp_path) -> None:
    """名字别读反（t-074）：本测验的是**校验放行**——`HEAD`/`main^` 这类 ref 名过得了
    "非空/不以 - 开头/不含空白"的门，抵达真判据（未署名 ⇒ not ok）。断言本来就是
    `not ok`，旧名 "accepts" 会让人以为是验签收，将来"顺手改成 assertTrue"即毁测。
    """
    ws = _repo(tmp_path)
    ok, msg = verify_commit(ws, "HEAD")
    assert not ok and "missing attestation" in msg, msg   # 通过校验，进到真判据（未署名）


def test_wrong_token_in_window_is_refused(tmp_path) -> None:
    """钉住 **token 比对支路**（t-075）：旧"重放"测用 2020 年戳，`timestamp mismatch`
    先短路，`tok not in expected` 这行从未被执行——删掉整个比对，本文件仍全绿。
    现在：署名行时间**落在提交作者分钟内**（时间判据放行），token 手改成别的词 ⇒
    必须红在 `token mismatch`（树/secret 绑定由此可证伪）。
    """

    from k3dge.engine.attest import token

    ws = _repo(tmp_path)
    # 先落一个文件并暂存，使 token 基于**非空树**：旧写法在空树上产 token 再加文件，
    # 正确 token 也会因树变而红，测不出"伪造"只测出"树变"（ocr2-110）。
    (ws / "b.txt").write_text("1\n", encoding="utf-8")
    _gitc(ws, "add", "-A")
    msg = append_to_message(ws, "feat: token case", who="t")
    m = re.search(r"@ (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z #(\S+)", msg)
    assert m, msg
    # token 必须**形状合法但绑定错误**（词表词）——乱写会让 LINE_RE 直接不匹配，
    # 报 "missing attestation line"，永远走不到比对那一支。
    # 注意：`token()` 先过 `window()`（截到分钟）——给同分钟的盐会被截成同一个串，
    # "换盐"全撞是必然。错误绑定要拿**不同分钟**的时间戳产 token：
    import datetime as _dt

    real = m.group(2)
    when = _dt.datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=_dt.timezone.utc)
    acceptable = {real, token(ws, (when - _dt.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))}
    bad = ""
    for salt in range(1, 20):
        cand = token(ws, f"2030-01-{salt:02d}T00:0{salt % 10}:00Z")
        if cand not in acceptable:          # verify 比对**同分钟＋前一分钟**两个窗，都得不撞
            bad = cand
            break
    assert bad, f"错误绑定的候选都撞进可接受窗：{acceptable}"
    forged = msg.replace("#" + m.group(2), "#" + bad)
    env_extra = {"GIT_AUTHOR_DATE": m.group(1).replace("T", " ") + " +0000",
                 "GIT_COMMITTER_DATE": m.group(1).replace("T", " ") + " +0000"}
    # 树保持 token 时刻的样子（b.txt 已是 "1\n" 并暂存）：唯一变量是 token 真伪，
    # 伪造被拒即证伪绑定，不掺树变（ocr2-110）。
    _gitc(ws, "-c", "user.name=t", "-c", "user.email=t@t",
          "commit", "-q", "--no-verify", "-m", forged, env_extra=env_extra)
    ok, out = verify_commit(ws, _head(ws))
    assert not ok and "token mismatch" in out, out


def test_stale_shaped_line_is_refreshed_not_kept(tmp_path):
    # 形状对但 token 过期/伪造的行不得原样保留，必须重算 fresh 行（ocr2-011/035）。
    ws = _repo(tmp_path)
    (ws / "a.txt").write_text("x\n", encoding="utf-8")
    _gitc(ws, "add", "-A")
    stale = "feat: x\n\nk3dge-commit: t @ 2020-01-01T00:00:00Z #wrongword\n"
    out = append_to_message(ws, stale, who="t")
    assert "wrongword" not in out and "2020-01-01" not in out
    assert PREFIX in out


def test_windows_tolerance_is_symmetric_around_the_minute() -> None:
    """ocr2-188：署名行时间容差必须对称（±1 分钟），不能只容同分钟与更早一分钟。"""
    from k3dge.engine.attest import windows

    assert windows("2026-01-01T00:05:30Z") == [
        "2026-01-01T00:04", "2026-01-01T00:05", "2026-01-01T00:06"]


def test_verify_commit_survives_non_ascii_under_ascii_locale(tmp_path, monkeypatch) -> None:
    """ocr2-189：git 输出 UTF-8，但 `text=True` 按 locale 解码；ASCII locale 不得崩栈。"""
    import locale

    ws = _repo(tmp_path)
    (ws / "a.txt").write_text("x\n", encoding="utf-8")
    _gitc(ws, "add", "-A")
    msg = append_to_message(ws, "feat: x\n\n作者：José", who="José")
    m = re.search(r"@ (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z", msg)
    assert m, msg
    _gitc(ws, "-c", "user.name=José", "-c", "user.email=t@t",
          "commit", "-q", "--no-verify", "-m", msg,
          env_extra={"GIT_AUTHOR_DATE": m.group(1) + "Z",
                     "GIT_COMMITTER_DATE": m.group(1) + "Z"})
    monkeypatch.setattr(locale, "getencoding", lambda: "ascii")
    ok, out = verify_commit(ws, _head(ws))     # 不得抛 UnicodeDecodeError
    assert ok, out


def test_verify_commit_accepts_later_valid_line_after_shaped_decoy(tmp_path) -> None:
    """ocr2-190：正文里靠前的形状合法但无效的行不得遮住真正的 trailer。"""
    ws = _repo(tmp_path)
    (ws / "a.txt").write_text("x\n", encoding="utf-8")
    _gitc(ws, "add", "-A")
    msg = append_to_message(ws, "feat: x", who="t")
    m = re.search(r"@ (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z", msg)
    assert m, msg
    decoy = "k3dge-commit: t @ 2020-01-01T00:00:00Z #wrongword"
    body = msg.replace(PREFIX, decoy + "\n" + PREFIX, 1)
    _gitc(ws, "-c", "user.name=t", "-c", "user.email=t@t",
          "commit", "-q", "--no-verify", "-m", body,
          env_extra={"GIT_AUTHOR_DATE": m.group(1) + "Z",
                     "GIT_COMMITTER_DATE": m.group(1) + "Z"})
    ok, out = verify_commit(ws, _head(ws))
    assert ok, out
