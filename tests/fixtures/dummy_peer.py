"""Dummy peer — 与真实 peer 同契约（`docs/protocols/peer_contract.md`），canned 工件。

桩子先行的锚：骨架链（submit → 协议外等待 → collect → 验壳 → 落盘 → 数计数）
在没有任何真实 harness 时必须可跑、可测。真实 peer 在各自仓内换实现，契约不变。

行为（全部由环境/入参决定，无隐藏状态外溢）：
- `dummy_submit`  → {ok, kind:"job", payload:{job_id}}（≤ 即时）
- `dummy_collect` → {ok, kind:"report", payload:{report_markdown}} 或 NOT_FOUND
- 报告里「待修」行数由环境变量 `DUMMY_PENDING`（默认 0）控制 —— 用来测开环/闭环两态。
"""

import datetime
import json
import os
import uuid

try:
    from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    try:
        from mcp.server import MCPServer as FastMCP  # type: ignore[assignment]
    except ImportError:
        FastMCP = None  # type: ignore[assignment]

if FastMCP is None:  # pragma: no cover
    raise SystemExit("mcp SDK not importable; install k3dge[mcp]")

mcp = FastMCP("dummy")

import tempfile as _tempfile
from pathlib import Path as _Path

#: 仓根派生的**每检出**独立路径 + 可显式覆盖：以前写死 `/tmp/k3dge_dummy_peer_jobs.json`
#: ⇒ (a) 任何本机用户可抢先创建/换成符号链接（我们随后 os.replace 会跟着把内容写到它指向的
#: 地方，等于任意文件覆写/DoS），(b) 两个并发检出/工作树共用一份账，互相看见对方的 job（t-013）。
_REPO_ROOT = _Path(__file__).resolve().parents[2]


def _state_path() -> _Path:
    import hashlib

    override = os.environ.get("DUMMY_PEER_STATE", "").strip()
    if override:
        return _Path(override)
    key = hashlib.sha1(str(_REPO_ROOT).encode("utf-8")).hexdigest()[:10]
    return _Path(_tempfile.gettempdir()) / f"k3dge_dummy_peer_jobs-{key}.json"


_STATE_FILE = _state_path()
_LOCK_FILE = _Path(str(_STATE_FILE) + ".lock")
_MAX_JOBS = 200                      # 桩也被跨进程反复跑；不回收就无界增长


def _load_jobs() -> dict:
    """读作业账。**只有"文件不存在"才等于"还没有作业"**。

    旧实现把 OSError/坏 JSON 一并吞成 `{}`：调用方紧接着 `_save_jobs({只有新作业})`
    ⇒ 一次瞬时读失败（或上一次非原子写留下的半截文件）就把已入队的作业全丢掉，
    之后它们的 collect 永远 NOT_FOUND（t-010）。形状也必须校：合法 JSON 但不是对象
    （`[]`/`null`/`42`）此前原样返回，`jobs[job_id] = {...}` 当场 TypeError。
    """
    if _STATE_FILE.is_symlink():
        # 符号链接＝有人把账本指到别处（或被抢注）：宁可拒跑也不顺着它读写
        raise RuntimeError(f"dummy peer: 状态文件是符号链接，拒用（{_STATE_FILE}）")
    try:
        raw = _STATE_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise RuntimeError(f"dummy peer: 作业账读不出（{exc}）") from exc
    data = _json_loads(raw)                       # 坏 JSON ⇒ 抛错，不再冒充空账
    if not isinstance(data, dict):
        raise RuntimeError(f"dummy peer: 作业账不是对象（{type(data).__name__}）")
    return data


def _save_jobs(jobs: dict) -> None:
    """同目录临时件 + `os.replace` 原子落盘（t-011）。

    `write_text` 先截断再分块写：跨进程读者撞上中途就拿到残缺 JSON ⇒ 被当空账再覆盖回去，
    两个缺陷相乘就是"作业凭空消失"。顺带按插入序裁到 `_MAX_JOBS`，避免无界增长。
    """
    items = list(jobs.items())[-_MAX_JOBS:]
    tmp = _Path(str(_STATE_FILE) + f".{os.getpid()}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(_json_dumps(dict(items), ensure_ascii=False))
    os.replace(tmp, _STATE_FILE)


import contextlib


@contextlib.contextmanager
def _state_lock():
    """load → mutate → save 的复合更新必须互斥（t-012）。

    两个并发 `dummy_submit` 读同一快照、各加自己那条、后写者赢 ⇒ 先提交那个的 job_id
    从没落账，它的 collect 永远 NOT_FOUND（`uuid4` 只保证不撞 key，救不了读改写）。
    Windows 没有 fcntl：退化成尽力而为（桩在 POSIX 下跑主链路；这里不假装有锁）。
    """
    try:
        import fcntl
    except ImportError:                                  # pragma: no cover - Windows
        yield
        return
    with open(_LOCK_FILE, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


_json_loads = json.loads
_json_dumps = json.dumps
_HEADER = "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |"
_SEP = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"


def _now() -> str:
    # tz-aware 输出（t-018）：M10 起全仓规定 k3dge 产的时间戳带显式偏移
    # （`2026-09-16-M10-chore-timestamp_tz_offset`），naive `datetime.now()` 与
    # events.jsonl 的 UTC 戳比较会歧义——peer_contract §generated_at 也是 ISO-8601。
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")


@mcp.tool()
def dummy_submit(baseline: str = "", scope: str = "", milestone_id: str = "",
                 branch: str = "", wt_dir: str = "") -> str:
    """Contract §1: validate + enqueue only; the wait lives outside the protocol."""
    # 长度先判再全形式匹配（t-017）：旧顺序 `all(...)` 在前——调用方可控的超长串会被
    # 逐字符扫完才因长度被拒；错误消息也补上"小写十六进制/长度"，大写粘贴不再无从下手。
    bl = str(baseline or "").strip()
    len_ok = len(bl) in (40, 64)
    hex_ok = bool(bl) and all(c in "0123456789abcdef" for c in bl)
    if not (len_ok and hex_ok):
        return json.dumps(
            {"ok": False, "error": "BAD_BUNDLE",
             "message": f"baseline 必须是 40 或 64 位**小写**十六进制 commit oid，收到 {baseline!r}"},
            ensure_ascii=False,
        )
    job_id = uuid.uuid4().hex[:12]
    with _state_lock():                     # 读改写整段上锁（t-012）
        jobs = _load_jobs()
        # branch/wt_dir 是工具公开 schema 的一部分：旧实现收下即丢 ⇒ 作业记录不含被审现场
        # 上下文，用桩跑真链时行为不明显（t-016）——一并存进作业记录并回显进报告。
        jobs[job_id] = {"baseline": bl, "scope": scope, "milestone_id": milestone_id,
                        "branch": str(branch or "").strip(), "wt_dir": str(wt_dir or "").strip()}
        _save_jobs(jobs)
    return json.dumps({"ok": True, "kind": "job", "payload": {"job_id": job_id}}, ensure_ascii=False)


@mcp.tool()
def dummy_collect(job_id: str) -> str:
    """Contract §1: idempotent collect; PENDING/NOT_FOUND are first-class errors."""
    job = _load_jobs().get(job_id)
    if job is None:
        return json.dumps(
            {"ok": False, "error": "NOT_FOUND", "message": f"no such job: {job_id!r}"},
            ensure_ascii=False,
        )
    raw_pending = os.environ.get("DUMMY_PENDING", "")
    try:
        # 文档说"默认 0"，但旧实现只在**变量缺失**时回落：`DUMMY_PENDING=""` 或 `"3 "` 这类
        # 畸形值会当场 ValueError，报错发生在工具内部而不是入口（t-014）
        pending = int(raw_pending.strip() or "0")
    except ValueError:
        return json.dumps({"ok": False, "error": "BAD_CONFIG",
                           "message": f"DUMMY_PENDING 必须是整数，收到 {raw_pending!r}"},
                          ensure_ascii=False)
    if pending < 0:
        return json.dumps({"ok": False, "error": "BAD_CONFIG",
                           "message": f"DUMMY_PENDING 不得为负，收到 {pending}"}, ensure_ascii=False)
    today = datetime.date.today().isoformat()
    ms = job.get("milestone_id") or "M0"
    rows = []
    for i in range(pending):
        rows.append(
            f"| D{i + 1} | {today} | 中 | P1 | 缺陷 | dummy finding {i + 1} | src/x.py:{i + 1} | 待修 | 转 task | 待补 | 待复审 |  |"
        )
    report_md = (
        f"# 审计：{job.get('scope') or 'target'}（milestone {ms}）\n\n"
        f"- **基线**: {job.get('baseline') or '-'}\n"
        f"- **审计人**: dummy+test-seat\n"
        f"- **透镜来源**: dummy（peer contract 桩）\n"
        # 这里原本又拼了**第二条** `- **基线**: 0000…`（40 个 0）⇒ 同一份报告两个互相矛盾的
        # 基线事实，消费侧读到的第一条恰好是 job 的真基线才没炸；契约上仍是自相矛盾件（t-015）
        f"- **范围**: {job.get('scope') or '-'}\n"
        f"- **分支**: {job.get('branch') or '-'}\n"
        f"- **工作树**: {job.get('wt_dir') or '-'}\n\n"
        f"{_HEADER}\n{_SEP}\n" + ("\n".join(rows) + "\n" if rows else "")
    )
    return json.dumps(
        {
            "ok": True,
            "kind": "report",
            "payload": {"report_markdown": report_md},
            "provenance": {
                "seat": "dummy+test-seat",
                "generated_at": _now(),
                "baseline": job.get("baseline") or "",
            },
        },
        ensure_ascii=False,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
