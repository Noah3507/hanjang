"""Measure load time, rank_ads time and peak memory of the bundle (step 11, for A's worker settings).

Run from the repository root, inside .venv-rank (Windows, macOS or Linux):
  python scripts/ml_benchmark_inference.py --bundle artifacts/models/ranking/bt-logistic-v1

Loads the bundle once (timed separately), ranks the four fixture ads once cold
and --repeats times warm, and prints one JSON line: load seconds, first and
warm rank_ads seconds (median, p95, max), peak process memory in MB, platform
and package versions. Uses only the standard library for memory (no psutil).
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # allow "python scripts/..." from the repo root

from ml.inference import RankInput, load_model, rank_ads
from ml.inference.bundle import installed_versions


def peak_memory_mb() -> float | None:
    """Peak resident memory of this process (Windows: PeakWorkingSetSize)."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        process = ctypes.windll.kernel32.GetCurrentProcess()
        if not ctypes.windll.psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
            return None
        return counters.PeakWorkingSetSize / 1e6
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / 1e6 if sys.platform == "darwin" else peak / 1e3  # macOS bytes, Linux kilobytes


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bundle", type=Path, default=Path("artifacts/models/ranking/bt-logistic-v1"))
    parser.add_argument("--images", type=Path, default=Path("tests/fixtures/ads"))
    parser.add_argument("--repeats", type=int, default=20)
    args = parser.parse_args(argv)
    resolve = lambda p: p if p.is_absolute() else repo_root / p  # noqa: E731
    images = sorted(resolve(args.images).glob("*.png"))[:4]
    if len(images) != 4:
        raise SystemExit("need four PNG ads")
    items = [RankInput(p.stem, p) for p in images]

    start = time.perf_counter()
    model = load_model(resolve(args.bundle))
    load_seconds = time.perf_counter() - start
    start = time.perf_counter()
    first = rank_ads(items, model)
    first_seconds = time.perf_counter() - start
    warm = []
    for _ in range(args.repeats):
        start = time.perf_counter()
        again = rank_ads(items, model)
        warm.append(time.perf_counter() - start)
        if again["items"] != first["items"]:
            raise SystemExit("rank_ads is not deterministic")
    warm.sort()
    result = {
        "model_version": model.model_version, "load_seconds": round(load_seconds, 3),
        "rank_ads_first_seconds": round(first_seconds, 3),
        "rank_ads_warm_seconds": {"median": round(statistics.median(warm), 4),
                                  "p95": round(warm[max(0, int(0.95 * len(warm)) - 1)], 4),
                                  "max": round(warm[-1], 4), "repeats": len(warm)},
        "peak_memory_mb": round(peak_memory_mb() or 0, 1) or None,
        "platform": platform.platform(), "python": platform.python_version(),
        "packages": installed_versions(),
    }
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
