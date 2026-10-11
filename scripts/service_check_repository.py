"""Check the Git index for forbidden files and common secret patterns.

This is a supplementary check, not a guarantee against all secrets or PII.
Never print matched values. No dependencies beyond Python and Git.
"""

import argparse
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TITLE = re.compile(r"^(feat|fix|refactor|test|docs|chore|ci|build|perf|style|revert)(\([a-zA-Z0-9_./-]+\))?!?: \S.*$")
SECRET = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    rb"|\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b"
    rb"|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"
    rb"|\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b"
)


def inspect_file(name: str, content: bytes) -> list[str]:
    path = PurePosixPath(name)
    lower = path.name.lower()
    reasons = []
    if (lower == ".env" or lower.startswith(".env.")) and lower != ".env.example":
        reasons.append("real environment file")
    if path.suffix.lower() in {".key", ".pem", ".p12", ".pfx"}:
        reasons.append("private credential file")
    if lower.startswith(("credentials", "service-account")) and lower.endswith(".json"):
        reasons.append("credential JSON file")
    if path.suffix.lower() in {".tmp", ".temp", ".swp"} or lower.endswith("~"):
        reasons.append("temporary file")
    if any(part.lower() in {".aws", ".venv", "node_modules", "uploads", "user_uploads", "artifacts", "tmp"} for part in path.parts):
        reasons.append("local or private runtime directory")
    if SECRET.search(content):
        reasons.append("possible secret pattern")
    return reasons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-title", help="Validate a Conventional Commits PR title")
    args = parser.parse_args()
    failures = []
    if args.pr_title is not None and not TITLE.fullmatch(args.pr_title):
        failures.append("PR title must use Conventional Commits format")
    git = shutil.which("git")
    if git is None:
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/cmd/git.exe"
        if candidate.is_file():
            git = str(candidate)
    if git is None:
        print("Repository check failed: Git is not installed or available")
        return 1
    # Index reads detect staged secrets even if the working copy was cleaned.
    command = [git, "-c", f"safe.directory={ROOT.as_posix()}"]
    try:
        names = subprocess.check_output(command + ["ls-files", "-z"], cwd=ROOT)
        for raw in names.split(b"\0"):
            if not raw:
                continue
            name = raw.decode("utf-8")
            content = subprocess.check_output(command + ["show", f":{name}"], cwd=ROOT)
            for reason in inspect_file(name, content):
                failures.append(f"{name}: {reason}")
    except (subprocess.CalledProcessError, UnicodeError):
        print("Repository check failed: unable to inspect Git index")
        return 1
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("Repository index and requested PR title checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
