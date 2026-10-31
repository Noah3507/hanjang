"""Tests for the inference package (step 11). A tiny random CLIP stands in for ViT-B/32: no download."""

import dataclasses
import importlib.util
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import open_clip
import pytest
from PIL import Image
from safetensors.numpy import save_file

from ml.features.clip_features import ClipEncoder, feature_version
from ml.inference import (
    ArtifactMismatch,
    InferenceFailure,
    InvalidImage,
    ModelNotAvailable,
    RankInput,
    RankingError,
    extract_features,
    load_model,
    rank_ads,
    score_ad,
)
from ml.inference.bundle import write_bundle

ROOT = Path(__file__).resolve().parents[2]
ADS = ROOT / "tests/fixtures/ads"
SCHEMA = json.loads((ROOT / "tests/fixtures/contracts/rank-output.schema.json").read_text())
STATS = ["brightness", "contrast", "saturation", "n_colors"]
TINY = "hanjang-tiny-test"
TINY_CFG = {"embed_dim": 8,
            "vision_cfg": {"image_size": 224, "layers": 1, "width": 32, "head_width": 16, "patch_size": 32},
            "text_cfg": {"context_length": 8, "vocab_size": 64, "width": 16, "heads": 2, "layers": 1}}


def _items(paths=None):
    names = ["c_emotional", "c_price", "c_visual", "c_brand"]
    paths = paths or [ADS / f"{n[2:]}.png" for n in names]
    return [RankInput(n, p) for n, p in zip(names, paths)]


def _train_files(folder: Path, dim: int, version: str, seed: int = 0):
    rng = np.random.default_rng(seed)
    n = dim + 4
    save_file({"weights": rng.normal(size=n), "scaler_mean": rng.normal(size=n) * 0.01,
               "scaler_std": rng.random(n) + 0.5}, str(folder / "model.safetensors"))
    (folder / "model_config.json").write_text(json.dumps({
        "model_version": "bt-test-v1", "feature_version": version,
        "feature_columns": [f"clip_{i}" for i in range(dim)] + STATS,
        "stats": {"version": "stats-v1", "columns": STATS}}))


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    config_dir = tmp_path_factory.mktemp("cfg")
    (config_dir / f"{TINY}.json").write_text(json.dumps(TINY_CFG))
    open_clip.add_model_config(config_dir)
    encoder = ClipEncoder.load(TINY, pretrained=None)
    version = feature_version(encoder.metadata(), "stats-v1")
    source, out = tmp_path_factory.mktemp("trained"), tmp_path_factory.mktemp("bundle")
    _train_files(source, TINY_CFG["embed_dim"], version)
    write_bundle(source, out, encoder, code={"commit": "test", "dirty": False})
    return out


@pytest.fixture
def copy(bundle, tmp_path):
    target = tmp_path / "bundle"
    shutil.copytree(bundle, target)
    return target


def _check(value, schema, defs):
    """A minimal JSON Schema check for rank-output.schema.json."""
    if "$ref" in schema:
        return _check(value, defs[schema["$ref"].split("/")[-1]], defs)
    if "anyOf" in schema:
        assert any(_ok(value, s, defs) for s in schema["anyOf"])
        return
    kind = schema.get("type")
    if kind == "object":
        assert isinstance(value, dict) and set(schema["required"]) <= set(value)
        assert set(value) <= set(schema["properties"])
        for key, item in value.items():
            _check(item, schema["properties"][key], defs)
    elif kind == "array":
        assert isinstance(value, list) and schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 1e9)
        for item in value:
            _check(item, schema["items"], defs)
    elif kind == "string":
        assert isinstance(value, str) and len(value) >= schema.get("minLength", 0)
        assert "const" not in schema or value == schema["const"]
    elif kind in ("number", "integer"):
        assert isinstance(value, (int, float)) and math.isfinite(value)
        assert kind == "number" or isinstance(value, int)
        assert schema.get("minimum", -math.inf) <= value <= schema.get("maximum", math.inf)
    elif kind == "null":
        assert value is None


def _ok(value, schema, defs):
    try:
        _check(value, schema, defs)
        return True
    except AssertionError:
        return False


def test_rank_ads_matches_the_contract_schema_and_keeps_input_order(bundle):
    model = load_model(bundle)
    out = rank_ads(_items(), model)
    _check(out, SCHEMA, SCHEMA["$defs"])
    assert [i["candidate_id"] for i in out["items"]] == ["c_emotional", "c_price", "c_visual", "c_brand"]
    by_score = sorted(out["items"], key=lambda i: (-i["score"], i["candidate_id"]))
    assert [i["rank"] for i in by_score] == [1, 2, 3, 4]
    assert (out["model_version"], out["feature_version"]) == (model.model_version, model.feature_version)


def test_pairwise_is_six_sorted_pairs_of_the_sigmoid_of_score_differences(bundle):
    out = rank_ads(_items(), load_model(bundle))
    score = {i["candidate_id"]: i["score"] for i in out["items"]}
    pairs = out["pairwise"]["comparisons"]
    assert out["pairwise"]["method"] == "bradley_terry_sigmoid_v1"
    assert [(p["candidate_a_id"], p["candidate_b_id"]) for p in pairs] == [
        ("c_brand", "c_emotional"), ("c_brand", "c_price"), ("c_brand", "c_visual"),
        ("c_emotional", "c_price"), ("c_emotional", "c_visual"), ("c_price", "c_visual")]
    for p in pairs:
        expected = 1 / (1 + math.exp(-(score[p["candidate_a_id"]] - score[p["candidate_b_id"]])))
        assert p["probability_a_preferred"] == pytest.approx(expected, abs=1e-12)


def test_score_ad_equals_rank_ads_and_the_manual_formula(bundle):
    model = load_model(bundle)
    out = rank_ads(_items(), model)
    for item, row in zip(_items(), out["items"]):
        assert abs(score_ad(item.rendered_image_path, model) - row["score"]) <= 1e-6
        x = extract_features(item.rendered_image_path, model)
        manual = float(((x - model._scaler_mean) / model._scaler_std) @ model._weights)
        assert row["score"] == pytest.approx(manual, abs=1e-12)


def test_feature_vector_is_float64_finite_read_only_in_column_order(bundle):
    model = load_model(bundle)
    x = extract_features(ADS / "price.png", model)
    assert x.dtype == np.float64 and x.shape == (len(model.feature_columns),) and np.isfinite(x).all()
    assert model.feature_columns[-4:] == tuple(STATS) and not x.flags.writeable
    assert abs(np.linalg.norm(x[:-4]) - 1) < 1e-5  # L2-normalized CLIP part, as in training


def test_ties_are_broken_by_candidate_id(bundle):
    same = ADS / "visual.png"
    out = rank_ads(_items([same, ADS / "price.png", same, ADS / "brand.png"]), load_model(bundle))
    tie = {i["candidate_id"]: i for i in out["items"] if i["candidate_id"] in ("c_emotional", "c_visual")}
    assert tie["c_emotional"]["score"] == tie["c_visual"]["score"]
    assert tie["c_emotional"]["rank"] < tie["c_visual"]["rank"]  # "c_emotional" < "c_visual"


def test_results_are_reproducible_across_loads(bundle):
    assert rank_ads(_items(), load_model(bundle)) == rank_ads(_items(), load_model(bundle))


def test_model_handle_cannot_be_changed(bundle):
    model = load_model(bundle)
    with pytest.raises(dataclasses.FrozenInstanceError):
        model.model_version = "other"
    with pytest.raises(ValueError):
        model._weights[0] = 1.0
    with pytest.raises(TypeError):
        model.clip["model"] = "other"
    encoder = model._encoder.model
    assert not encoder.training and not any(p.requires_grad for p in encoder.parameters())
    assert model.close_call_score_gap == 0.2 and model.device == "cpu"


@pytest.mark.parametrize("items", [
    lambda: _items()[:3],
    lambda: [RankInput("same", ADS / "price.png")] * 4,
    lambda: [("c1", ADS / "price.png")] * 4,
])
def test_wrong_candidate_lists_are_value_errors(bundle, items):
    with pytest.raises(ValueError):
        rank_ads(items(), load_model(bundle))


def _bad_image(tmp_path, kind):
    path = tmp_path / f"{kind}.png"
    if kind == "jpeg":
        Image.new("RGB", (1080, 1350), "white").save(path, format="JPEG")
    elif kind == "small":
        Image.new("RGB", (1000, 1350), "white").save(path)
    elif kind == "transparent":
        Image.new("RGBA", (1080, 1350), (255, 255, 255, 0)).save(path)
    elif kind == "gray":
        Image.new("L", (1080, 1350), 128).save(path)
    elif kind == "broken":
        path.write_bytes(b"\x89PNG\r\n\x1a\n not really")
    return path


@pytest.mark.parametrize("kind", ["jpeg", "small", "transparent", "gray", "broken", "missing"])
def test_invalid_images_raise_invalid_image(bundle, tmp_path, kind):
    model = load_model(bundle)
    with pytest.raises(InvalidImage) as error:
        score_ad(_bad_image(tmp_path, kind), model)
    assert str(tmp_path) not in str(error.value)  # no absolute paths in messages


def test_fully_opaque_rgba_is_accepted(bundle, tmp_path):
    path = tmp_path / "rgba.png"
    Image.open(ADS / "price.png").convert("RGBA").save(path)
    model = load_model(bundle)
    assert score_ad(path, model) == pytest.approx(score_ad(ADS / "price.png", model), abs=1e-9)


def test_missing_bundle_parts_raise_model_not_available(copy, tmp_path):
    with pytest.raises(ModelNotAvailable):
        load_model(tmp_path / "nowhere")
    clip = next((copy / "clip").glob("*.safetensors"))
    clip.unlink()
    with pytest.raises(ModelNotAvailable):
        load_model(copy)
    (copy / "manifest.json").unlink()
    with pytest.raises(ModelNotAvailable):
        load_model(copy)


def _edit_manifest(folder: Path, change):
    path = folder / "manifest.json"
    manifest = json.loads(path.read_text())
    change(manifest)
    path.write_text(json.dumps(manifest))


@pytest.mark.parametrize("change", [
    lambda m: m["feature_columns"].reverse(),
    lambda m: m["packages"].update(torch="0.0.1"),
    lambda m: m.update(manifest_version="ranking-bundle-v0"),
    lambda m: m["clip"].update(preprocessing_version="center-crop-v1"),
    lambda m: m["files"].update({"../outside.txt": {"sha256": "0", "bytes": 0}}),
    lambda m: m.update(close_call_score_gap=0),
])
def test_manifest_mismatches_raise_artifact_mismatch(copy, change):
    _edit_manifest(copy, change)
    with pytest.raises(ArtifactMismatch):
        load_model(copy)


def test_changed_model_bytes_fail_the_checksum(copy):
    path = copy / "model.safetensors"
    data = bytearray(path.read_bytes())
    data[-1] ^= 0xFF
    path.write_bytes(bytes(data))
    with pytest.raises(ArtifactMismatch, match="checksum"):
        load_model(copy)


def test_model_file_must_be_the_one_in_the_manifest(copy, tmp_path):
    assert load_model(copy, model_file=copy / "model.safetensors").model_version == "bt-test-v1"
    with pytest.raises(ArtifactMismatch):
        load_model(copy, model_file=tmp_path / "other.safetensors")


def test_non_finite_features_raise_inference_failure(bundle, monkeypatch):
    model = load_model(bundle)
    monkeypatch.setattr(model._encoder, "encode", lambda images, mode="pad": np.full((1, 8), np.nan, np.float32))
    with pytest.raises(InferenceFailure):
        score_ad(ADS / "price.png", model)
    assert issubclass(InferenceFailure, RankingError) and issubclass(InvalidImage, RankingError)


def test_inference_does_not_import_pandas():
    code = "import sys, ml.inference; assert 'pandas' not in sys.modules, 'pandas imported'"
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)


def test_build_script_writes_a_checked_bundle(bundle, tmp_path):
    spec = importlib.util.spec_from_file_location("ml_build_bundle", ROOT / "scripts/ml_build_bundle.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    model_dir = tmp_path / "artifacts/models/ranking/bt-logistic-v1"
    model_dir.mkdir(parents=True)
    for name in ("model.safetensors", "model_config.json"):
        shutil.copy2(bundle / name, model_dir / name)
    config = json.loads((model_dir / "model_config.json").read_text())
    config["clip"] = {"model": TINY, "pretrained": None}
    (model_dir / "model_config.json").write_text(json.dumps(config))
    shutil.copytree(ADS, tmp_path / "tests/fixtures/ads")
    encoder = load_model(bundle)._encoder
    report = build.main(["--skip-cache-check"], repo_root=tmp_path, encoder=encoder)
    assert set(json.loads((model_dir / "manifest.json").read_text())["files"]) == {
        "model.safetensors", "model_config.json", f"clip/{TINY}-None-visual.safetensors"}
    assert len(report["fixture_ranking"]["items"]) == 4 and (model_dir / "bundle_report.json").exists()
    assert load_model(model_dir).model_version == "bt-test-v1"


def test_loading_does_not_log_the_random_init_warning(bundle, caplog):
    with caplog.at_level("WARNING"):
        load_model(bundle)
    assert "No pretrained weights loaded" not in caplog.text


def _symlink(link: Path, target: Path):
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are not available here (e.g. Windows without the privilege)")


def test_a_file_linked_to_outside_the_bundle_is_rejected(copy, tmp_path):
    clip = next((copy / "clip").glob("*.safetensors"))
    outside = tmp_path / "outside.safetensors"
    clip.rename(outside)  # same bytes, so only the location is wrong
    _symlink(clip, outside)
    with pytest.raises(ArtifactMismatch, match="outside the bundle"):
        load_model(copy)


def test_a_folder_linked_to_outside_the_bundle_is_rejected(copy, tmp_path):
    outside = tmp_path / "outside-clip"
    (copy / "clip").rename(outside)
    _symlink(copy / "clip", outside)
    with pytest.raises(ArtifactMismatch, match="outside the bundle"):
        load_model(copy)


def test_a_manifest_linked_to_outside_the_bundle_is_rejected(copy, tmp_path):
    outside = tmp_path / "manifest.json"
    (copy / "manifest.json").rename(outside)
    _symlink(copy / "manifest.json", outside)
    with pytest.raises(ArtifactMismatch, match="outside the bundle"):
        load_model(copy)


def test_links_that_stay_inside_the_bundle_are_allowed(copy):
    (copy / "clip").rename(copy / "clip-data")
    _symlink(copy / "clip", copy / "clip-data")
    assert load_model(copy).model_version == "bt-test-v1"


@pytest.mark.parametrize("name", ["..\\\\model.safetensors", "C:/model.safetensors", "/etc/passwd"])
def test_windows_style_and_absolute_names_are_rejected(copy, name):
    from ml.inference.bundle import safe_member

    with pytest.raises(ArtifactMismatch):
        safe_member(copy, name)
