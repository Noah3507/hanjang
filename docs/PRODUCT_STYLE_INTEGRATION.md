# Product style service integration

Baseline: main `8e319e3`, PR #65 merged. B owns `design_style.py`, templates,
frontend and ML; none are modified. No prompt, font, contrast threshold, model,
environment or production-server change.

## Service contract and data flow

- `AnalysisResponse.product_kind_hint` is additive and nullable. Existing CLIP
  category IDs only (`food/drink/dessert/nonfood`) are considered. Two distinct
  valid finite scores are required; ties, duplicates and unavailable CLIP return
  null. Similarity is the raw winner score; margin is raw first minus second.
  Appearance/impression are excluded. Old cached analyses derive it on GET too.
- It is a design hint, never a food-ingredient/quality fact. The copy payload and
  CLIP prompts/models are unchanged; no additional inference is required.
- `DesignStore.context()` reads the current selected asset and only the completed
  analysis stored under that asset ID with matching source ID. Missing, failed,
  processing or old-photo analysis contributes empty palette/no hint.
- A's `design_style_context.resolve_bundle()` calls B's `resolve_style(StyleInput)`
  for each registered template. Name recognition/colour logic is not duplicated.
  Missing analysis still permits B's name-based style. Actual returned versions,
  input values, sorted variable pairs and valid-analysis fingerprint are captured.
- `TemplateInput.style_context` is internal, immutable and keyword-only. Existing
  positional arguments, promotion validation and three-argument mock executors
  remain compatible. `text_values()` separates strings from style metadata for
  validation/font coverage. `dataclasses.replace()` retains the captured bundle.
- `render_templates()` appends only that page's captured `Style.css()` after its
  existing CSS. No external API accepts CSS. A direct legacy call with no context
  keeps the previous rendering path; the real v3 service supplies the context.
- `DesignResponse.style_snapshot` is an additive envelope of the four actual
  rendering styles, not a change to v2 Candidate or ML input. Variables are sorted
  name/value pairs in JSON. Frontend consumers can ignore this extra metadata.

## Identity, edits and race protection

The existing v2 revision/copy/template snapshot and source asset hash are joined
with immutable style inputs/results, including the actual returned style version,
variables and valid-analysis fingerprint. All 16 styles are resolved for the
source identity conservatively; changing any one invalidates old sets. No version
string or product classifier is reimplemented in A.

GET recomputes current identity; stale sets have no current ranking. Edit,
ranking and PNG/PDF download continue to require revision/snapshot/ownership/TTL.
Rendering uses the start-time bundle and publication rechecks current identity
under the existing render→copy→analysis→upload lock order. A changed style/input
cannot be published as the old result. Captured styles are not replaced by a new
completion-time resolution. Existing atomic publish/leases remain in place.

Text/price edits re-render only the selected template, retaining its style,
promotion values and other assets. Diagnostics refresh; ranking becomes pending
and is manually requested for the new revision. No LLM or CLIP call is added.

## Local actual results — 2026-11-25

`artifacts/product-style-check/run-ed6707d0/gallery.html`: four price templates,
two actual photos, before/after pairs (16 comparison PNGs). Fixed Mock copy;
actual Chromium renderer. Jajang CLIP is a preserved actual result bound by photo
SHA; coffee is a new offline inference with the existing model/environment.

| Actual photo | CLIP first | Second | Raw margin | Final kind / source |
| --- | --- | --- | --- | --- |
| Jajang | food 0.23920637369155884 | nonfood 0.22404257953166962 | 0.015163794159889221 | noodle_soup / name |
| Espresso | drink 0.2540961802005768 | nonfood 0.23767410218715668 | 0.016422078013420105 | drink / name |

Both margins are below B's unchanged 0.02. Names classify correctly, and valid
photo palettes set background hue. Only two photos are available for this review;
no actual chicken/rice/salad/cake samples were substituted or fabricated. This
sample cannot calibrate a CLIP-only threshold: retain 0.02 provisionally and ask B
to review a broader labelled collection. No claim of statistical confidence.

Both isolated API runs completed real `bt-logistic-v1` ranking, single-candidate
edit, ranking invalidation, diagnostics and actual PNG/PDF exports. User originals
and unchanged candidates were preserved. An initial verification run stopped
when ranking was null; its error code was not retained. A direct saved-PNG model
check passed, then the completed isolated run used a 120-second cold-start limit.
Production timeout/settings were not changed; cold-start behaviour remains a
deployment check. No automatic Mock substitution was used for model failure.

No-analysis known-name case renders a name-based style. Unknown-name/no-analysis
case (with name intentionally withheld from the same jajang photo) returns empty
CSS and preserves decoded PNG pixels exactly. This is a fallback test, not a new
unknown-product photo. A separate existing synthetic technical fixture also proves
empty-CSS pixel equality and four-page style isolation in real Chromium.

Gallery Chromium check: 16 images loaded at 1080×1350, console/pageerror zero.
PNG output overflow checks passed. The edited headline was also visually checked.
PDF download succeeded via the actual exporter; no separate PDF viewer visual
comparison was performed. These are API/TestClient + actual rendering checks,
not a claim that the full production website was exercised in a browser.

The colours visibly change, but food appeal/commercial quality has not been
approved. Rectangular photos inside circles and existing layout proportions are
unchanged and remain B's design-review topic.

## Tests and preservation

- Full backend run before the final extra tests: 678 passed, 40 explicit opt-in
  skips, one existing AnyIO deprecation warning. Skips are not passes.
- Final style service regressions: 13 tests; real Chromium technical test separate.
- Commands: `python -m pytest`; targeted
  `python -m pytest tests/service/test_style_integration.py -q`; actual renderer
  `RUN_RENDER_TESTS=1 python -m pytest tests/service/test_style_integration.py -q`.
  CI provides its own frontend/build/browser checks; local frontend code unchanged.
- Paid LLM/image generation calls: zero. Ledger remains 12 entries / $0.01952175,
  verified by SHA before/after the actual service checks. User photos, local
  reports/PNG/PDF, model files and environments are not staged or uploaded.

No production server was stopped/restarted or deployed. Tests use their own
temporary stores and workers; the local HTML gallery can be opened directly.
