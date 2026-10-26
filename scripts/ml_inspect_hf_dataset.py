"""List or download files from a Hugging Face dataset repo, with provenance.

Examples (run from the repository root, inside .venv-ml):
  python scripts/ml_inspect_hf_dataset.py Evan12/CreativeRanking --list
  python scripts/ml_inspect_hf_dataset.py Evan12/CreativeRanking \
      --download list.zip test_data_list.txt --out data/raw/creativeranking

Downloads are recorded in <out>/provenance.json (repo, revision, date,
size, sha256) so the data can be reviewed later. Nothing is uploaded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo_id", help="e.g. Evan12/CreativeRanking")
    parser.add_argument("--revision", default=None, help="commit sha; default: latest")
    parser.add_argument("--list", action="store_true", help="list files and sizes")
    parser.add_argument("--download", nargs="*", default=[], help="file paths to download")
    parser.add_argument("--out", type=Path, default=None, help="output folder under data/")
    args = parser.parse_args()

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

    if args.download:
        if args.out is None:
            parser.error("--out is required with --download (use a folder under data/)")
        args.out.mkdir(parents=True, exist_ok=True)
        records = []
        for filename in args.download:
            local = Path(
                hf_hub_download(
                    args.repo_id,
                    filename,
                    repo_type="dataset",
                    revision=revision,
                    local_dir=args.out,
                )
            )
            record = {
                "file": filename,
                "bytes": local.stat().st_size,
                "sha256": sha256_of(local),
            }
            records.append(record)
            print(f"downloaded {filename}: {human_size(record['bytes'])} sha256={record['sha256']}")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for record in records:
            record["revision"] = revision
            record["retrieved_at"] = now
        provenance_path = args.out / "provenance.json"
        provenance = {"repo_id": args.repo_id, "files": []}
        if provenance_path.exists():
            provenance = json.loads(provenance_path.read_text())
        # Keep earlier downloads; replace entries for files fetched again.
        kept = [f for f in provenance["files"] if f["file"] not in set(args.download)]
        provenance["files"] = kept + records
        provenance_path.write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {provenance_path}")


if __name__ == "__main__":
    main()