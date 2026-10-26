"""Tests for scripts/ml_inspect_hf_dataset.py. Nothing is downloaded."""

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ml_inspect_hf_dataset.py"
spec = importlib.util.spec_from_file_location("ml_inspect_hf_dataset", SCRIPT)
inspect_hf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspect_hf)

REPO = "someone/dataset"
SHA = "a" * 40
CONTENT = b"hello dataset\n"


@pytest.fixture
def fake_hub(monkeypatch):
    """Replace the network calls; record every download request."""
    calls = []

    class FakeApi:
        def dataset_info(self, repo_id, revision=None):
            return SimpleNamespace(sha=revision or "b" * 40, card_data={"license": "mit"})

    def fake_download(repo_id, filename, repo_type, revision, local_dir):
        calls.append({"repo_id": repo_id, "file": filename, "revision": revision})
        path = Path(local_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(CONTENT)
        return str(path)

    monkeypatch.setattr(inspect_hf, "HfApi", FakeApi)
    monkeypatch.setattr(inspect_hf, "hf_hub_download", fake_download)
    return calls


def run(tmp_path, *args):
    inspect_hf.main(list(args), repo_root=tmp_path)


def test_download_records_revision_and_sha256(tmp_path, fake_hub):
    run(tmp_path, REPO, "--revision", SHA, "--download", "a.txt", "--out", "data/raw/x")
    provenance = json.loads((tmp_path / "data/raw/x/provenance.json").read_text())
    assert provenance["repo_id"] == REPO
    [record] = provenance["files"]
    assert record["file"] == "a.txt"
    assert record["revision"] == SHA
    assert record["bytes"] == len(CONTENT)
    assert record["sha256"] == hashlib.sha256(CONTENT).hexdigest()
    assert fake_hub == [{"repo_id": REPO, "file": "a.txt", "revision": SHA}]


@pytest.mark.parametrize("out", ["outside", "data", "data/../ml", "/tmp/elsewhere"])
def test_out_outside_data_is_rejected(tmp_path, fake_hub, out):
    with pytest.raises(SystemExit):
        run(tmp_path, REPO, "--revision", SHA, "--download", "a.txt", "--out", out)
    assert fake_hub == []


@pytest.mark.parametrize("revision", [None, "main", "abc123"])
def test_download_without_pinned_revision_is_rejected(tmp_path, fake_hub, revision):
    args = [REPO, "--download", "a.txt", "--out", "data/raw/x"]
    if revision is not None:
        args += ["--revision", revision]
    with pytest.raises(SystemExit):
        run(tmp_path, *args)
    assert fake_hub == []


def test_existing_provenance_is_updated_not_duplicated(tmp_path, fake_hub):
    run(tmp_path, REPO, "--revision", SHA, "--download", "a.txt", "--out", "data/raw/x")
    run(tmp_path, REPO, "--revision", SHA, "--download", "a.txt", "b.txt", "--out", "data/raw/x")
    provenance = json.loads((tmp_path / "data/raw/x/provenance.json").read_text())
    assert sorted(f["file"] for f in provenance["files"]) == ["a.txt", "b.txt"]


def test_provenance_of_another_dataset_is_rejected(tmp_path, fake_hub):
    run(tmp_path, REPO, "--revision", SHA, "--download", "a.txt", "--out", "data/raw/x")
    with pytest.raises(SystemExit):
        run(tmp_path, "other/dataset", "--revision", SHA, "--download", "a.txt",
            "--out", "data/raw/x")
    provenance = json.loads((tmp_path / "data/raw/x/provenance.json").read_text())
    assert provenance["repo_id"] == REPO
