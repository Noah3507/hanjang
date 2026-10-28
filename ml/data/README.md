# ML 데이터셋 스키마

원본 데이터는 git에 올리지 않습니다. 위치는 `data/raw/<dataset>/`(git-ignored)이고, `ml/data/`에는 코드와 문서만 둡니다.
내려받기는 `scripts/ml_inspect_hf_dataset.py`를 revision 고정으로 실행하며, 각 폴더의 `provenance.json`에 파일·크기·sha256·revision·받은 시각을 기록합니다.

## TASTE

| 항목 | 값 |
| --- | --- |
| 출처 | Hugging Face `purvanshi/TASTE` |
| revision | `731a7f588d433214c6d864d2e9f47978d91aed6b` |
| 라이선스 | 데이터셋 카드 MIT, LICENSE 파일 포함 |
| 위치 | `data/raw/taste/` |

| 파일 | 행 수 | 열 |
| --- | --- | --- |
| rankings.parquet | 14,460 | eval_round_stage_id, dimension, track, prompt_id, asset_id, evaluator_id, rank |
| assets.parquet | 644 | asset_id, model, image_url, track, image_path |
| prompts.parquet | 721 | prompt_id, track, dimension, prompt_id_src, prompt_text |
| evaluators.parquet | 10 | evaluator_id, tracks, n_ranking_rows, n_halluc_rows |
| hallucinations.parquet | 3,200 | track, prompt_id_src, asset_id, evaluator_id, hallucination_value, hallucination_flag |

- 순위 한 건 = `(prompt_id, evaluator_id)` 묶음의 이미지 4장, rank 1~4 (1 = 가장 선호).
- 정상 묶음 3,595개. 8행 묶음 10개(같은 평가자의 중복 평가, 순위 중복)는 학습에서 제외합니다.
- 학습 목표는 `dimension == "preference"` (3,260행, 4장 묶음 160개). 다른 dimension은 현재 사용하지 않습니다.
- split 기준: 같은 이미지 4장 묶음. 서로 다른 묶음 161개 중 이미지 4장이 두 묶음에 걸쳐 있으므로, 이미지를 공유하는 묶음은 한 그룹으로 합친 뒤 나눕니다.
- `prompt_id`나 `prompt_id_src`로 나누면 안 됩니다. 같은 4장이 여러 dimension에서 재사용되어 학습/평가에 같은 이미지가 섞입니다.
- `eval_round_stage_id`는 dimension별 평가 단계 번호이고 순위 묶음 키가 아닙니다.

## CreativeRanking

| 항목 | 값 |
| --- | --- |
| 출처 | Hugging Face 복사본 `Evan12/CreativeRanking` (원본: Tianchi dataId=93585) |
| revision | `16ad7beb2af81fb35b72b0d4797c688680e3bb05` |
| 라이선스 | 카드에 apache-2.0 표기. 원본 Tianchi 이용 조건은 확인하지 못함 |
| 위치 | `data/raw/creativeranking/` |

> 주의: 복사본 업로더와 원본의 관계, 원본 이용 조건이 확인되지 않았습니다. "승인된 학습 데이터"로 표현하지 않고, 연구·검증용 후보로만 다룹니다.

- 받은 파일: `list.zip`(104.7 MB) → `list/list/{train,val,test}_data_list.txt`. 최상위 `test_data_list.txt`는 압축 안 test 파일과 동일합니다.
- `images.zip`(107.7 GB)은 받지 않았습니다. 이후 제품 1~2만 개 부분집합만 사용합니다.
- 형식: 탭 구분, 헤더 없음, 5열 `item_id`(32자리 제품 ID), `image`(이미지 파일명), `ds`(0~14 일차), `pv`(그날 노출), `clk`(그날 클릭).

| split | 행 | 제품 | 이미지 | 이미지별 총 pv 중앙값 | 전체 CTR |
| --- | --- | --- | --- | --- | --- |
| train | 9,718,149 | 300,242 | 1,026,378 | 50 | 0.0293 |
| val | 3,163,215 | 100,240 | 340,449 | 45 | 0.0292 |
| test | 3,180,146 | 100,345 | 340,906 | 45 | 0.0297 |

- 제품당 이미지 중앙값 3, 최대 11. 이미지당 등장 일수 중앙값 8~9일. clk > pv 행은 0개.
- split 간 제품 중복이 0이므로 원본 split을 그대로 사용합니다.
- 라벨: `(item_id, image)`별로 pv·clk를 합산하고, 같은 제품 안의 두 이미지 CTR 차이를 두 비율 z 검정으로 판단합니다. 평활 CTR(α·β)은 쓰지 않습니다(아래 "비교 쌍" 참고).

## 비교 쌍 (pairs-v1)

`python scripts/ml_build_pairs.py`가 `data/raw/`를 읽어 `data/processed/pairs/`(Git 제외)에 `taste.parquet`, `creativeranking.parquet`, `stats.json`을 씁니다. 기준 숫자는 `ml/data/pair_config.json`에 있습니다.

- 공통 열: `dataset`, `source_split`, `group_id`, `image_a`, `image_b`, `a_wins`. 항상 `image_a < image_b`(문자열 순)이고 `a_wins`는 1(A 선호) 또는 0입니다. 같은 이미지끼리의 쌍은 없습니다.
- TASTE: `preference`의 평가 한 건(이미지 4장, rank 1 = 최선호)마다 6쌍. 평가 묶음은 행 4개, 서로 다른 `asset_id` 4개, 이미지 경로 4개(누락·중복 없음), 순위가 정확히 1·2·3·4일 때만 쓰고 나머지는 제외해 `stats.json`의 `dropped_by_reason`에 이유별로 셉니다. `assets`에 같은 `asset_id`가 두 번 있으면 오류로 멈춥니다. `source_split`은 비어 있고 6단계에서 4장 묶음 단위로 나눕니다. 평가자별 표를 합치지 않고 한 표를 한 행으로 둡니다.
- CreativeRanking: 이미지별 합산 pv가 `min_pv`(100) 이상인 이미지만, 같은 제품 안에서만 짝짓습니다. 두 비율 z 검정의 |z|가 `min_z`(1.96) 이상인 쌍만 남기고 CTR이 높은 쪽이 이깁니다. 원본 split별로 쌍이 있는 제품을 해시 순서로 정해 train 14,000 / val 3,000 / test 3,000개만 씁니다(같은 config면 항상 같은 제품). `pv_a`, `clk_a`, `pv_b`, `clk_b`, `z`를 함께 저장해 방향을 직접 확인할 수 있습니다.
- CreativeRanking 결과도 여전히 권리 미확인 데이터입니다. 연구·검증용으로만 씁니다.
- CreativeRanking 라벨은 관측 CTR에 기반한 상대 비교용 약한 라벨(weak label)입니다. |z| ≥ 1.96은 관측 CTR 차이가 통계적으로 구분된다는 뜻일 뿐, 노출 대상·시간대·캠페인 차이를 통제하지 않으므로 이미지가 CTR 차이의 원인이라는 증거가 아닙니다. 쌍마다 검정을 반복하므로 다중 비교에 따른 오탐도 일부 섞일 수 있습니다.
- 재현: 같은 revision의 원본과 `pairs-v1` config로 실행하면 2026-10-27 맥북 기준 TASTE 4,770쌍(평가 795건, 제외 10건), CreativeRanking train 32,018 / val 7,068 / test 6,791쌍이 나옵니다. 실행마다 `stats.json`에 같은 통계가 기록됩니다.
- 입력 검증: CreativeRanking 원본 행에 제품·이미지 값 누락, pv·clk 누락·숫자 아님·음수, clk > pv가 하나라도 있으면 합산 전에 오류로 멈춥니다.
- 결과 저장: 모든 처리가 성공해야 `data/processed/pairs/`가 한 번에 바뀝니다. 중간에 실패하면 이전 결과가 그대로 남고 일부 파일만 바뀌지 않습니다.
- 추적 정보: `stats.json`에 코드 커밋(`code.commit`, 수정 중이었는지 `code.dirty`), 입력 파일별 크기·SHA-256(`inputs`), 원본 다운로드 기록(`sources`, 각 `provenance.json`)을 남깁니다.

## 공통

- 코드는 특정 데이터셋에 묶지 않고, "같은 그룹 안의 이미지 선호 순서" 형태로 변환해서 사용합니다.
- 전략 라벨(emotional/price/visual/brand)은 feature로 쓰지 않습니다.

## 학습·검증·테스트 나누기 (split-v1)

`python scripts/ml_split_pairs.py`가 `data/processed/pairs/`를 읽어 `data/processed/splits/split-v1/`(Git 제외)에 `taste.parquet`, `creativeranking.parquet`, `stats.json`을 씁니다. 비율은 `ml/data/split_config.json`에 있습니다.

- 결과에 `split`(train/val/test)과 `split_group`(함께 움직이는 묶음) 열이 추가됩니다.
- TASTE: 이미지를 하나라도 공유하는 디자인 요청은 한 묶음으로 합친 뒤, 묶음 단위로 70/15/15를 해시 순서로 나눕니다. 같은 config면 항상 같은 결과입니다. 비율은 쌍 개수가 아니라 **묶음 개수** 기준이라, 묶음마다 쌍 수가 다르면 쌍 비율은 70/15/15에서 벗어날 수 있습니다(현재 데이터는 묶음마다 6쌍×평가자 수가 같아 쌍 비율도 3,330/720/720으로 맞습니다).
- CreativeRanking: 원본 split을 그대로 씁니다(제품 겹침 0). 다만 같은 이미지 파일을 다른 split의 제품이 함께 쓰는 경우가 있어, 그런 이미지는 가장 앞선 split(train → val → test)에만 남기고 뒤 split에서 그 이미지가 들어간 쌍은 뺍니다. 개수는 `stats.json`의 `cross_split_images`, `dropped_cross_split_pairs`, 쌍이 모두 빠져 사라진 제품 수 `groups_emptied_by_dedup`에 기록합니다. 이미지를 빼기 전에 같은 제품(`group_id`)이 두 원본 split에 들어 있으면 바로 오류로 멈춥니다.
- 누수 검사: 한 묶음이나 한 이미지가 두 split에 나타나면 스크립트가 오류로 멈춥니다. 결과는 `stats.json`에 기록합니다.
- 결과 저장: 모든 split과 누수 검사가 성공해야 `split-v1/`이 한 번에 바뀝니다. 중간에 실패하면 이전 결과가 그대로 남습니다. `stats.json`에 코드 커밋(`code`)과 입력 파일 SHA-256(`inputs`)을 남깁니다.
- test는 최종 평가 때까지 보지 않습니다. 모델 선택과 설정 조정은 val만 씁니다.
