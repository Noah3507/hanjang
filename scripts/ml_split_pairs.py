"""Assign train/val/test to the preference pairs and check for leakage.

Run from the repository root, inside .venv-ml, after scripts/ml_build_pairs.py:
  python scripts/ml_split_pairs.py

Reads data/processed/pairs/, writes data/processed/splits/<version>/
(ignored by Git): taste.parquet, creativeranking.parquet, stats.json.
Stops with an error if any group or image appears in two splits. The output
folder is replaced only when every step and check succeeds (no partial
results). stats.json records the code commit and the SHA-256 of the inputs.
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

from ml.data.outputs import code_revision, describe_inputs, staged_output
from ml.data.split import check_no_leakage, load_config, split_creativeranking, split_taste


def inside_data(path: Path, repo_root: Path) -> Path:
    data_root = (repo_root / "data").resolve()
    target = (path if path.is_absolute() else repo_root / path).resolve()
    if target == data_root or not target.is_relative_to(data_root):
        raise ValueError(f"--out must be a folder inside {data_root}, got {target}")
    return target


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=repo_root / "ml/data/split_config.json")
    parser.add_argument("--pairs", type=Path, default=repo_root / "data/processed/pairs")
    parser.add_argument("--out", type=Path, default=Path("data/processed/splits"))
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    try:
        out_dir = inside_data(args.out, repo_root) / cfg["version"]
    except ValueError as error:
        parser.error(str(error))

    inputs = {"taste_pairs": args.pairs / "taste.parquet",
              "creativeranking_pairs": args.pairs / "creativeranking.parquet"}
    if (args.pairs / "stats.json").exists():
        inputs["pairs_stats"] = args.pairs / "stats.json"
    stats = {
        "config_version": cfg["version"],
        "config": cfg,
        "code": code_revision(repo_root),
        "inputs": describe_inputs(inputs, repo_root),
    }

    # Split and check everything in memory first; nothing is written unless all succeed.
    taste = split_taste(pd.read_parquet(inputs["taste_pairs"]), cfg["taste"], cfg["version"])
    stats["taste"] = check_no_leakage(taste)
    print("taste:", stats["taste"])
    cr, cr_info = split_creativeranking(pd.read_parquet(inputs["creativeranking_pairs"]))
    stats["creativeranking"] = {**check_no_leakage(cr), **cr_info}
    print("creativeranking:", stats["creativeranking"])

    stats["built_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with staged_output(out_dir) as tmp:  # replaces out_dir only if all files are written
        taste.to_parquet(tmp / "taste.parquet", index=False)
        cr.to_parquet(tmp / "creativeranking.parquet", index=False)
        (tmp / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out_dir}")
    return stats


if __name__ == "__main__":
    main()
