# Phase 15 local integration validation — 2026-11-16

## Environment and code

Windows, Python 3.12.10 (`.venv`, `.venv-rank`, `.venv-analysis` reused), Node
24.20.0, existing Playwright 1.64.0 Chromium. Base main `c7892d8`, starting
Phase 14 commit `6cdd2ef`, branch `feat/ad-templates-v3`. No package upgrade or
model/font download in this phase. B source/weights and v2 contracts unchanged.
See [service/API/data contract](DESIGNS_V3_SERVICE.md).

## Automated verification

| Check | Actual result |
|---|---|
| Backend full suite, RUN_RENDER_TESTS=1 and RUN_RANKING_TESTS=1 | **478 passed, zero failed/skipped**, 338.27 seconds |
| Frontend | **73 passed**, 17 files |
| TypeScript | passed |
| Production build | passed, new temporary outDir; presentation dist preserved |
| New service fake-render contract checks | **11 passed** |
| Existing browser editor/diagnostics regressions | **4 passed** |
| Final v3 actual-model browser flow | **1 passed**, 58.8 seconds including runner |
| Final gallery actual Chromium loading | **16 images decoded, pageerror=0** |
| PNG/PDF comparison | one-page A4, actual PDFium render, embedded pixels exactly equal PNG |

After the broad run, the fade promotion backplate received a targeted real
Chromium regression plus re-rendered evidence. `test_template_v3.py` and
`test_designs.py` were re-run together: **22 passed** (72.52 seconds). Earlier broad execution also passed 477 tests before
the new all-sixteen boundary test was added. Counts overlap; do not sum them.

The warning is the existing Starlette/AnyIO BlockingPortal deprecation. No model
tests were represented as successful skips; the explicit local models were used.
No new GitHub Actions run (local commits only, push/PR forbidden).

Relevant commands:

```powershell
$env:RUN_RENDER_TESTS='1'; $env:RUN_RANKING_TESTS='1'; $env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests/service/test_template_v3.py tests/service/test_designs.py -q
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test:ci
npm.cmd --prefix frontend run build -- --outDir <new-temp-directory>
$env:PLAYWRIGHT_EXTERNAL_SERVER='1'; $env:PLAYWRIGHT_FRONTEND_PORT='5186'
$env:PLAYWRIGHT_REQUIRE_RANKING_MODEL='1'
npm.cmd --prefix frontend run test:e2e -- designs-v3.spec.ts editor.spec.ts diagnostics.spec.ts
```

## Browser evidence

Latest v3: `artifacts/phase15/e2e-reviewed/` contains desktop/mobile screenshots,
browser log, raw model ranking evidence, edited PNG/PDF, PDF raster and download
verification. Existing regressions: `artifacts/phase15/e2e-final/` (four passing
editor/diagnostics tests). Development servers use dedicated storage, not the
presentation runtime, with Mock copy / paid=false / empty process API key.

The final mandatory scenario performed actual HTTP and Chromium operations:

1. Save synthetic product/photo, generate four Mock strategy copies and v2 PNGs.
2. Select price on the existing card; generate price A–D with the same copy.
3. Run actual bt-logistic-v1 and show four scores/version separately from rules.
4. Edit A headline, re-render; edit B price to 12,000원, re-render. A is retained,
   B changes, v2 remains revision 1, ranks invalidate.
5. Download A PNG/PDF; one-page PDF embeds exactly those PNG pixels. PDFium
   successfully rasterized it; title was visually reviewed in the downloaded PNG.
6. Generate emotional A–D, return to price revision 3, cancel an unsaved edit.
7. Reload and restore using the existing saved-info GET action; edited price
   set remains available. Download original v2 PNG unchanged by v3.
8. Cancel returns keyboard focus to A's edit button. Mobile width 375px: no
   horizontal document overflow. Browser pageerror=0.

One early attempt found a real textarea-label lookup/accessibility mismatch;
labels now explicitly connect by htmlFor/id. A later assertion counted the new
promotion details as a fifth diagnostic: its scope was corrected to the four
advertisement articles, not weakened. Failure screenshots/trace/video were
preserved under the earlier `e2e-real-model-01`/`e2e-final` folders. The final
v3 retry passed. No existing tests were deleted or relaxed.

API fake-render tests separately cover cached duplicate requests, separate
strategy IDs, original v2 preservation, changed-price scope, edit failure keeping
last PNG, old revisions rejected, ownership/session/TTL, tampered assets,
generation dispatch busy, source changed in flight, stale inference, no silent
Mock fallback and invalid commercial claims. They are not real-image evidence.

## Rendering and visual comparison

Outside Git: `../phase15-work-20261116/review-final/`.

- 48 RGB1080×1350 PNGs: **16 templates × 3 systematically combined cases**.
- `gallery.html` / `gallery.png`: four strategies as rows, A–D as columns.
- `representative/`: square complex procedural scene, short Korean copy.
- `tall-transparent/`: dark tall transparent product, long name/body, verified
  input discount/original price/promotion/date.
- `wide-private-price/`: wide complex background, bright product, 가격 비공개.
- Exact inputs, original source image hashes, actual fonts, line counts,
  overflow/fit steps, geometric bounds, contrast evidence, diagnostics and PNG
  hashes are in per-case metadata.json. `verification.json` verifies all 48.
- Final folder reuses 44 identical reviewed PNGs and re-renders the four emotional
  images for the corrected promotion backplate, without modifying review-02.

Mixed Korean/Latin/special symbols and omitted price are additionally tested
through all 16 real Chromium templates. Unsupported glyphs and excessive copy
return explicit failures. No truncation/ellipsis/price rewriting or photo shrink
to hide text overflow is used.

Rights: original code-authored procedural scenes (noise, gradient, glass-like
highlight/shadow) and earlier original synthetic product drawings. These add
complex image conditions but are **not real photographs**. Commercial quality
and arbitrary real-photo backgrounds/focal points still require human testing
with confirmed photo rights. No source example photo was assumed licensed.

Same exact Phase 14 input/photo comparison for price A–D, short and long cases:
`../phase15-work-20261116/price-before-after/gallery.html` (8 before, 8 after).
Original Phase 14 files are untouched. A contains the subject with inset; B
reserves more information room; C's image circle grows to 540px; D's smaller
stamp sits below the photo rather than hiding it. Original color/layout
identities remain, with deliberate safe-fit/source-font deviations documented.

Final actual diagnostic outcomes across 48:

- Contrast: 31 normal, 17 unavailable/partial; **no measured problem remains**.
  Minimum verified ratio is **4.9323:1**, not a claim for unmeasured regions.
- Font size: 48 caution due to small source-like auxiliary/footer text.
- Layout: 37 normal, 11 caution for conservative photo-frame overlaps.
- Density: 44 normal, 4 caution; display/wordmark blocks contribute large bounds.
- Text-to-text collisions, slot overflow and canvas-outside text are rejected by
  the renderer. Do not turn the remaining cautions into a design approval.

Visual review compared the original 16-design contact sheet with rendered PNGs.
Distinct gallery/fade/editorial/arch, wordmark/emblem/pattern/Korean-wordmark,
full-image/polaroid/cinema/film and four price directions are visible. Source
font substitutions, contain/letterboxing, auxiliary slots and changed price
spacing mean these are **not pixel-identical Illustrator reproductions**.
Decorative repeated-brand text is labeled as such and not a claimed readable
marketing message. Human design approval remains pending.

## Actual model evidence and limits

Existing `bt-logistic-v1` bundle, unchanged `.venv-rank`, A-owned RealRanker →
unchanged B load_model/RankInput/rank_ads. Final PNG bytes for representative
A–D were evaluated per strategy. Evidence: `../phase15-work-20261116/model-results.json`.

| Set | Score range (raw) | First–second gap |
|---|---|---|
| emotional | -0.673863 to 0.074828 | 0.659078 |
| price | -1.821881 to -0.155324 | 0.558418 |
| brand | -0.944257 to -0.094699 | 0.546062 |
| visual | -1.106943 to -0.335566 | 0.434340 |

Worker reported model load 2.4755s once; four inference runs 1.4931, 1.5288,
1.1244, 1.0853s; model_loads remained 1. Concurrent rendering/test load differs
from the earlier isolated 0.344s benchmark; this is four functional runs, not a
repeat benchmark or p95 estimate. UI/browser evidence also confirms source=model
and actual model version. No retraining, weights/preprocessing edits or new
confidence thresholds. Same-strategy model generalization remains unvalidated.

## Preservation and remaining limits

Paid OpenAI calls: **0**. Existing Responses adapter/OpenAI path unchanged.
Ledger stays **8 completed records / $0.01274025**, SHA256:
`2b221949d6d59a36906e5150118bce454a4cc8c54ec077f873203cedb81597b6`.
No .env/credentials/transfer/model/environment/source-ZIP/user-output changes.
No existing presentation/Tunnel restart, external publication, push, PR or merge.

Final local UI is http://127.0.0.1:5186, backend http://127.0.0.1:8016/docs,
isolated Mock-copy/actual-model storage. Earlier development ports 8015/5185 were
not forcibly stopped either. All are local-only and not persistent across reboot.

Remaining: real-photo testing, professional design approval, source/licensing
review before commercial publication, source serif/weight fidelity, focal-point
automation (not implemented), optical typography tuning and same-strategy model
evaluation. Jobs/sessions are still in-memory with original 24h TTL. No claim of
durable recovery after restart. Promotion changes after a completed set are
explicitly rejected rather than silently changing facts. No new deployment or
CI run was performed for the unpushed local commits.
