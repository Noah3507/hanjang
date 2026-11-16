# Phase 14 local validation — 2026-11-16

## Code and scope

Base main: `c7892d80887c0d571ecaf159dd4a348b3ec6afde` (PR #52).
Work branch: `feat/ad-templates-v3`. Local commit only; no push/PR/deployment.
Implementation and 16-design specification: [AD_TEMPLATES_V3](AD_TEMPLATES_V3.md).

## Preserved inputs and evidence locations

All design source files and generated evidence are outside the repository:
`../phase14-work-20261116/`.

- `inventory.json`: source ZIP hash, 76 extracted files and per-file hashes.
- `source/`: 16 original AI and 60 original PNG; no source asset added to Git.
- `contact.png`, `price-contact.png`: visual source inspection sheets.
- `ai-pdf-analysis.json`, `ai-text-runs.json`: PDF-compatible AI evidence;
  not an Illustrator editable-layer extraction.
- **`final-review-accepted/`**: definitive five-case comparison, 20 v2 PNG and 20 v3 PNG,
  source images, exact inputs, identities/hashes, font/layout measurements,
  fitting stages, diagnostics, `gallery.html` and `gallery.png`.

This folder name identifies the final technical check, not user design approval.
It reuses 35 byte-identical validated PNGs from final-review and re-renders D's
five PNGs after a 25px stamp adjustment to preserve clearance from the footer.

Other comparison folders are intermediate attempts and deliberately preserved.
Do not mix them into final evaluation. Early runs found price glyph height,
discount/body collision and long-name slot capacity failures. An early diagnostic
adapter omitted renderer text_boxes and returned unavailable; corrected before
final evidence. One broad test run mixed already-imported old Python code with
edited templates and failed; a fresh broad run passed. No assertion or existing
test was removed/weakened to obtain that result.

## Test assets and visual assessment

Five code-authored synthetic product images: light transparent tall bottle,
dark horizontal shirt on background, dark speaker on background, dark transparent
tall bottle with long name/body and promotion, light transparent wide speaker.
Rights: original code-authored geometry, no third-party photo or real brand.
These test ratio/shape/layout and input preservation, **not real-photo quality**.
Reference example-photo commercial rights are not assumed.

Same source PNG, product facts and headline/body/CTA are passed to existing v2
four strategies and new v3 four price variants. Promotions exist only in the
explicit v3 test inputs; the old facts contract has no promotion fields.
Do not score these as equivalent strategy experiments or claim discount values
were inferred. Actual model inference/quality evaluation is not performed.

Visual checks used actual rendered PNGs and source contact sheets. Distinct
yellow/circle, photo-over-black split, dark big-price and white/red-stamp layouts
remain recognizable. Long fields wrap without deletion. Transparent products use
contain to preserve shape; opaque product photos use cover and can crop. The
stamp deliberately covers part of its image. Compared with the source, Noto
replaces Pretendard, extra headline/body slots require denser B and a smaller C
photo, English slogans are absent without explicit input, and missing commercial
claims leave deliberate negative space. These are prototypes for user review,
not a claim of commercial design approval or pixel fidelity.

Raw text bounds, line counts, font sizes/weights/actual fonts, overflow and
collisions are recorded. Optical balance, brand suitability and photo cropping
still require a human. No aesthetic score is manufactured. Existing diagnostic
small-font and intentional-image-overlap cautions remain. Image/badge/stamp
contrast is conservatively unavailable where not verified. A's optional red
promotion label was darkened to `#d62d22` after a 4.15:1 measurement; final PNG
evidence should be used rather than the earlier CSS-only calculation. Final
measured contrast ratios are at least 4.93:1 where verified; overall contrast
coverage stays partial. All 20 v3 PNGs retain small-font cautions, 12 have layout
cautions (conservative product-frame overlaps), and all 20 have normal density.
The final gallery loaded all 20 images in actual Chromium without page errors.

## Commands and outcomes

Windows Python 3.12.10; existing .venv; Node 24.20.0; existing Playwright 1.64.0
Chromium. No dependency upgrade or virtual-environment reinstall.

```powershell
$env:RUN_RENDER_TESTS='1'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
# 463 passed, 3 skipped, 1 warning (268.22 seconds)
.\.venv\Scripts\python.exe -m pytest tests/service/test_template_v3.py -q -p no:cacheprovider
# Final targeted execution: 9 passed (27.26 seconds)
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test:ci
# 15 files / 68 tests passed
npm.cmd --prefix frontend run build -- --outDir <new-temp-directory>
# passed; existing presentation frontend/dist untouched
.\.venv\Scripts\python.exe scripts/service_check_repository.py
git diff --check
```

The broad run includes existing real Chromium rendering, editing/PDF and
diagnostic tests. Its three skips are explicit local B-bundle inference tests;
no model inference or model download was requested. The final targeted run also
covers the corrected diagnostic adapter and final CSS changes made after broad
collection. Existing warning: Starlette's AnyIO BlockingPortal deprecated alias.

Tests verify real RGB1080×1350 PNG, ID distinction, exact text including price
whitespace, optional-claim absence/presence, long fields, overflow rejection,
unsupported glyph/image/template rejection, real Bold metadata/hash and measured
diagnostic coverage. Browser execution is offline Chromium rendering; no new
service UI, authenticated API flow or paid provider E2E was performed.

The source ZIP, credentials, .env, transfer, models, virtual environments,
existing upload/download data and presentation/Tunnel settings were not changed.
Ledger remains 8 completed records / $0.01274025; SHA256:
`2b221949d6d59a36906e5150118bce454a4cc8c54ec077f873203cedb81597b6`.
No paid call, upload to an external service, server restart or Tunnel action.

## Remaining work

- User review of final gallery and original-design deviations.
- Real product photographs with documented rights; crop/focal-point tuning.
- Production version/variant and verified-promotion contracts, persistence,
  revision/stale/session checks and UI selection before public integration.
- Remaining 12 registry entries are specifications, not implemented templates.
- ML evaluation on new layouts and same-strategy candidate-set contract review;
  no B model modifications or claims of objective quality improvement.
- No GitHub Actions run for this unpushed local work; local checks only.
