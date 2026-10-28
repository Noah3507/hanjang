"""Build preference pairs from the raw TASTE and CreativeRanking files.

Run from the repository root, inside .venv-ml:
  python scripts/ml_build_pairs.py

Reads data/raw/ (see ml/data/README.md), writes data/processed/pairs/
(ignored by Git): taste.parquet, creativeranking.parquet, stats.json.
The folder is replaced only when every step succeeds (no partial results).
stats.json records the code commit and the SHA-256 of every input file.
CreativeRanking rights are unverified; the output is for research only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # allow "python scripts/..." from the repo root

from ml.data.outputs import code_revision, describe_inputs, find_provenance, staged_output
from ml.data.pairs import (
    creativeranking_pairs,
    load_config,
    read_creativeranking_split,
    taste_pairs,
)

SPLITS = ("train", "val", "test")


def inside_data(path: Path, repo_root: Path = REPO_ROOT) -> Path:
    data_root = (repo_root / "data").resolve()
    target = (path if path.is_absolute() else repo_root / path).resolve()
    if target == data_root or not target.is_relative_to(data_root):
        raise ValueError(f"--out must be a folder inside {data_root}, got {target}")
    return target


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=repo_root / "ml/data/pair_config.json")
    parser.add_argument("--taste-dir", type=Path, default=repo_root / "data/raw/taste")
    parser.add_argument("--cr-dir", type=Path,
                        default=repo_root / "data/raw/creativeranking/list/list")
    parser.add_argument("--out", type=Path, default=Path("data/processed/pairs"))
    args = parser.parse_args(argv)
    try:
        out_dir = inside_data(args.out, repo_root)
    except ValueError as error:
        parser.error(str(error))

    cfg = load_config(args.config)
    data_root = repo_root / "data"
    taste_files = {"taste_rankings": args.taste_dir / "rankings.parquet",
                   "taste_assets": args.taste_dir / "assets.parquet"}
    cr_files = {f"creativeranking_{s}": args.cr_dir / f"{s}_data_list.txt" for s in SPLITS}
    stats = {
        "config_version": cfg["version"],
        "config": cfg,
        "code": code_revision(repo_root),
        "inputs": describe_inputs({**taste_files, **cr_files}, repo_root),
        "sources": {"taste": find_provenance(args.taste_dir, data_root),
                    "creativeranking": find_provenance(args.cr_dir, data_root)},
    }

    # Build everything in memory first; nothing is written unless every step succeeds.
    taste, stats["taste"] = taste_pairs(
        pd.read_parquet(taste_files["taste_rankings"]),
        pd.read_parquet(taste_files["taste_assets"]),
        cfg["taste"],
    )
    print("taste:", stats["taste"])
    parts, stats["creativeranking"] = [], {}
    for split in SPLITS:
        rows = read_creativeranking_split(args.cr_dir, split)
        split_pairs, split_stats = creativeranking_pairs(
            rows, cfg["creativeranking"], split, salt=cfg["version"]
        )
        parts.append(split_pairs)
        stats["creativeranking"][split] = split_stats
        print(f"creativeranking {split}:", split_stats)
        del rows
    creativeranking = pd.concat(parts, ignore_index=True)

    stats["built_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with staged_output(out_dir) as tmp:  # replaces out_dir only if all files are written
        taste.to_parquet(tmp / "taste.parquet", index=False)
        creativeranking.to_parquet(tmp / "creativeranking.parquet", index=False)
        (tmp / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out_dir}")
    return stats


if __name__ == "__main__":
    main()
