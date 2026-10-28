"""Tests for scripts/ml_fetch_images.py with a small local zip. Nothing is downloaded."""

import importlib.util
import zipfile
from pathlib import Path

import fsspec
import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ml_fetch_images.py"
spec = importlib.util.spec_from_file_location("ml_fetch_images", SCRIPT)
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)

FILES = {
    "images/a.png": b"stored bytes " * 100,
    "images/b.png": b"deflated bytes " * 300,
    "images/c.png": b"never needed",
}


def make_zip(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("images/", "")
        z.writestr("images/a.png", FILES["images/a.png"], compress_type=zipfile.ZIP_STORED)
        z.writestr("images/b.png", FILES["images/b.png"], compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("images/c.png", FILES["images/c.png"], compress_type=zipfile.ZIP_STORED)
    return path


@pytest.fixture
def local_zip(tmp_path):
    fs = fsspec.filesystem("file")
    path = str(make_zip(tmp_path / "images.zip"))
    return fs, path, fetch.zip_index(fs, path)


def test_index_lists_files_with_offsets(local_zip):
    _, _, index = local_zip
    assert sorted(index["name"]) == ["a.png", "b.png", "c.png"]
    assert (index["header_offset"] >= 0).all()


@pytest.mark.parametrize("name", ["a.png", "b.png"])
def test_member_bytes_match_for_stored_and_deflated(local_zip, name):
    fs, path, index = local_zip
    row = index.set_index("name").loc[name]
    row["path"] = f"images/{name}"
    assert fetch.fetch_member(fetch.range_reader(fs, path), row) == FILES[f"images/{name}"]


def test_fetch_writes_only_needed_images_and_resumes(local_zip, tmp_path):
    fs, path, index = local_zip
    out = tmp_path / "out"
    first = fetch.fetch_zip_images(fs, path, index, ["a.png", "b.png"], out, workers=2)
    assert first == {"needed": 2, "skipped_existing": 0, "fetched": 2}
    assert (out / "b.png").read_bytes() == FILES["images/b.png"]
    assert not (out / "c.png").exists()
    again = fetch.fetch_zip_images(fs, path, index, ["a.png", "b.png"], out, workers=2)
    assert again == {"needed": 2, "skipped_existing": 2, "fetched": 0}


def test_missing_name_and_corrupt_crc_are_errors(local_zip, tmp_path):
    fs, path, index = local_zip
    with pytest.raises(ValueError):
        fetch.fetch_zip_images(fs, path, index, ["zzz.png"], tmp_path / "out")
    bad = index.copy()
    bad.loc[bad["name"] == "a.png", "crc"] = 0
    with pytest.raises(ValueError):
        fetch.fetch_zip_images(fs, path, bad, ["a.png"], tmp_path / "bad", retries=1)


def test_main_uses_split_files_and_stays_inside_data(local_zip, tmp_path):
    fs, path, _ = local_zip
    splits = tmp_path / "data/processed/splits/split-v1"
    splits.mkdir(parents=True)
    pd.DataFrame({"image_a": ["a.png"], "image_b": ["b.png"]}).to_parquet(splits / "creativeranking.parquet")

    class LocalZipFs:
        """Route the Hugging Face zip path to the local test zip."""
        def open(self, _path, *args, **kwargs):
            return fs.open(path, *args, **kwargs)

    report = fetch.main(["--skip-taste"], repo_root=tmp_path, fs=LocalZipFs())
    assert report["creativeranking"]["fetched"] == 2
    assert (tmp_path / "data/raw/creativeranking/images/a.png").exists()
    assert (tmp_path / "data/raw/creativeranking/zip_index.parquet").exists()
    with pytest.raises(SystemExit):
        fetch.main(["--skip-taste", "--cr-dir", "ml"], repo_root=tmp_path, fs=LocalZipFs())
