# Offline fonts and edit/export verification

## Scope and integration

Based on main `9cae2d6` (PR #67 merged). A-owned backend, rendering worker,
font assets and tests only; B-owned frontend/templates/ML/design_style unchanged.
Production prompt, operating server, environment and ledger are unchanged.

See [font assets and B CSS contract](../backend/assets/fonts/README.md).
Two official variable fonts are available offline; production templates retain
their existing family until B applies the CSS. Font fingerprints join the current
v3 source identity, so font changes invalidate designs and associated ranking,
edit and download operations. Existing style snapshots and v2 identity remain.
Missing/damaged assets fail explicitly; a last successful edit is not discarded.

## Readability: what changed, what did not

The 36 PNG px reference is a provisional service heuristic, not a universal
advertising standard. Actual measurements use 1080×1350 at deviceScaleFactor 1.
All fields previously shared that threshold. Additive items now expose field
role and applied threshold; the v3 worker also records initial/final size and
shrink ratio. Missing shrink evidence remains null, not an invented value.
`fonts(texts, role_thresholds=...)` supports explicit offline comparison; no new
production threshold or environment override has been activated without B/team
agreement. API envelopes and existing frontend fields remain compatible.

Using 48 saved actual Chromium results (16 templates × 3 real-copy conditions):

| Field | Actual min–max PNG px | Below 36 / measured |
| --- | --- | --- |
| Store | 22–114 | 36/48 |
| Product | 38–72 | 0/48 |
| Headline | 30–40 | 27/48 |
| Body (nonempty) | 32 | 24/24 |
| Price | 36–137.24 | 0/48 |
| CTA | 28–32 | 48/48 |

Current profile flags 48/48 templates. An **unapproved comparison proposal**
(headline/price36, body/CTA/brand28, product32, support24) flags27/48. This shows
the source of ubiquitous warnings, not validated readability improvement. It is
not an approved standard and must not silently become production configuration.
Raw comparison: `artifacts/font-support-20261125/diagnostics-comparison.json`.
Overflow, collisions, small text, uncertain contrast and existing contrast rules
remain. Layout bbox overlap remains a risk indicator, not proven visual occlusion.
No diagnostic result is fed into ranking: the existing A adapter supplies final
PNG paths and IDs to B's `rank_ads`; no feature/scaler/model semantics changed.

## Actual local verification and presentation demonstration

Saved real v7 responses and original jjajang/espresso photos were replayed. The
copy provider was explicitly marked mock/replay; no new LLM output was claimed.
Photo analysis used stored real analysis. Chromium rendering and bt-logistic-v1
ranking were real. All work used an isolated TestClient application; the running
presentation server was not restarted or used for mutations.

Local gallery: `artifacts/font-support-20261125/gallery.html` (13 images).
Six comparison PNGs: two photos × existing Noto Sans / Noto Serif / Pretendard;
only isolated test CSS changes the family. CDP confirmed custom font glyphs,
including an explicit Pretendard→Noto Jamo fallback test. Korean/English/digits,
400/700 computed weights, font coverage and variable axes were checked.
The serif changes letterforms/spacing visibly; matching the original designer's
whole composition still requires B's template review. No aesthetic superiority
or general quality score is asserted.

API demonstration uses emotional_a, with original photo/style unchanged:

| Stage | Revision | Actual PATCH+render+GET seconds |
| --- | --- | --- |
| Original | 1 | Initial stage not timed |
| Price only: 7,000원→6,500원 | 2 | 6.075 |
| Headline only: 오늘 저녁은 짜장면 한 그릇 | 3 | 6.256 |
| Empty body | 4 | 5.671 |
| Empty CTA | 5 | 6.063 |
| Body only | 6 | 7.271 |
| CTA only | 7 | 10.677 |

Durations include local API overhead and Chromium; not a performance SLA.
Every edit adds **0 LLM / 0 image-generation calls**. The original product draft
retains 7,000원; only the selected candidate's facts/copy are changed. Other three
candidate assets and style snapshot stay the same. Price-bearing copy must be
explicitly updated by the client; old-price text is rejected, not auto-rewritten.
The demo's selected emotional copy did not contain the old price, so price-only
PATCH was appropriate. The backend does not infer a global product-price change.

Old revision PATCH/download, unsupported characters, conflicting old-price copy,
and forced render failure were checked; the last good result survives failure.
Existing tests separately cover ownership/expiry, inflight snapshot changes and
long mixed text/overflow without truncation. Extreme accepted-length copy can
still fail a particular slot; the renderer reports overflow and preserves the
last success rather than silently deleting text. No new editing system added.

Final PNG is RGB1080×1350. Actual download PDF has one A4 page,
594.96×841.92pt, and contains an image whose decoded pixels exactly match PNG.
PDFium rasterization was used because Poppler is not installed. The rendered PDF
was visually inspected: Korean, 6,500원, edited text and photo are present with
no visible clipping. `latest-pdf-rendered.png` is local review evidence, not a
claim that rasterized PDF page pixels equal the original unscaled PNG.

Presentation: open gallery; compare `01-original`, `02-price-only` and
`03-headline-only`; then `latest.png` / `latest.pdf`. Actual records:
`api-check.json`, `font-comparison.json`, `browser-check.json`. The unchanged
source photo asset is distinct from a claim of byte-identical photo pixels in
every recomposed poster. Style/background are preserved; no repaint occurred.

## Limits and handoff

- B must apply the supplied font families in template CSS and review line breaks.
- Field-specific thresholds need team approval; warning counts are not hidden.
- No `limits.json` exists in this main; no invented per-template limits added.
- Existing AnyIO/Starlette deprecation warning is unrelated to this work.
- Ledger stays15 calls / $0.02431050, verified by SHA-256 before/after replay.
- No production server restart, deployment, paid API, model download or main merge.
- User photos, generated PNG/PDF, local replay scripts and ledger stay out of Git.

## Executed tests

- Final default backend `python -m pytest -q`: **692 passed,43 skipped**.
  Skips are explicit installed-Chromium/model opt-ins, not reported as passes.
- `RUN_RENDER_TESTS=1` template_v3 + diagnostics: **82 passed**.
- Final `RUN_RENDER_TESTS=1` render_fonts + designs: **20 passed**.
- Frontend: **103 passed /19 files**, TypeScript and production build passed.
- Actual local replay:13 gallery images decoded; console/pageerror0; six font
  comparison renders and seven API edit stages, actual model rerank/PDF checked.
- Repository index policy and `git diff --cached --check` passed.

The earlier full Chromium-opt-in run returned729 passed,2 failed,3 skipped:
the variable-family assertion below and an exact-pixel fallback-CSS comparison
(`price_c`). The latter passed on an unchanged isolated16-template rerun
(1 passed); a separate price_c comparison also produced byte-identical decoded
pixels and saved both PNGs/font evidence in `price-c-pixel-recheck.json`.
Its initial cause is unconfirmed; no template or tolerance was changed to hide
it. Treat it as a non-reproduced pixel-stability warning, not a repaired defect.

An initial actual-font test incorrectly expected CDP's variable Noto name to
equal the static family exactly. The renderer was using Noto Serif correctly;
the test now accepts the actual base-family name while still asserting custom
glyph use, axis metadata, computed weights and fallback. Final targeted rerun
passed. Existing Starlette/AnyIO deprecation warning remains.

CI is reported with the pull request. A green test does not replace B's
original-design and user visual acceptance.
