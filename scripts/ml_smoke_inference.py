"""Smoke check of a model bundle on any computer (step 12 handoff).

Run from the repository root, inside .venv-rank:
  python scripts/ml_smoke_inference.py            # check: compare with ml/inference/smoke_expected.json
  python scripts/ml_smoke_inference.py --record   # B only: write the expected values from B's bundle

The check loads the bundle with ml.inference.load_model (which verifies every
SHA-256 in the manifest), compares the manifest's file hashes with the ones B
recorded, ranks the four synthetic fixture ads and compares the result:
ranks must be identical, scores and pairwise values may differ by at most
--tolerance (default 1e-3; CPUs and math libraries round float32 slightly
differently, while the closest fixture scores are about 0.03 apart).
Prints PASS or FAIL with the largest difference; exits with 1 on FAIL.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # allow "python scripts/..." from the repo root

from ml.inference import RankInput, load_model, rank_ads
from ml.inference.bundle import installed_versions, read_manifest

BUNDLE = "artifacts/models/ranking/bt-logistic-v1"
EXPECTED = "ml/inference/smoke_expected.json"
FIXTURES = "tests/fixtures/ads"
IDS = ("c_emotional", "c_price", "c_visual", "c_brand")


def run(bundle: Path, fixtures: Path) -> tuple[dict, dict]:
    model = load_model(bundle, model_file=bundle / "model.safetensors")
    items = [RankInput(i, fixtures / f"{i[2:]}.png") for i in IDS]
    return read_manifest(bundle), rank_ads(items, model)


def compare(expected: dict, manifest: dict, ranking: dict, tolerance: float) -> list[str]:
    problems = []
    if manifest["model_version"] != expected["model_version"]:
        problems.append(f"model_version {manifest['model_version']} != {expected['model_version']}")
    hashes = {name: f["sha256"] for name, f in manifest["files"].items()}
    if hashes != expected["files_sha256"]:
        problems.append("bundle file hashes differ from the recorded bundle")
    got = {i["candidate_id"]: i for i in ranking["items"]}
    for candidate, want in expected["items"].items():
        if got[candidate]["rank"] != want["rank"]:
            problems.append(f"{candidate}: rank {got[candidate]['rank']} != {want['rank']}")
        if abs(got[candidate]["score"] - want["score"]) > tolerance:
            problems.append(f"{candidate}: score {got[candidate]['score']:.6f} != {want['score']:.6f}")
    pairs = {(p["candidate_a_id"], p["candidate_b_id"]): p["probability_a_preferred"]
             for p in ranking["pairwise"]["comparisons"]}
    for key, want in expected["pairwise"].items():
        a, b = key.split("|")
        if abs(pairs[(a, b)] - want) > tolerance:
            problems.append(f"pairwise {a}-{b}: {pairs[(a, b)]:.6f} != {want:.6f}")
    return problems


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bundle", type=Path, default=Path(BUNDLE))
    parser.add_argument("--expected", type=Path, default=Path(EXPECTED))
    parser.add_argument("--tolerance", type=float, default=1e-3)
    parser.add_argument("--record", action="store_true", help="B only: write the expected values")
    args = parser.parse_args(argv)
    resolve = lambda p: p if p.is_absolute() else repo_root / p  # noqa: E731
    bundle, expected_path = resolve(args.bundle), resolve(args.expected)
    manifest, ranking = run(bundle, repo_root / FIXTURES)

    if args.record:
        expected = {
            "model_version": manifest["model_version"],
            "files_sha256": {name: f["sha256"] for name, f in manifest["files"].items()},
            "items": {i["candidate_id"]: {"score": i["score"], "rank": i["rank"]} for i in ranking["items"]},
            "pairwise": {f"{p['candidate_a_id']}|{p['candidate_b_id']}": p["probability_a_preferred"]
                         for p in ranking["pairwise"]["comparisons"]},
            "note": "synthetic fixture ads: the order checks reproducibility only, not ad quality",
            "recorded_on": {"platform": platform.platform(), "python": platform.python_version(),
                            "packages": installed_versions()},
        }
        expected_path.write_text(json.dumps(expected, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"recorded {expected_path.relative_to(repo_root) if expected_path.is_relative_to(repo_root) else expected_path}")
        return {"recorded": expected}

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    problems = compare(expected, manifest, ranking, args.tolerance)
    got = {i["candidate_id"]: i for i in ranking["items"]}
    worst = max(abs(got[c]["score"] - w["score"]) for c, w in expected["items"].items())
    for candidate in IDS:
        print(f"  {candidate:12s} rank {got[candidate]['rank']}  score {got[candidate]['score']:+.6f}")
    print(f"largest score difference {worst:.2e} (tolerance {args.tolerance:g}), platform {platform.platform()}")
    if problems:
        print("FAIL")
        for problem in problems:
            print("  -", problem)
        raise SystemExit(1)
    print("PASS")
    return {"passed": True, "largest_score_difference": worst}


if __name__ == "__main__":
    main()
