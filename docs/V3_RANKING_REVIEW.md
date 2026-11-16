# PR #53 — ML review feedback

## Score guidance policy

V3 uses the active bundle manifest's `close_call_score_gap` (currently **0.2**),
not a new UI constant. The A-owned service reads this policy next to the
configured model file and verifies the manifest model version matches the
ranking. Missing/invalid metadata yields null; there is no guessed fallback.
No B code, weights, inference output or existing v2 response is changed.

The additive nullable `ranking_close_call_score_gap` field is in the v3
`DesignResponse` envelope, outside the unchanged `Ranking` contract. V2 UI and
its existing adjacent-pair `<0.2` behavior are unchanged. V3 deliberately uses
**first versus second ranked raw score, gap <= manifest policy**, as requested.
It does not use the smallest gap among all six pairs as its headline condition.

The UI displays:

> 상위 시안들의 추천 점수가 비슷합니다. 작은 점수 차이만으로 디자인의 우열을 판단하기 어려우므로 직접 비교해 선택해 주세요.

This is a user guidance rule, **not validated statistical confidence or
same-strategy ranking accuracy**. Scores are raw relative model outputs, never
conversion rates, calibrated probabilities or accuracy. Only display formatting
uses two decimals; decisions use full raw scores without rounding or epsilon.

Guidance requires a current completed model result with four finite scores,
unique matching candidate IDs, ranks 1–4 in score order and the same result,
candidate and PNG revision as the current set. Failed/pending rankings, missing
scores/policy, editing, stale inputs/revision and Mock results cannot trigger it.
Model bundle token changes invalidate ranking and policy together. Existing
snapshot/hash/ownership/TTL checks are retained. No model failure blocks editing
or downloading the last successful designs.

## Shared numeric evidence

- [Markdown summary](analysis/phase16-ranking-review/README.md)
- [Full precision JSON](analysis/phase16-ranking-review/scores.json)
- [Candidate CSV](analysis/phase16-ranking-review/candidates.csv)
- [All unordered pairs CSV](analysis/phase16-ranking-review/pairs.csv)
- [Counts/ratios CSV](analysis/phase16-ranking-review/summaries.csv)
- Export utility: `scripts/service_ranking_comparison.py`; reconstruction method
  and CLI placeholders are in the summary. B can recompute all pair counts
  directly from shared JSON without private photos, model weights or inference.

Same source photo/copy/model-feature versions were checked; final PNGs differ.
Historical per-call weight hashes are absent, so weight equality is not invented.
Phase 16 used the same RealRanker/bundle, but this is not a controlled single-
factor experiment. IDs in the inference runner and renderer are labeled separately.
There are 16 candidates and 48 pair records (6 × 4 strategies × before/after).
Strict `<0.2` pairs: before **4/24 (16.67%)**, after **7/24 (29.17%)**.
Inclusive manifest-policy counts happen to equal those counts in this dataset;
no pair is exactly 0.2. Neither ratio is evidence of accuracy or improvement.

Ranking order before → after:

- Emotional: DABC → DBAC
- Price: BCDA → CABD
- Brand: CBAD → CBDA
- Visual: CADB → CDAB

No user photo/copy, private path, credential, model file or ledger is included
in these shared data files. Markdown rounds values only for readability.

## Verification and review

Focused tests exercise configurable manifest policy, exact boundary, rounded-
display disagreement, missing/NaN/failure/Mock states, source/revision changes,
all four strategies, v2 preservation and every exported pair's arithmetic.
The browser suite distinguishes simulated model-response guidance tests from
the actual B-model v3/unchanged v2 integration path. Free Mock copy only.
Final test/CI counts are reported in PR #53; skipped tests are not passes.

Local backend: **504 passed**, actual rendering/ranking opt-ins enabled.
Frontend: **81 passed**, TypeScript and isolated production build passed.
Initial test-authoring syntax/response-readiness issues were fixed. An overlapping
second browser invocation briefly caused the expected single-renderer `RENDER_BUSY`
in v2; the unchanged v2 editor passed when rerun serially. Failed-run artifacts
are retained separately; no test was deleted or loosened.
The mock v3 browser fixture was also completed with the real contract's
`source_revision`; the source-identity fence correctly rejected the incomplete
fixture. Five existing browser scenarios passed in the final serial run, and
the corrected four-strategy guidance scenario was rerun separately.

Existing servers/settings were preserved. An isolated Mock-copy/actual-model
backend/frontend is available at `http://127.0.0.1:8018` / `http://127.0.0.1:5188`.
No PowerShell execution policy was changed; after the script launcher was
blocked by existing policy, the isolated backend used Python/uvicorn directly
with process-only Mock/paid=false/offline environment. No .env modification.

B handoff message:

> B님, PR #53에 v3 상위 1·2위 원본 score 차이 ≤ manifest 기준 안내를
> 추가했습니다. 점수 표시는 두 자리이며 판정에는 원본값을 사용합니다.
> docs/analysis/phase16-ranking-review/의 JSON/CSV에 전후 16개 시안과
> 모든 48쌍·비율이 있으며 README에 재현 방법을 적었습니다. 동일 전략
> 추천 정확도 기준으로 해석하지 않습니다. 기존 리뷰 요청은 유지하며,
> main 병합·배포는 별도 사용자 승인 전까지 진행하지 않습니다.
