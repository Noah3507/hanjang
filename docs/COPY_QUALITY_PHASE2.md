# Copy quality Phase 2: preparation protocol

The separately approved two-call experiment completed on 2026-11-23.
See [actual results and diagnosis](COPY_QUALITY_PHASE2_RESULTS.md).
The commands below document the original gate; they are not permission to rerun.
The selected plan's execution fence exists and the ledger is now at 10 calls.

## Fixed experiment

PR #60 is merged at `9650c7ce5b4d56f5078fdc986ab152e59410fc13`.
Preparation branch: `test/copy-quality-phase2`. No production prompt, design,
ML implementation, environment file or running server is changed.

Compare only the system prompt: A is v5 from
`c8cb74a93cbdf99c9791d96927a237ca038f0172`; B is v6 from the main commit above.
Both use the existing Responses adapter, current shared validation, model
`gpt-5.4-mini-2026-03-17`, reasoning `none`, output limit 2048, store false,
SDK/app retries zero. This isolates prompts, not historical validator versions.

Common synthetic facts: 골목반점 / 짜장면 / 7,000원 / warm; no product features,
address or contact details. User-provided local jajang photo is used only for
offline analysis and rendering; photo bytes and local paths are not sent to OpenAI.

## Approved free input preparation

Original photo: `test-images/jjajang2.jpg`, 800×800 JPEG,
SHA-256 `af52da34caf2d6c2662340db8fa76934bbcea0ba5fc3bb8a983dbd71692159a8`.
Never commit this user file. Original remains unchanged. Actual local rembg,
CLIP and five-color extraction succeeded. Derived mask retains some accessories;
both arms therefore render the original, not the cutout.

All 12 original CLIP cues are retained in
`artifacts/copy-quality-phase2/jjajang-photo/analysis.json`.
User selected one maximum raw-score cue per category, in fixed order:
category=food, appearance=glossy, impression=bright. These are fallible visual
impressions, not evidence of ingredients, origin or manufacturing. Existing
fact-grounding prompt and validation remain in force; semantic safety still
requires review of actual outputs. Palette is not sent by the existing adapter.

The existing conservative input bound is a byte-based guard, not measured tokens:

| Common analysis policy | v5 | v6 | 6000 guard |
| --- | ---: | ---: | --- |
| Full 12 cues | 6198 | 5984 | v5 rejected before dispatch |
| Selected 3 cues | 5049 | 4835 | Both pass |
| No cues | 4670 | 4456 | Both pass |

Selected signed plan: `artifacts/copy-quality-phase2/proposed-top3/plan.json`.
The full analysis snapshot, selected payload, source/runtime hashes and original
ledger hash are pinned. No silent truncation or prompt/cap modification occurs.
The result applies to this reduced shared context; it does not measure full-12-cue
production behavior. Earlier alternative plans are not selected for execution.

## Cost and execution gate

Existing ledger: 8 completed records, $0.01274025; untouched during preparation.
Maximum two paid attempts, cumulative request limit 10, cumulative budget $0.10.
Conservative reservation: $0.013716 per attempt, $0.027432 total; worst-case
combined reserved cost $0.04017225. Actual cost uses returned usage; failed or
unknown-usage requests may still incur cost and retain the existing reservation.

Explicit user paid approval is required before executing:

```powershell
.\.venv\Scripts\python.exe scripts/service_copy_ab.py execute --output artifacts/copy-quality-phase2/proposed-top3 --photo test-images/jjajang2.jpg --approved-two-paid-calls
```

Do not run that command during free preparation. The tool rechecks photo, ledger,
code, settings and signed plan before dispatch. A persistent exclusive execution
fence prevents repeated runs. A failure stops before B, without retry or repair;
do not remove the fence or automatically resume. Never reset the existing ledger.
The server configuration and credentials are not copied or changed.

## Evaluation and image review

Save raw UTF-8 responses, bound copies, usage/cost, validation and automatic
observables separately. Raw text may be unavailable after transport/incomplete
response failure; do not invent it. Both arms use the same validation policy.

Seven 1–5 review criteria: product fit, advertising appeal, natural Korean,
strategy differentiation, headline/body/CTA coherence, factual safety, willingness
to use. For each criterion: 1=clear failure, 3=usable with meaningful editing,
5=strong and ready for the stated purpose. Require a written reason citing copy.
Factual safety score does not replace hard validation. Human CSV starts blank;
AI subjective review and actual human ratings must remain separate. No evaluation
is completed merely because tests pass. A single sample per prompt is diagnostic,
not statistical evidence of overall superiority.

After approved responses, render each arm using the same original photo, facts,
layout and mood. `scripts/service_copy_ab_render.py` accepts `--renderer v2` or
`--renderer v3-a` (one existing A layout per strategy). This is eight images per
renderer, not a test of all 16 v3 designs. Never edit design templates for this test.
Inspect photo prominence, wrapping/overflow, hierarchy, contrast, photo/background
integration, CTA and commercial finish. Record automated geometry separately from
subjective assessment. List the three largest observed issues only after results.

Free layout fixtures are explicitly handwritten, identical in both arms, and **not
LLM output**. Galleries:

- `artifacts/copy-quality-phase2/photo-layout-only/rendered/gallery.html` (v2)
- `artifacts/copy-quality-phase2/photo-layout-only/rendered-v3/gallery.html` (v3 A)

Actual Chromium produced eight PNGs per gallery. These establish photo/rendering
readiness only; real-copy length, aesthetic quality and prompt improvement remain
unverified. No authenticated website E2E or paid generation ran in preparation.

## Free verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests/service/test_copy_ab.py tests/service/test_openai_validation.py tests/service/test_copy_particles.py -q
```

2026-11-23: 78 passed; one existing Starlette/AnyIO deprecation warning.
Fake SDK and isolated synthetic ledgers test gating, two-attempt maximum, failure
stop, no retries, input equality, plan/photo/ledger tampering, raw preservation,
cue selection and existing grounding/particle validation. Actual local model
execution and Chromium rendering are distinct free checks. Frontend/type/build
are not rerun: no frontend/API/template change. Existing servers are untouched.
