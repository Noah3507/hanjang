"""Fetch only the images the preference pairs need, without the 107.7 GB zip.

Run from the repository root, inside .venv-ml, after scripts/ml_split_pairs.py:
  python scripts/ml_fetch_images.py

- TASTE: downloads images/ of purvanshi/TASTE (about 640 files).
- CreativeRanking: reads the central directory of images.zip once (cached as
  data/raw/creativeranking/zip_index.parquet), then fetches each needed image
  with one HTTP range request, checks its CRC32 and writes it to
  data/raw/creativeranking/images/. Existing correct files are skipped, so an
  interrupted run can simply be started again.
Both use pinned revisions. Nothing is uploaded; data/ is ignored by Git.
"""

from __future__ import annotations

import argparse
import json
import struct
import threading
import time
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
TASTE_REPO = "purvanshi/TASTE"
TASTE_REV = "731a7f588d433214c6d864d2e9f47978d91aed6b"
CR_REPO = "Evan12/CreativeRanking"
CR_REV = "16ad7beb2af81fb35b72b0d4797c688680e3bb05"
LOCAL_HEADER = struct.Struct("<4s5H3I2H")  # 30 bytes, zip local file header
HEADER_MARGIN = 1024  # extra bytes fetched for the name/extra fields


def inside_data(path: Path, repo_root: Path) -> Path:
    data_root = (repo_root / "data").resolve()
    target = (path if path.is_absolute() else repo_root / path).resolve()
    if target == data_root or not target.is_relative_to(data_root):
        raise ValueError(f"folder must be inside {data_root}, got {target}")
    return target


def needed_images(split_dir: Path, dataset: str) -> list[str]:
    pairs = pd.read_parquet(split_dir / f"{dataset}.parquet")
    return sorted(set(pairs["image_a"]) | set(pairs["image_b"]))


def zip_index(fs, zip_path: str) -> pd.DataFrame:
    """Read the zip central directory once: name, offset, sizes, method, CRC."""
    with fs.open(zip_path, "rb", block_size=8 * 1024 * 1024) as handle:
        infos = [i for i in zipfile.ZipFile(handle).infolist() if not i.is_dir()]
    return pd.DataFrame({
        "path": [i.filename for i in infos],
        "name": [i.filename.rsplit("/", 1)[-1] for i in infos],
        "header_offset": [i.header_offset for i in infos],
        "compress_size": [i.compress_size for i in infos],
        "file_size": [i.file_size for i in infos],
        "compress_type": [i.compress_type for i in infos],
        "crc": [i.CRC for i in infos],
    })


def range_reader(fs, zip_path: str):
    """read(start, end) with one unbuffered file handle per thread: one HTTP range per read."""
    local = threading.local()

    def read(start: int, end: int) -> bytes:
        if not hasattr(local, "handle"):
            local.handle = fs.open(zip_path, "rb", cache_type="none")
        local.handle.seek(start)
        return local.handle.read(end - start)

    return read


def fetch_member(read, row) -> bytes:
    """Return one member's bytes using a single range request (two if extra is long)."""
    start = int(row.header_offset)
    name_len = len(row.path.encode())
    end = start + LOCAL_HEADER.size + name_len + HEADER_MARGIN + int(row.compress_size)
    chunk = read(start, end)
    fields = LOCAL_HEADER.unpack(chunk[: LOCAL_HEADER.size])
    if fields[0] != b"PK\x03\x04":
        raise ValueError(f"bad local header for {row.path}")
    data_start = LOCAL_HEADER.size + fields[9] + fields[10]  # name length + extra length
    data_end = data_start + int(row.compress_size)
    if data_end > len(chunk):
        chunk = read(start, start + data_end)
    raw = chunk[data_start:data_end]
    if row.compress_type == zipfile.ZIP_STORED:
        data = raw
    elif row.compress_type == zipfile.ZIP_DEFLATED:
        data = zlib.decompress(raw, -15)
    else:
        raise ValueError(f"unsupported compression {row.compress_type} for {row.path}")
    if len(data) != int(row.file_size) or (zlib.crc32(data) & 0xFFFFFFFF) != int(row.crc):
        raise ValueError(f"size/CRC mismatch for {row.path}")
    return data


def fetch_zip_images(fs, zip_path: str, index: pd.DataFrame, names: list[str], out_dir: Path,
                     workers: int = 8, retries: int = 5) -> dict:
    rows = index.set_index("name", drop=False)
    missing = sorted(set(names) - set(rows.index))
    if missing:
        raise ValueError(f"{len(missing)} needed images are not in the zip, e.g. {missing[:3]}")
    out_dir.mkdir(parents=True, exist_ok=True)
    read = range_reader(fs, zip_path)
    todo = [rows.loc[n] for n in names
            if not ((out_dir / n).exists() and (out_dir / n).stat().st_size == rows.loc[n, "file_size"])]

    def one(row):
        for attempt in range(retries):
            try:
                data = fetch_member(read, row)
                tmp = out_dir / (row["name"] + ".part")
                tmp.write_bytes(data)
                tmp.replace(out_dir / row["name"])
                return
            except Exception:  # network errors, 429 rate limits, bad reads
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)

    done, start = 0, time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(one, r) for r in todo]):
            future.result()
            done += 1
            if done % 500 == 0 or done == len(todo):
                rate = done / max(time.time() - start, 1e-9)
                print(f"  {done}/{len(todo)} images, {rate:.1f}/s, "
                      f"about {(len(todo) - done) / max(rate, 1e-9) / 60:.0f} min left", flush=True)
    return {"needed": len(names), "skipped_existing": len(names) - len(todo), "fetched": len(todo)}


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT, fs=None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--splits", type=Path, default=Path("data/processed/splits/split-v1"))
    parser.add_argument("--taste-dir", type=Path, default=Path("data/raw/taste"))
    parser.add_argument("--cr-dir", type=Path, default=Path("data/raw/creativeranking"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--skip-taste", action="store_true")
    args = parser.parse_args(argv)
    try:
        taste_dir = inside_data(args.taste_dir, repo_root)
        cr_dir = inside_data(args.cr_dir, repo_root)
    except ValueError as error:
        parser.error(str(error))
    split_dir = args.splits if args.splits.is_absolute() else repo_root / args.splits
    report = {"retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    if not args.skip_taste:
        from huggingface_hub import snapshot_download

        snapshot_download(TASTE_REPO, repo_type="dataset", revision=TASTE_REV,
                          allow_patterns=["images/*"], local_dir=taste_dir)
        names = needed_images(split_dir, "taste")
        absent = [n for n in names if not (taste_dir / n).exists()]
        if absent:
            raise SystemExit(f"{len(absent)} TASTE images are missing, e.g. {absent[:3]}")
        report["taste"] = {"repo": TASTE_REPO, "revision": TASTE_REV, "images": len(names)}
        print("taste:", report["taste"])

    if fs is None:
        from huggingface_hub import HfFileSystem

        fs = HfFileSystem()
    zip_path = f"datasets/{CR_REPO}@{CR_REV}/images.zip"
    index_path = cr_dir / "zip_index.parquet"
    if index_path.exists():
        index = pd.read_parquet(index_path)
    else:
        print("reading the images.zip directory (a few minutes, once)...", flush=True)
        index = zip_index(fs, zip_path)
        cr_dir.mkdir(parents=True, exist_ok=True)
        index.to_parquet(index_path, index=False)
    names = needed_images(split_dir, "creativeranking")
    report["creativeranking"] = {
        "repo": CR_REPO, "revision": CR_REV, "zip_entries": len(index),
        **fetch_zip_images(fs, zip_path, index, names, cr_dir / "images", workers=args.workers),
    }
    print("creativeranking:", report["creativeranking"])
    (cr_dir / "images_provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    main()
