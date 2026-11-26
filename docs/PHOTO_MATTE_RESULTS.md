# Photo matte integration results

Base main `eb0fc34`, merged PR #71. `git apply --check` and application of B's
`photo-matte-for-A.patch` succeeded. No font, photo_mode, template, frontend,
copy-generation or B ML/script files changed. Source photos/models/environment,
transfer files, previous outputs and paid ledger remain untouched.

## Patch and safety fixes

B's faint + near cleanup is used immediately after model/original alpha minimum.
FAINT_ALPHA64, SOLID_ALPHA128, NEAR_FRACTION0.03 and core MIN_PIECE0.01 remain.
RGB is not modified by cleanup; the existing resize remains the only spatial
resampling. New processing reports `u2netp-matte-cleanup-v1-preserve-solid`.

Three corrections were required:

- Original patch removed a disconnected opaque piece smaller than1% of total
  core area. Area alone cannot prove noise: preserve **all alpha>=128** pixels,
  including small pieces outside the filtered core's zone. Soft surroundings of
  tiny pieces are still heuristic, not a complete product-preservation guarantee.
- Empty arrays reached OpenCV and reproduced a native access-violation/C++ error.
  Guard empty/non-2D input, do not mutate input, and retain the existing sanitized
  PHOTO_PROCESSING_FAILED contract for cleanup exceptions.
- Large full-resolution ellipse dilation was expensive. Keep the **exact same**
  OpenCV ellipse by decomposing it into the union of centered rectangles; dilation
  distributes over that union. Pixel-equivalence tests cover both implementations
  and branch radii. Row/column bbox extrema avoid image-sized coordinate arrays.
  No alpha/radius threshold was tuned to reduce haze scores.

## Supplied eleven-product evidence (B's results, not reproduced by A)

`transfer/haze.json` and the comparison sheet were inspected. B's two example
poster backgrounds help show residue, but these composites cannot establish
ground-truth product edges or reconstruct original alpha masks.

| Supplied label | raw haze | B both haze | B removed alpha mass share |
| --- | ---: | ---: | ---: |
| Chicken | .0589 | .0116 | .0498 |
| Americano | .0235 | .0004 | .0247 |
| Smoothie | .0189 | .0050 | .0236 |
| Vegetable juice | .0044 | .0010 | .0063 |
| Gimbap | .0041 | .0024 | .0033 |
| Hotpot | .0101 | .0025 | .0083 |

All11 rows include cake/noodle/poke/salad/unadong too. Source products.csv and
identifiable corresponding11 original/mask pairs were not available in the
project/adjacent design assets. The supplied Americano row appears to use an
opaque cup, so it is **not a glass-cup validation**. Small smoothie decorations,
juice glass edges and hotpot handles need original/mask comparison to establish
whether removal is background or real product. Lower haze is not semantic proof.

## A's actual two-photo verification

B's `scripts/ml_cutout_haze.py` was imported/run unchanged on actual jjajang and
espresso sources. The main processor was captured from Git for the before arm.
The successful comparison replay reused previous verified pre-cleanup rembg
cutouts, checking source size and all RGB pixels before using cached alpha.
The first comparison attempt made two fresh local-model inferences, then failed
only in the report's strict Palette list/tuple parser; that was corrected to JSON
validation. No new paid output was substituted. Cached actual LLM v7 copy and
analysis/style context were identical in each before/after advertisement pair.

| Actual source | Before haze | After haze | Removed alpha mass | Changed >=128 pixels | RGB |
| --- | ---: | ---: | ---: | ---: | --- |
| Jjajang | .0085 | .0022 | .7953% | 0 | All equal, unresized |
| Espresso | .0001 | .0000 | .1956% | 0 | All equal, unresized |

Haze is B's mask-confidence heuristic, not measured background-area accuracy.
The script rounds it to four decimals; displayed .0000 does not prove zero haze.
Removed alpha mass includes all removed soft opacity, not necessarily only haze.
Cleanup samples on actual masks: jjajang about9ms; espresso about9–26ms.
Actual original files stayed byte-identical. Full poster product pixels need not
be identical: cleaned alpha changes support bounds and the existing renderer may
therefore place/scale the preserved source differently. There is no recoloring.

Actual Chromium PNGs use emotional_a/light and visual_c/dark for both products.
The unchanged rembg/matte pipeline still has imperfect edges; no claim of
commercially perfect segmentation or complete physical product preservation.

## Glass/sem transparency limitation

**Actual glass, ice/liquid transparency and the eleven original products remain
unverified.** In a clearly labelled synthetic glass-like fixture, all22300 soft
pixels at alpha48 were removed while opaque pixels were preserved. This exposes
the expected risk of threshold64; it is not a measured real-glass loss result.
Changing thresholds without real glass evidence would invent a new calibration,
so64 is retained. Do not approve transparent-product quality from haze alone.
When cutout quality is uncertain, compare the unchanged original and use the
existing original-photo option. Real glass RGB originals plus pre/post alpha
files are needed before claiming safe glass handling; no new classifier or
automatic mask rewrite is introduced to hide this uncertainty.

## Processing/cache and compatibility

PhotoResponse gains additive nullable `processing_version`. Legacy/unknown
results are null; newly successful worker results carry the version through the
existing JSON boundary. Missing version in an older worker response remains
supported. New processing is not falsely attributed to existing assets.

Completed-photo cache behavior is unchanged: no model invocation, migration,
batch replacement or automatic retry on a version mismatch. Existing originals,
processed PNGs and ads are preserved. There is no new reprocessing endpoint.
Existing failed-processing retry uses the new code. A new selected processed
asset changes the existing asset/hash dependency and stales rendering/ranking;
old PNGs remain private/readable until normal TTL. Metadata alone does not
pretend the pixels changed. photo_mode source selection/normalization is untouched.

An isolated real worker returned the new version and a valid PNG. The
fresh-worker jjajang PNG SHA256 exactly matched the successful cached-mask
comparison PNG, providing an additional check of replay provenance. Isolated
service/Chromium compatibility used actual new cutouts, stored actual copy/CLIP
replay, real bt-logistic-v1 and actual PNG/PDF: cutout→original→cutout, all16
jjajang original templates, title/price edit, style/other-assets preservation,
stale download rejection. Transitions made0 additional LLM/rembg calls; source
RGB original mode remains unchanged. These tests did not touch the live server.

## Time and memory scope

Three synthetic stress runs, Windows, fresh process, same mask/rule:

| Alpha dimensions | Original ellipse median | Equivalent optimized median | Optimized process peak Working Set |
| --- | ---: | ---: | ---: |
| 1600×1600 | .0830s | .0642s | 67.6MiB |
| 4000×6000 (24MP) | 20.672s | 7.128s | 346.9MiB |

Peak measured using Windows GetProcessMemoryInfo includes Python/NumPy/OpenCV,
mask arrays and test assertions, **not rembg/Chromium or full-service memory**.
Full-resolution24MP remains heavier than1600px; it is not advertised as a fixed
latency. Existing90s worker timeout/fallback is unchanged. Large coordinates are
reduced to row/column extrema, but connected-component labels still use memory.
No process-memory improvement is claimed. Raw three-run data: local performance.json.

## Tests and local review

- Full backend:725 passed,44 explicit opt-in skips.
- Latest focused matte/photo API:23 passed, including the later added selected
  asset→stale-rank/old-PNG preservation case (Ranking fixture explicitly mock).
- Matte14 tests include B's five tests, exact ellipse equivalence, all-RGB/input
  alpha preservation, tiny pieces, empty masks, determinism and failure contract.
- Actual compatibility/model/PNG/PDF assertions passed; Chromium decoded20
  comparison images and43 compatibility images with console/pageerror0.
  Existing Starlette/AnyIO deprecation warning remains.
- Frontend unchanged; existing frontend/type/build/browser/release CI exercises
  integration. No opaque product-area safety is inferred from CI success.

Open `artifacts/photo-matte-20261126/final-comparison/gallery.html`; compare
before/after on both backgrounds and inspect the explicitly synthetic glass
fixture. `comparison.json` contains original numbers and actual measurements.
B's two-photo diagnostic is in its `b-diagnostic-two-photos/` subfolder.
`artifacts/photo-matte-20261126/compat/gallery.html` has the43-image mode/edit
regression, and worker-check.json records actual subprocess/version evidence.

Paid LLM/image calls0. Ledger15/$0.02431050 SHA256 unchanged. No font/photo_mode/
template/frontend/ML/script changes, no server restart, deployment or main merge.
User review and explicit merge approval remain required. The material remaining
risk is **real transparent-product edge preservation**, not a proven fixed issue.
