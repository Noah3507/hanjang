"""List or download files from a Hugging Face dataset repo, with provenance.

Examples (run from the repository root, inside .venv-ml):
  python scripts/ml_inspect_hf_dataset.py Evan12/CreativeRanking --list
  python scripts/ml_inspect_hf_dataset.py Evan12/CreativeRanking \
      --revision 16ad7beb2af81fb35b72b0d4797c688680e3bb05 \
      --download list.zip test_data_list.txt --out data/raw/creativeranking

Downloads require a pinned 40-character commit sha (--revision) and an
output folder inside the repository's data/ folder (ignored by Git).
Each file is recorded in <out>/provenance.json (repo, revision, date,
size, sha256) right after it is downloaded. Nothing is uploaded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMIT_SHA = re.compile(r"[0-9a-f]{40}")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def human_size(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "?"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def resolve_out_dir(out: Path, repo_root: Path = REPO_ROOT) -> Path:
    """Return the absolute output folder; it must be strictly inside <repo>/data/."""
    data_root = (repo_root / "data").resolve()
    target = (out if out.is_absolute() else repo_root / out).resolve()
    if target == data_root or not target.is_relative_to(data_root):
        raise ValueError(f"--out must be a folder inside {data_root}, got {target}")
    return target


def require_pinned_revision(revision: str | None) -> str:
    if revision is None or not COMMIT_SHA.fullmatch(revision):
        raise ValueError("--download needs --revision <40-character commit sha>")
    return revision


def load_provenance(path: Path, repo_id: str) -> dict:
    if not path.exists():
        return {"repo_id": repo_id, "files": []}
    provenance = json.loads(path.read_text())
    if provenance.get("repo_id") != repo_id:
        raise ValueError(
            f"{path} belongs to {provenance.get('repo_id')!r}, not {repo_id!r}; "
            "use a separate --out folder per dataset"
        )
    return provenance


def save_provenance(path: Path, provenance: dict) -> None:
    """Write atomically so an interrupted run never leaves a broken file."""
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def record_file(provenance: dict, record: dict) -> None:
    """Replace an earlier entry for the same file, keep all others."""
    provenance["files"] = [f for f in provenance["files"] if f["file"] != record["file"]]
    provenance["files"].append(record)


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo_id", help="e.g. Evan12/CreativeRanking")
    parser.add_argument("--revision", default=None,
                        help="40-character commit sha (required with --download)")
    parser.add_argument("--list", action="store_true", help="list files and sizes")
    parser.add_argument("--download", nargs="*", default=[], help="file paths to download")
    parser.add_argument("--out", type=Path, default=None, help="output folder inside data/")
    args = parser.parse_args(argv)

    out_dir = None
    if args.download:
        # Check everything before any network call or download.
        if args.out is None:
            parser.error("--out is required with --download (use a folder inside data/)")
        try:
            require_pinned_revision(args.revision)
            out_dir = resolve_out_dir(args.out, repo_root)
            provenance_path = out_dir / "provenance.json"
            provenance = load_provenance(provenance_path, args.repo_id)
        except ValueError as error:
            parser.error(str(error))

    api = HfApi()
    info = api.dataset_info(args.repo_id, revision=args.revision)
    revision = info.sha
    print(f"repo: {args.repo_id}")
    print(f"revision: {revision}")
    license_claim = info.card_data.get("license") if info.card_data else None
    print(f"license (card claim, not verified): {license_claim}")

    if args.list:
        entries = api.list_repo_tree(
            args.repo_id, repo_type="dataset", revision=revision, recursive=True
        )
        for entry in sorted(entries, key=lambda e: e.path):
            size = getattr(entry, "size", None)
            if size is not None:
                print(f"{human_size(size):>10}  {entry.path}")

    if out_dir is not None:
        if revision != args.revision:
            raise SystemExit(f"server returned revision {revision}, expected {args.revision}")
        out_dir.mkdir(parents=True, exist_ok=True)
        for filename in args.download:
            local = Path(
                hf_hub_download(
                    args.repo_id,
                    filename,
                    repo_type="dataset",
                    revision=revision,
                    local_dir=out_dir,
                )
            )
            record = {
                "file": filename,
                "bytes": local.stat().st_size,
                "sha256": sha256_of(local),
                "revision": revision,
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            record_file(provenance, record)
            save_provenance(provenance_path, provenance)  # saved after every file
            print(f"downloaded {filename}: {human_size(record['bytes'])} sha256={record['sha256']}")
        print(f"wrote {provenance_path}")


if __name__ == "__main__":
    main()
