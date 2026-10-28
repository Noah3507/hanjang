"""Tests for ml/data/outputs.py: all-or-nothing output folders."""

from pathlib import Path

import pytest

from ml.data.outputs import staged_output


def _write(folder: Path, text: str) -> None:
    with staged_output(folder) as tmp:
        (tmp / "result.txt").write_text(text)


def test_success_replaces_the_folder_and_leaves_no_hidden_folders(tmp_path):
    out = tmp_path / "data" / "out"
    _write(out, "v1")
    _write(out, "v2")
    assert (out / "result.txt").read_text() == "v2"
    assert [p.name for p in out.parent.iterdir()] == ["out"]


def test_error_while_writing_keeps_the_previous_folder(tmp_path):
    out = tmp_path / "data" / "out"
    _write(out, "v1")
    with pytest.raises(RuntimeError):
        with staged_output(out) as tmp:
            (tmp / "result.txt").write_text("half")
            raise RuntimeError("step failed")
    assert (out / "result.txt").read_text() == "v1"
    assert [p.name for p in out.parent.iterdir()] == ["out"]


def test_failed_final_rename_restores_the_previous_folder(tmp_path, monkeypatch):
    out = tmp_path / "data" / "out"
    _write(out, "v1")
    real_rename = Path.rename

    def flaky_rename(self, target):
        if ".tmp-" in self.name:  # the new folder cannot be moved into place
            raise PermissionError("simulated lock on the new folder")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", flaky_rename)
    with pytest.raises(PermissionError):
        _write(out, "v2")
    monkeypatch.undo()
    assert (out / "result.txt").read_text() == "v1"
    assert [p.name for p in out.parent.iterdir()] == ["out"]
