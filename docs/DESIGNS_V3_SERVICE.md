# Phase 15–16 — 16 designs and second-stage service

PR #53 ML feedback: the additive nullable `ranking_close_call_score_gap` comes
from the active manifest for valid current model rankings. V3 compares raw
top-two gap inclusively, displays scores to two decimals, and keeps v2 unchanged.
See [policy, shared comparison data and B handoff](V3_RANKING_REVIEW.md).

Phase 16 renderer version: `ad-templates-v3-alpha-quality-3`. Guarded alpha
support placement and measured image diagnostics supplement the existing v3
flow; opaque photos retain their full frame and unknown subject extent. See
[quality report](PHASE16_QUALITY_REPORT.md) and [local PR draft](PR_AD_TEMPLATES_V3.md)
for evidence, warnings and the paid-copy validation limit. V2 contracts and B
model code remain unchanged.

## Scope and authorization

Implemented on `feat/ad-templates-v3`, following Phase 14 commit `6cdd2ef` and
main `c7892d8`. The user's Phase 15 request explicitly authorizes an additive
v3 API, strategy selection, same-strategy ranking, diagnostics, per-design copy
and price editing, downloads and local commits. This supersedes the earlier
Phase 14 local-render-only scope. It does not authorize paid calls, publishing,
push, PR, B ML changes or presentation-server restarts.

The existing rendering/Candidate/ranking/editing/download contracts remain
unchanged. New `DesignCandidate` extends Candidate only within the new envelope.
B still receives `RankInput(candidate_id, final_png_path)` through the existing
A-owned `RealRanker` worker, without a strategy feature or altered preprocessing.

## User flow

1. Upload/save → Mock or existing approved copy path → original four strategies.
2. Select a strategy on an existing card or in the new strategy selector.
3. Click **이 전략으로 시안 4개 더 보기**. The four variations reuse that source
   candidate's exact headline/body/CTA, including existing user edits. No new LLM.
4. Review A–D, diagnostics and optional **ML 참고 순위**. Cards stay A–D; an ML
   score never overrides warnings or automatically promotes a design as best.
5. Edit one design's headline/body/CTA or explicitly entered price; render again;
   download its revision-bound PNG/A4 PDF. Other designs and v2 stay unchanged.
6. Switch strategies, or refresh and click **저장 정보 다시 조회**. Strategy choice
   is sessionStorage-scoped to the job; server memory retains each strategy set.

Selection is locked while an unsaved editor is open. Cancel restores focus to
the corresponding edit button. Inputs have explicit labels/IDs; buttons expose
selection state and processing/disabled state. Images preserve 4:5 preview ratio.

## API (all under /api/v1)

Every request uses the existing `X-Hanjang-Session`, owner check, 24h job TTL,
private registered assets and existing presentation gateway when enabled.
Mutation bodies are bounded at 16KiB before parsing. No public file path API.

Let `base = /jobs/{job_id}/designs/{strategy}`; strategy is one of the four
existing names, not an arbitrary template ID.

| Route | Behavior |
|---|---|
| POST base | 202; reserve the existing renderer slot, render four variations in background |
| GET base | pending/processing/completed/failed; latest set for that strategy |
| PATCH base/candidates/{candidate_id} | 202; edit one design, keeping its ID and the other three assets |
| POST base/ranking | synchronous 200 result or safe failure; immutable PNG snapshot, real model by default |
| GET base/ranking | current set and ranking; stale rank is withheld |
| GET base/diagnostics | measured rules, revision/snapshot/currentness; no invented contrast |
| GET base/candidates/{candidate_id}/download | format=png/pdf and expected_revision/expected_snapshot required |

Creation body:

```json
{
  "expected_render_revision": 1,
  "expected_source_asset_id": "11111111111111111111111111111111",
  "expected_copy_key": "22222222222222222222222222222222",
  "promotion": {
    "original_price": "15000원",
    "discount_text": "30%",
    "promotion_text": "직접 확인한 행사명",
    "period_text": "2026.11.16–2026.11.20"
  }
}
```

All promotion fields are optional and empty by default. Optional UI inputs
accept explicit verified facts before creation. Completed sets retain their
promotion data; a conflicting creation retry returns 409 rather than silently
replacing it. Existing v2 facts and copy APIs do not acquire promotion fields.

Edit body:

```json
{
  "expected_revision": 1,
  "expected_snapshot": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "expected_asset_id": "33333333333333333333333333333333",
  "copy": {"headline": "사용자가 작성한 제목", "body": "사용자가 작성한 본문", "cta": "상품 보기"},
  "price_text": "12000원"
}
```

Rank requests contain just expected_revision and expected_snapshot. Copy keys,
source revision/asset, version, candidate IDs, template IDs, generation revision,
edit revision and asset IDs are separate. The opaque snapshot hashes the current
set. Each download revalidates after PDF execution too.

## Transactions, lifetime and failure

- State is `Record.design_sets[strategy]`, protected by the existing render →
  copy/analysis/upload lock order. No separate global store survives an expired job.
- A source key binds the current v2 result, selected image hash and template
  version. Facts/photo/copy/v2 revision changes make old v3 results stale.
- The existing RenderSlot fences dispatch, duplicate/running work and publication.
  Different strategy requests during rendering receive retryable busy errors;
  finishing A does not overwrite B's selector or B's stored results.
- A–D publish atomically. If one design overflows, its safe template/field IDs
  are reported and publication is withheld; no incomplete set goes to the model.
  This is explicit partial generation failure, not a successful partial result.
- Editing computes outside the lock, rechecks source/revision/assets, then
  publishes one new PNG and a new set revision. Same candidate ID, changed asset;
  other candidates preserve their copy, facts, ID and asset. All four exposed
  revision fields advance together. Failed edits preserve the last successful set.
- Ranking and diagnostics invalidate on successful editing. Late inference,
  bundle changes, changed bytes or source changes cannot publish as current.
  Auth/ownership/TTL and four unique registered RGB1080×1350 PNGs are checked.
- Normal errors never return raw exception text, paths, stack traces or secrets.
  Model failure never silently becomes Mock. Retry remains available and does
  not block input/copy/render/edit/download.
- Source uploads and old successful assets are not overwritten. New files are
  O_EXCL-created under the existing private TTL root. Failure cleanup only
  removes this operation's unpublished newly created files.
- Like v2, job/session metadata is in memory. Refresh in the same tab can restore;
  server restart or expiry cannot promise durable recovery. No persistence/queue
  or external deployment changes are introduced.

## Explicit price and claim policy

Price edits are **v3-candidate overrides**, not modifications of the uploaded
InputDraft, original facts, source copy or v2. `original_price_text` retains the
input value. Other designs retain their prices. Facts are never automatically
normalized, translated, discounted or corrected. Conflicting old price text in
the edited copy is rejected; the user must edit it, not a hidden replacement.

Amounts used for promotion validation are parsed into Decimal only for checking:
supported explicit currencies KRW/원, USD/$ and EUR/€ must agree; price must be
below original price. Percentage is checked at the caller's declared decimal
precision using ROUND_HALF_UP; rendered raw strings remain unchanged. This is
rounding of a supplied percentage, not generation of a discount or a new price.
Unknown representations return review-required, not guessed conversions.
Dates must be real and ordered (full end year or same-year shorthand). Raw dates
are preserved. Price absent/private works without invented numeric values:
direct rendering allows an empty price; the service uses existing facts or the
user's explicit 가격 비공개/가격 문의/별도 문의. Existing upload facts still require text.

Unprovided stock, sales, awards, efficacy, limited sale or free shipping are not
generated by the renderer. Supplied free text is user-authored, not a verified
truth certification. False supplied claims cannot be detected universally.

## Templates, image handling and source differences

Registry VERSION is `ad-templates-v3-16-layouts-2`. Twelve additional independent
HTML entries reuse a shared semantic slot partial and per-template CSS rules:

- emotional_a/b/c/d: gallery, fade, editorial columns, arch/circle.
- brand_a/b/c/d: large input wordmark, emblem, repeated input-brand pattern,
  Korean wordmark/side image.
- visual_a/b/c/d: broad image, polaroid, cinema gradient, film rails.
- price_a/b/c/d retain the Phase 14 files and distinct layouts, improved below.

Real Noto 400/700 faces, both pinned hashes, cmap checks and Chromium actual-font
checks remain. No synthetic bold or font/model download at runtime. No new font
download in Phase 15. Emotional designs use the existing licensed sans rather
than the source Noto Serif ExtraLight; price/brand use Noto rather than Pretendard.
These substitutions and the extra product/price/copy slots change source fidelity.

Phase 15 contained the full selected image with fixed padding. Phase 16 instead
measures alpha support, conditionally trims faint transparent margins with an
alpha-mass guard and fits all meaningful support inside the slot. Opaque photos
still contain the full frame; their true subject size remains unknown. Circles
use measured ellipse containment. Full-bleed/cinema references use bounded contained image fields and
contrast-safe text lanes, so they are less edge-to-edge than the source. This
is a documented subject-protection tradeoff, not pixel-identical reconstruction.
The service reuses the photo currently selected through the existing rembg
workflow; it does not automatically run rembg again or reinterpret the product.
Users can keep original photos for atmospheric/visual designs or select an
existing processed transparent photo before generating the source/v3 sets.

Price improvements: A uses an inset contained circle; B shortens the photo field
to reserve aligned text lanes and larger information spacing; C grows its circle
from 425 to 550px by Phase 16 while retaining big-price hierarchy; D moves a smaller stamp
below the photo and separates claims inside it. Source yellow/black/red design
identities remain. Same-image/copy before/after evidence is outside Git.

No example PNG/AI/photo or embedded source font was committed. Only reconstructed
geometry and licensed Noto assets are used. Source rights remain the owner's
responsibility; original procedural test imagery avoids assuming photo rights.

## Diagnostics and ML interpretation

Actual Chromium slots, line counts, bounds, fitting steps, font faces and paired
background pixels feed the existing diagnostics engine. Bbox/photo intersections
are conservative warnings; template metadata labels intended overlaps/decorative
brand pattern without suppressing the warnings. Uncertain contrast stays
unavailable. Small-font/density thresholds are existing tunable heuristics,
not a design approval or new aesthetic metric.

Actual model runs use existing `.venv-rank`/bt-logistic-v1, cached by the existing
worker, immutable private PNG copies and exact ID mapping. Explicit development
Mock uses zero equal scores with ID tie ordering (scores hidden); no fake strategy
remapping is used to satisfy the old four-strategy MockRanker. Real mode rejects
non-model output. No automatic fallback or changed B interface.

Same-strategy generalization is not validated. Raw scores/1–4 ranks and model
version are labeled reference only, separate from diagnostics; no CTR/probability
or invented explanations. No 0.2 confidence threshold is used in this v3 UI.

## Local use and verification

Use [LAPTOP_SETUP](../LAPTOP_SETUP.md)'s existing Mock/paid=false local launcher
with a new ignored JSON pointing to existing resources and a **new upload root**.
Never reuse presentation storage for automated tests (the normal TTL sweeper runs).

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/service_local.ps1 -ConfigFile artifacts/phase15/final-dev-config.json -Port 8016 -FrontendPort 5186
# Separate shell
$env:DEV_BACKEND_URL='http://127.0.0.1:8016'
npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 5186 --strictPort
```

Local generated config is not a committed portable file; see the launcher example
for a new machine. Existing .env, models and environments are reused, not copied.
UI: http://127.0.0.1:5186. Backend docs: http://127.0.0.1:8016/docs.
These are loopback development servers, not presentation/external deployment.

```powershell
$env:RUN_RENDER_TESTS='1'; $env:RUN_RANKING_TESTS='1'
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test:ci
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe scripts/service_v3_gallery.py --output ..\phase15-new-review
# For an already running Mock-copy / actual-model local server:
$env:PLAYWRIGHT_EXTERNAL_SERVER='1'; $env:PLAYWRIGHT_FRONTEND_PORT='5186'
$env:PLAYWRIGHT_REQUIRE_RANKING_MODEL='1'
npm.cmd --prefix frontend run test:e2e -- designs-v3.spec.ts
```

Opt-in test flags require existing local artifacts. They never install/download
models. Default CI separates real-model/render tests as before. Offline gallery
output must be a new directory outside Git. See [test report](PHASE15_TEST_REPORT.md)
for actual runs and remaining limits. No push means no new GitHub CI run.
