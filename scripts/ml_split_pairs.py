"""Assign train/val/test to the preference pairs and check for leakage.

Run from the repository root, inside .venv-ml, after scripts/ml_build_pairs.py:
  python scripts/ml_split_pairs.py

Reads data/processed/pairs/, writes data/processed/splits/<version>/
(ignored by Git): taste.parquet, creativeranking.parquet, stats.json.
Stops with an error if any group or image appears in two splits.
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
    out_dir.mkdir(parents=True, exist_ok=True)

    stats = {"config_version": cfg["version"], "config": cfg}
    taste = split_taste(pd.read_parquet(args.pairs / "taste.parquet"), cfg["taste"], cfg["version"])
    stats["taste"] = check_no_leakage(taste)
    taste.to_parquet(out_dir / "taste.parquet", index=False)
    print("taste:", stats["taste"])

    cr, cr_info = split_creativeranking(pd.read_parquet(args.pairs / "creativeranking.parquet"))
    stats["creativeranking"] = {**check_no_leakage(cr), **cr_info}
    cr.to_parquet(out_dir / "creativeranking.parquet", index=False)
    print("creativeranking:", stats["creativeranking"])

    stats["built_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (out_dir / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out_dir}")
    return stats


if __name__ == "__main__":
    main()
