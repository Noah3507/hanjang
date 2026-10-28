"""Write pipeline outputs all-or-nothing and record what produced them."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def code_revision(repo_root: Path) -> dict:
    """Git commit of the code that ran, and whether tracked files had local edits."""
    def git(*args: str) -> str | None:
        try:
            result = subprocess.run(["git", "-C", str(repo_root), *args],
                                    capture_output=True, text=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            return None
        return result.stdout.strip()

    commit = git("rev-parse", "HEAD")
    status = git("status", "--porcelain", "--untracked-files=no")
    return {"commit": commit, "dirty": None if status is None else bool(status)}


def find_provenance(path: Path, data_root: Path) -> dict | None:
    """The nearest provenance.json at or above path (stopping at data/), if any."""
    current = Path(path).resolve()
    data_root = Path(data_root).resolve()
    while current.is_relative_to(data_root):
        candidate = current / "provenance.json"
        if candidate.exists():
            return json.loads(candidate.read_text())
        if current == data_root:
            break
        current = current.parent
    return None


def describe_inputs(files: dict[str, Path], repo_root: Path) -> dict:
    """Size and SHA-256 of every input file, keyed by a short label."""
    described = {}
    for label, path in files.items():
        path = Path(path).resolve()
        try:
            shown = str(path.relative_to(Path(repo_root).resolve()))
        except ValueError:
            shown = str(path)
        described[label] = {"path": shown, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
    return described


@contextmanager
def staged_output(out_dir: Path) -> Iterator[Path]:
    """Yield a temporary folder; replace out_dir with it only if the block succeeds.

    On any error, including a failed final rename, the temporary folder is
    removed and the previous out_dir is restored, so a failed run never leaves
    partial results. (A hard kill between the two renames can still leave the
    previous results only in the hidden .old- folder next to out_dir.)
    """
    out_dir = Path(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:8]
    tmp = out_dir.parent / f".{out_dir.name}.tmp-{token}"
    tmp.mkdir()
    try:
        yield tmp
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    old = out_dir.parent / f".{out_dir.name}.old-{token}"
    moved_old = False
    try:
        if out_dir.exists():
            out_dir.rename(old)
            moved_old = True
        tmp.rename(out_dir)
    except BaseException:
        # The swap failed: put the previous results back where they were.
        if moved_old and not out_dir.exists():
            old.rename(out_dir)
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    shutil.rmtree(old, ignore_errors=True)
