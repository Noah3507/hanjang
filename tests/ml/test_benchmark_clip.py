"""Tests for scripts/ml_benchmark_clip.py. No model weights are downloaded."""

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ml_benchmark_clip.py"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ads"


def load_script():
    spec = importlib.util.spec_from_file_location("ml_benchmark_clip", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bench = load_script()


def make_ads(folder, count=4, size=(1080, 1350), mode="RGB"):
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        Image.new(mode, size).save(folder / f"ad{i}.png")
    return folder


def test_script_imports_without_unix_resource_module(monkeypatch):
    # Windows Python has no "resource" module; importing the script must still work.
    monkeypatch.setitem(sys.modules, "resource", None)
    load_script()


def test_peak_memory_uses_windows_api_on_windows(monkeypatch):
    monkeypatch.setitem(sys.modules, "resource", None)
    monkeypatch.setattr(bench.sys, "platform", "win32")
    monkeypatch.setattr(bench, "_peak_rss_windows_mb", lambda: 123.0)
    assert bench.peak_rss_mb() == 123.0


@pytest.mark.skipif(sys.platform == "win32", reason="Unix memory path")
def test_peak_memory_is_positive_here():
    assert bench.peak_rss_mb() > 0


@pytest.mark.skipif(not FIXTURES.exists(), reason="shared ad fixtures not present")
def test_shared_fixtures_are_valid_ads():
    assert len(bench.find_ad_images(FIXTURES)) == 4


@pytest.mark.parametrize(
    "count, size, mode",
    [(3, (1080, 1350), "RGB"), (5, (1080, 1350), "RGB"),
     (4, (1080, 1080), "RGB"), (4, (1080, 1350), "RGBA")],
)
def test_invalid_ads_are_rejected(tmp_path, count, size, mode):
    folder = make_ads(tmp_path / "ads", count, size, mode)
    with pytest.raises(ValueError):
        bench.find_ad_images(folder)


@pytest.mark.parametrize("text", ["0", "-1"])
def test_warm_runs_must_be_at_least_one(text):
    with pytest.raises(argparse.ArgumentTypeError):
        bench.positive_int(text)


def test_bad_input_stops_before_loading_a_model(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("model must not be loaded for invalid inputs")

    monkeypatch.setattr(bench.open_clip, "create_model_and_transforms", fail)
    folder = make_ads(tmp_path / "ads", size=(500, 500))
    with pytest.raises(SystemExit):
        bench.main(["--model", "ViT-B-32", "--images", str(folder)])
    with pytest.raises(SystemExit):
        bench.main(["--model", "ViT-B-32", "--warm-runs", "0"])
