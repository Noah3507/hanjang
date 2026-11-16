# Phase 17 — PR verification and ML collaboration review

Prepared 2026-11-16 on `feat/ad-templates-v3`, implementation HEAD `956e185`.
This phase authorizes push and PR/reviewer requests, but not main merge, paid
calls or deployment. The Phase 16 local-only PR draft remains a historical draft.

## Git and security preflight

After `git fetch origin`, main is `c7892d8`, including B's merged PR #52
(`docs/ml-windows-results`, author `parkyeonwooo`). All five implementation
commits already descend from that main; no merge/rebase or duplicate B changes
were needed. No existing remote v3 branch or open PR was found. The working tree
was clean at entry. Local main is two commits behind origin/main; it was not
checked out or modified for this feature PR.

All 64 distinct changed blobs across the five outgoing commits were checked,
not just the final tree. No detected secrets, protected/runtime files,
unexpected large files or absolute Windows user paths were found. The largest
new asset is the licensed 4,816,044-byte Noto Sans KR Bold font, SHA-256
`5a6ceb287ed2fc6cfc6213144ebea68cbd94b20fc9eb873d8486493bf02d9bda`.
Its internal copyright/license metadata agrees with the pinned source and
OFL 1.1 in `templates/fonts/`: bundling/embedding/redistribution is allowed with
the notice and license, without selling the font alone. Original font unchanged.
The existing index policy scanner and `git diff --check` also passed.
These checks are supplementary; they do not prove absence of every secret/PII.

No diff touches `ml/`, `tests/ml/`, B scripts or `backend/app/ml_adapter/`.
V3 calls the existing A-owned ranking worker; it does not replicate B inference.
No original ZIP, Illustrator file, user photo, generated PNG/PDF, model bundle,
ledger, environment or credential file is included.

## Fresh local validation of the implementation

| Check | Result |
|---|---|
| Full backend, `RUN_RENDER_TESTS=1` | 490 passed, 3 explicit actual-model skips, 261.25 s |
| Actual ranking opt-in, `test_real_ranker.py` | 15 passed, including all 3 skipped cases; 36.62 s |
| Unique backend test cases across those runs | 493 passed |
| Frontend full unit suite | 74 passed / 17 files |
| TypeScript and production build | Passed; build stored outside presentation assets |
| B bundle smoke | PASS; maximum score error 9.46e-06, tolerance 0.001 |
| Existing v2 editor/diagnostic browser tests | 4 passed |
| Final v3 actual-photo/real-model browser test | 1 passed, 54.4 s |

The full backend includes API, ID mapping, stale/ownership, diagnostics, actual
Chromium renderer, editing and download regression coverage. Existing AnyIO
deprecation remains. No paid SDK calls were made.

The first browser invocation used the repository root rather than frontend
config and failed five tests before navigation. The next invocation passed all
four v2 tests but v3 expected Mock text while the existing server used the real
model. These are invocation mistakes, not suppressed product failures. The v3
test passed with `PLAYWRIGHT_REQUIRE_RANKING_MODEL=1`. The five unique browser
scenarios therefore passed across the corrected runs. Earlier failures and final evidence are retained separately under
`artifacts/phase17/`; no existing server is restarted or stopped.

Prior Phase 16 evidence was inspected: passed browser `.last-run.json`, 80 PNG
checks, actual model scores, source hashes and PDF exact-embedding report.
The latest 80-PNG/font/geometry/PDF verification is documented in
[Phase 16](PHASE16_QUALITY_REPORT.md). It is separate from fresh Phase 17 runs.
Real paid copy quality and same-strategy ranking accuracy are not validated.

CI runs only after the authorized push/PR. The final PR checks tab is the
authoritative remote result; local tests must not be described as CI success.
At preflight main rules require a PR and prohibit deletion/force push, but list
no required CI contexts. We still require all five existing workflow jobs to
pass for this review; no protection or workflow is weakened.

## B review checklist

B is unambiguously identified by `docs/MODEL_DEVELOPMENT.md`, merged ML PRs
#48/#52 and current repository write permission as **parkyeonwooo**. A review
request is authorized; it does not authorize merge.

1. Confirm unchanged `RankInput(candidate_id, final_png_path)`, preprocessing,
   feature order, bundle/scaler/weights and model version semantics.
2. Check v2's four different strategies and v3's four same-strategy candidates;
   IDs, asset IDs, revision and snapshot must map to their actual final PNGs.
3. Inspect ordering, ties, reordered inputs, stale/late replies and failed-model
   behavior. Mock is explicit; no quiet model-to-Mock substitution.
4. Distinguish A's rendered PNG changes (alpha margin placement, typography)
   from B's unchanged feature extraction. Input pixel distribution changes can
   change raw scores without improving preference prediction.
5. Review Phase 16 before/after results: Emotional DABC→DBAC, Price BCDA→CABD,
   Brand CBAD→CBDA, Visual CADB→CDAB. Full raw score deltas/timings are private
   local evidence, not probabilities, CTR or measured quality improvements.
6. Confirm diagnostics remain independent and do not override or sum into ML
   scores. A high model score never suppresses a caution/unavailable rule.
7. Evaluate same-strategy ranking separately using consented, blinded A/B user
   preferences, balanced display order, product/brand-separated holdouts and
   agreement/uncertainty reporting. No new data collection or training is
   performed in this PR; the protocol requires joint A/B review first.

Suggested review request message:

> B님, v3는 같은 전략의 최종 PNG 네 장을 기존 모델 API로 전달합니다.
> ML 코드·가중치·특징 추출은 변경하지 않았습니다. candidate/asset/revision
> 매핑과 v2 회귀, 이미지 배치 변경에 따른 점수 차이를 확인해 주세요.
> 같은 전략 내 추천 정확도는 아직 검증되지 않았으므로 별도 선호 평가가
> 필요합니다. diagnostics는 점수와 분리했습니다. 이 PR은 리뷰용이며
> main 병합·배포는 별도 사용자 승인 전까지 진행하지 않습니다.

## Preserved state and review environment

Ledger stays 8 completed / $0.01274025, SHA-256
`2b221949d6d59a36906e5150118bce454a4cc8c54ec077f873203cedb81597b6`.
No paid calls, retraining, model download, environment replacement or deployment.
Existing servers/Tunnel, transfer backup, credentials, uploads/downloads and
source design files are preserved. New test jobs/files are confined to the
existing isolated test server and ignored test outputs.

Local UI `http://127.0.0.1:5187`, backend `http://127.0.0.1:8017`; the private
Phase 16 gallery remains outside Git. Review the four variations, warnings,
optional model ranks, editing and downloads with Mock copy only. Processes
are not guaranteed to survive reboot. Human design acceptance and explicit
main merge approval are still required after CI and team review.
