# Local PR draft — do not publish yet

Proposed title: `feat(designs): add sixteen v3 templates and protected service workflow`

Base: `main`; head: `feat/ad-templates-v3`. Related issue: not supplied.
This is a draft document only. No push, PR creation, merge or CI run is implied.

## Problem and resulting behavior

The existing four-strategy output could not offer four distinct designs within
one strategy. Transparent margins also made real food look too small inside
circular layouts. Users can now select a strategy, review four source-based
templates, inspect separate diagnostic and model information, edit a design and
download its revision-bound PNG/PDF without regenerating copy.

## Included work (Phases 14–16)

- Sixteen HTML/CSS designs, registered by strategy and A–D variation; real local
  regular/bold fonts; bounded fit and exact fact/price rendering.
- Additive v3 API/store/schema and selector/editor UI; v2 Candidate/rendering
  contracts unchanged; ownership, TTL, snapshots, hashes, stale/atomic publication.
- Actual B model integration through the existing worker, independent diagnostics,
  per-design edits and private PNG/A4 PDF downloads.
- Alpha support placement, guarded transparent-margin trimming, circle containment,
  geometry warnings and legacy worker compatibility.
- Real-provider advertising directions and final-copy advisory checks, while
  preserving Mock behavior, placeholder facts and paid-call gates.
- Free regression tests, optional actual local-photo browser input, review utility
  and service/test documentation.

Main areas: `templates/v3/`, `backend/app/services/`, additive design routes and
schemas, `frontend/src/components/DesignVariants*`, v3 workers, service/integration
tests and `docs/DESIGNS_V3_SERVICE.md`. No B inference/training/weight changes.

## Validation

Phase 16: backend 493 passed; frontend 74 passed; typecheck/build passed; actual
browser v3/v2 editor/diagnostic scenarios 5 passed. Eight real B before/after
batches and actual offline rembg/CLIP checks passed. Eighty PNGs passed geometry,
font, hash and RGB/dimension checks. Edited PDF rasterized and embeds exactly
the downloaded PNG. Final focused rerun is recorded in the Phase 16 report.
See [Phase 15](PHASE15_TEST_REPORT.md) and
[Phase 16 evidence/limits](PHASE16_QUALITY_REPORT.md).

No paid OpenAI test; copy tests use Mock/fake SDK/fixed advertising fixtures.
GitHub CI is not run until an authorized future push. Screenshots/user food and
large generated PNGs intentionally remain private/local; no PR attachments.

## Reviewer checks and remaining limits

- Confirm preserved facts and price, distinct strategies, visible product, text
  hierarchy and edited asset downloads in the local gallery/UI.
- Keep rule warnings visible: small labels, layout/density cautions, unknown
  contrast over photos, opaque-subject unknown size and intentional gradients.
- Model raw scores are relative preference, not a combined quality/CTR metric.
- Source-inspired designs are not pixel-identical to original Illustrator files.
  Human design approval remains required. Paid prompt quality is unverified.
- In-memory job persistence/restart limitations remain unchanged.
- No source ZIP/user photos/secrets/models/ledger/runtime data are included.

Do not merge without explicit user approval.
