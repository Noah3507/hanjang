# Phase 16 model score comparison

Manifest policy: **0.2**, inclusive `gap <= policy`. Analysis-only comparator: strict `gap < 0.2`.
Neither is validated statistical confidence or same-strategy ranking accuracy. Raw model scores are not CTR or conversion rates.

Source: the final Phase 16 `review-candidate-02/model-comparison.json`, with `before/metadata.json` and `real-cutout/metadata.json`.
Local review directory is outside Git; only sanitized derived numbers/IDs are committed here. No images, copy or absolute paths are included.

## Comparability

{"source_photo_identical": true, "copy_identical": true, "model_and_feature_versions_identical": true, "final_pngs_identical": false, "weight_identity": "Same local RealRanker instance/bundle in Phase16 runner; no per-inference weight hash in source JSON, so historical equality not independently provable"}

Same source photo and copy; different final PNGs/layouts/fonts/placement. Changes are composite design changes, not a controlled estimate of one intervention.
Model/feature version equality is checked. Same bundle use is supported by the Phase 16 runner; the JSON does not record weight hashes per call.
Inference IDs `phase16-{template_id}` were assigned by the comparison runner. Render candidate IDs are separate and retained when available.

## Candidate scores (display rounded only)

| Strategy | Template | Before score | After score | Before rank | After rank | Score change | Rank gain |
|---|---|---:|---:|---:|---:|---:|---:|
| emotional | emotional_a | -0.556567 | -0.390048 | 2 | 3 | +0.166519 | -1 |
| emotional | emotional_b | -0.579301 | -0.357021 | 3 | 2 | +0.222280 | +1 |
| emotional | emotional_c | -1.062487 | -0.751028 | 4 | 4 | +0.311459 | +0 |
| emotional | emotional_d | -0.151560 | 0.097280 | 1 | 1 | +0.248841 | +0 |
| price | price_a | -1.001188 | -0.308498 | 4 | 2 | +0.692690 | +2 |
| price | price_b | -0.346017 | -0.434453 | 1 | 3 | -0.088436 | -2 |
| price | price_c | -0.667298 | -0.241546 | 2 | 1 | +0.425752 | +1 |
| price | price_d | -0.859018 | -0.737391 | 3 | 4 | +0.121627 | -1 |
| brand | brand_a | -0.782970 | -0.892676 | 3 | 4 | -0.109706 | -1 |
| brand | brand_b | -0.540796 | -0.417380 | 2 | 2 | +0.123416 | +0 |
| brand | brand_c | -0.281523 | -0.368261 | 1 | 1 | -0.086738 | +0 |
| brand | brand_d | -1.433900 | -0.740825 | 4 | 3 | +0.693076 | +1 |
| visual | visual_a | -0.256110 | -0.341479 | 2 | 3 | -0.085369 | -1 |
| visual | visual_b | -0.946412 | -0.976585 | 4 | 4 | -0.030174 | +0 |
| visual | visual_c | 0.059813 | 0.275284 | 1 | 1 | +0.215471 | +0 |
| visual | visual_d | -0.321367 | -0.195322 | 3 | 2 | +0.126045 | +1 |

## Six unordered pairs per strategy/version

| Strategy | Version | Policy count/6 | Policy ratio | <0.2 count/6 | <0.2 ratio |
|---|---|---:|---:|---:|---:|
| emotional | before | 1/6 | 16.67% | 1/6 | 16.67% |
| emotional | after | 1/6 | 16.67% | 1/6 | 16.67% |
| price | before | 2/6 | 33.33% | 2/6 | 33.33% |
| price | after | 3/6 | 50.00% | 3/6 | 50.00% |
| brand | before | 0/6 | 0.00% | 0/6 | 0.00% |
| brand | after | 2/6 | 33.33% | 2/6 | 33.33% |
| visual | before | 1/6 | 16.67% | 1/6 | 16.67% |
| visual | after | 1/6 | 16.67% | 1/6 | 16.67% |

Aggregate before: strict <0.2 = 4/24 (16.67%).

Aggregate after: strict <0.2 = 7/24 (29.17%).

## Reproduction

Run with existing Python; no model environment or inference needed. Paths below are placeholders, not private machine paths:
```text
python scripts/service_ranking_comparison.py --comparison <review>/model-comparison.json --before-metadata <review>/before/metadata.json --after-metadata <review>/real-cutout/metadata.json --manifest <bundle>/manifest.json --output-dir <new-output>
```
For reproduction without private review files, use `scores.json`: subtract each candidate score before rounding, enumerate `combinations(sorted(candidate_ids), 2)` (six pairs), and count `abs(left-right) <= close_call_score_gap` and separately `< 0.2`.
JSON/CSV retain binary64 source score precision; Markdown formatting is display-only. Rank gain = before minus after. No missing facts or historical weight hashes are invented.
