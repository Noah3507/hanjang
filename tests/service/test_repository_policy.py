"""Exercise the checker against real Git indexes, without touching this repo."""

from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
GIT = shutil.which("git") or "C:/Program Files/Git/cmd/git.exe"


@pytest.fixture
def repository(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(ROOT / "scripts/service_check_repository.py", scripts)
    subprocess.run([GIT, "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def stage(repository, name, content):
    path = repository / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    subprocess.run([GIT, "add", "--", name], cwd=repository, check=True)


def check(repository, *args):
    return subprocess.run(
        [sys.executable, str(repository / "scripts/service_check_repository.py"), *args],
        cwd=repository, capture_output=True, text=True,
    )


def test_clean_env_example_and_conventional_title_pass(repository):
    stage(repository, ".env.example", "HANJANG_CORS_ORIGINS=[]\n")
    assert check(repository, "--pr-title", "ci(policy): check repository inputs").returncode == 0


@pytest.mark.parametrize("name", [".env", "frontend/.env.local", "notes.tmp", "uploads/photo.txt"])
def test_private_or_temporary_staged_files_fail(repository, name):
    stage(repository, name, "not a real secret\n")
    assert check(repository).returncode == 1


def test_staged_secret_is_detected_even_after_working_copy_is_cleaned(repository):
    fake_secret = "sk-" + "x" * 40
    stage(repository, "config.txt", fake_secret)
    (repository / "config.txt").write_text("clean working copy", encoding="utf-8")
    result = check(repository)
    assert result.returncode == 1
    assert "possible secret pattern" in result.stdout
    assert fake_secret not in result.stdout
    assert fake_secret not in result.stderr


def test_nonconventional_title_fails_without_echoing_it(repository):
    result = check(repository, "--pr-title", "Update everything")
    assert result.returncode == 1
    assert "Update everything" not in result.stdout
