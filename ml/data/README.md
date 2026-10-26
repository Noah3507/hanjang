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
- 라벨: `(item_id, image)`별로 pv·clk를 합산한 뒤 평활 CTR `(clk+α)/(pv+α+β)`를 씁니다. 비교는 같은 제품 안의 이미지끼리만 합니다. 최소 pv 기준과 α·β는 5단계에서 정합니다.

## 공통

- 코드는 특정 데이터셋에 묶지 않고, "같은 그룹 안의 이미지 선호 순서" 형태로 변환해서 사용합니다.
- 전략 라벨(emotional/price/visual/brand)은 feature로 쓰지 않습니다.
