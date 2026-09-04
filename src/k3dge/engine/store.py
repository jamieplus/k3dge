"""Content-addressed snapshot store — 快照的内容寻址**存取**（git 对象库实现）。

规则 08 的切分：本模块只管"放进对象库 / 按引用取出 / 两快照 diff"三件事。
它**不知道**审计、不知道送检范围的构成规则（那是 `bundle.py` 的职责）、不碰账本。
传输与保留策略因此全部继承 git：远程席位=push/fetch/`git bundle`，GC=`git gc`。

引用格式：`cas://sha256:<tree-oid>`（store 以 --object-format=sha256 建库；
不支持的环境由 bundle 回退到旧 tar 文件路，ref 格式不变）。
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

STORE_REL = ".k3dge/store.git"


class StoreError(RuntimeError):
    pass


class GitStore:
    """一个消费仓一个本地裸库；tree OID 即内容哈希。"""

    def __init__(self, workspace: Path) -> None:
        self.workspace = Path(workspace)
        self.path = self.workspace / STORE_REL

    # -- plumbing helpers ----------------------------------------------------
    def _git(self, *args: str, stdin: bytes = b"", epoch: bool = False) -> bytes:
        env = {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, "GIT_DIR": str(self.path)}
        if epoch:  # 合成 commit 必须确定性：固定身份与 @0 时间戳（同输入同 commit oid）
            who = "k3dge-pack <noreply@k3dge.local>"
            env.update(GIT_AUTHOR_NAME=who.split(" ")[0], GIT_AUTHOR_EMAIL="noreply@k3dge.local",
                       GIT_AUTHOR_DATE="@0 +0000", GIT_COMMITTER_NAME=who.split(" ")[0],
                       GIT_COMMITTER_EMAIL="noreply@k3dge.local", GIT_COMMITTER_DATE="@0 +0000")
        proc = subprocess.run(
            ["git", *args], cwd=str(self.workspace), input=stdin,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        )
        if proc.returncode != 0:
            raise StoreError(f"git {' '.join(args)}: {proc.stderr.decode('utf-8', 'replace').strip()[:200]}")
        return proc.stdout

    def ensure(self) -> None:
        if (self.path / "HEAD").exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(["git", "init", "-q", "--object-format=sha256", "--bare", str(self.path)],
                           check=True, capture_output=True)
        except subprocess.CalledProcessError:
            raise StoreError("git lacks --object-format=sha256（bundle 将回退 tar 路）") from None

    @property
    def supports_sha256(self) -> bool:
        try:
            self.ensure()
            return True
        except StoreError:
            return False

    # -- 存取接口（bundle 层唯一的依赖面） ------------------------------------
    def put_tree(self, files: Dict[str, bytes]) -> str:
        """{relpath: bytes} → tree OID。自底向上 mktree，排序稳定 ⇒ 同内容必同 OID。"""
        self.ensure()
        root: dict = {}
        for rel, data in files.items():
            parts = rel.strip("/").split("/")
            node = root
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node[parts[-1]] = data
        return self._mktree(root)

    def _mktree(self, node: dict) -> str:
        rows: List[str] = []
        for name in sorted(node):
            val = node[name]
            if isinstance(val, dict):
                oid = self._mktree(val)
                rows.append(f"040000 tree {oid}\t{name}")
            else:
                blob = self._git("hash-object", "-w", "--stdin", stdin=val).strip().decode()
                rows.append(f"100644 blob {blob}\t{name}")
        return self._git("mktree", stdin="\n".join(rows).encode("utf-8") + b"\n").strip().decode()

    def list_tree(self, oid: str) -> List[Tuple[str, str]]:
        """[(mode:blob oid, path)]——resolve/stat 与 diff 的地基。"""
        out = self._git("ls-tree", "-r", oid)
        entries: List[Tuple[str, str]] = []
        for line in out.decode("utf-8", "replace").splitlines():
            meta, path = line.split("\t", 1)
            entries.append((meta.split()[2], path))
        return entries

    def get(self, ref: str, dest: Path) -> Path:
        """`cas://sha256:<oid>` → 物化到 dest/；逐文件 sha 校验不过即抛（库被动过就是事故）。"""
        oid = ref.split(":", 2)[-1] if "://" in ref else ref
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        for blob_oid, path in self.list_tree(oid):
            data = self._git("cat-file", "blob", blob_oid)
            target = dest / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if _object_hash(data, blob_oid) != blob_oid:
                raise StoreError(f"对象校验失败: {path}")  # git blob oid = hash("blob <len>\0"+data)，不是裸内容哈希
        return dest

    def diff(self, ref_a: str, ref_b: str) -> List[Tuple[str, str, str]]:
        """两快照 [(±, path, ±)]：复审 delta 的原料（新增/删除/变更）。"""
        # list_tree 给 (oid, path)；diff 按 path 对齐 ⇒ 建 path→oid 表
        a = {p: o for o, p in self.list_tree(_oid(ref_a))}
        b = {p: o for o, p in self.list_tree(_oid(ref_b))}
        out: List[Tuple[str, str, str]] = []
        for p in sorted(set(a) | set(b)):
            if p not in a:
                out.append(("+", p, b[p]))  # (±, path, oid)
            elif p not in b:
                out.append(("-", p, a[p]))
            elif a[p] != b[p]:
                out.append(("~", p, b[p]))
        return out


    # ---- ②快照 commit 链与 bundle 文件（store.git 内自洽，不碰消费仓 .git） ----------

    def commit_snapshot(self, files: Dict[str, bytes], job: str, prev_commit: Optional[str] = None) -> dict:
        """tree→epoch commit（可带前驱成链）。链住 store 侧 refs/snap/<job>，与主干开发分支互不污染。"""
        self.ensure()
        tree = self.put_tree(files)
        msg = f"k3dge snapshot job={job} tree={tree}"
        args = ["commit-tree", tree]
        if prev_commit:
            args += ["-p", prev_commit]
        args += ["-m", msg]
        commit = self._git(*args, epoch=True).strip().decode()
        ref = f"refs/snap/{job}"
        self._git("update-ref", ref, commit)
        return {"tree": tree, "commit": commit, "ref": ref}

    def bundle_create(self, commit: str, out: Path, has: Optional[str] = None) -> Path:
        """bundle 单文件＝交换原子；`has`＝前置 commit（薄包）——同一条 create，形状统一。

        git 拒绝对裸 SHA 打包（"empty bundle"）⇒ 先钉一个每-commit 的确定性 ref。
        """
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            out.unlink()
        ref = f"refs/k3dge-bundle/{commit[:16]}"
        self._git("update-ref", ref, commit)
        args = ["bundle", "create", str(out), ref]
        if has:
            args += ["--not", has]
        self._git(*args)
        return out

    @staticmethod
    def bundle_heads(bundle: Path) -> List[tuple]:
        import subprocess
        proc = subprocess.run(["git", "bundle", "list-heads", str(bundle)],
                              capture_output=True, text=True)
        out = []
        for line in proc.stdout.splitlines():
            oid, ref = line.split(maxsplit=1)
            out.append((oid, ref))
        return out

def _oid(ref: str) -> str:
    return ref.split(":", 2)[-1] if "://" in ref else ref


def _object_hash(data: bytes, oid: str) -> str:
    """按 oid 长度猜摘要算法（64=sha256, 40=sha1），复算 git 对象哈希。"""
    h = hashlib.sha256() if len(oid) == 64 else hashlib.sha1()
    h.update(f"blob {len(data)}".encode("ascii") + b"\0" + data)
    return h.hexdigest()




