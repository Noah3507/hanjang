# Model card: bt-logistic-v1 (한장 광고 상대 선호 모델)

작성: B, 2026-10-31. 대상: A(서비스 연동)와 발표·보고서 독자. 숫자는 모두 저장소의 스크립트로 다시 만들 수 있다.

## 한 줄 요약

광고 PNG 한 장에 **상대 선호 점수**를 매기는 선형 Bradley–Terry 모델이다. 같은 상품 광고 네 장의 순위를 정하는 데 쓴다. **클릭률·구매율·매출을 예측하지 않으며**, 점수와 pairwise 값은 보정된 확률이 아니다.

## 용도

| 쓸 수 있음 | 쓰면 안 됨 |
| --- | --- |
| 한장이 만든 1080×1350 광고 4장 중 상대적으로 더 선호될 후보를 순위로 보여 주기 | 클릭률·매출·구매 확률 예측, 광고비 결정 |
| 점수 차이가 작을 때(<0.2) "순위 차이가 근소합니다"처럼 문구로 알려 주기 | 점수나 pairwise 값을 % 확률·CTR처럼 표시 |
| 연구·시제품 시연 | 권리 확인 없는 상업 서비스 (아래 '데이터와 권리') |
| | 디자인 품질의 절대 평가, 광고가 아닌 이미지, 다른 상품끼리의 비교 |

## 입력과 출력

- 입력: 최종 광고 PNG, 1080×1350, 불투명 RGB. 계약: `docs/RANKING_CONTRACT_V1_1.md`.
- 특징(516): 흰색 정사각형 padding(`pad-square-v1`) 후 CLIP ViT-B/32(openai, QuickGELU, 224px) L2 정규화 임베딩 512 + 원본 이미지의 밝기·대비·채도·색 수 4(`stats-v1`).
- 점수: `s = Σ w·(x − mean)/std` (train 이미지로 맞춘 scaler). 두 광고의 비교 값은 `sigmoid(s_A − s_B)` (`bradley_terry_sigmoid_v1`, temperature 1).
- API·예외·bundle 형식: `ml/inference/README.md`.

## 데이터와 권리

| 데이터 | 쓰임 | 출처 | 권리 |
| --- | --- | --- | --- |
| CreativeRanking | **학습**, 선택(val), 최종 평가(test) | Hugging Face `Evan12/CreativeRanking` revision `16ad7beb…` (공개 사본) | **원본·라이선스·이용 권한 미확인. 연구·시제품용으로만 사용** |
| TASTE | 보조 평가, 보조 모델 실험 | Hugging Face `purvanshi/TASTE` revision `731a7f58…` | 데이터셋 카드 조건 확인 필요 |

- CreativeRanking 쌍: 같은 상품의 광고 이미지 중 노출 100회 이상인 것끼리, 클릭률 차이의 z값이 1.96 이상인 쌍만 사용(`ml/data/pair_config.json`). 상품은 원래 분할에서 train 14,000 / val 3,000 / test 3,000개를 뽑았고, 여러 분할에 걸친 이미지는 가장 앞 분할에만 남겼다.
- 레이블은 **관측된 클릭으로 드러난 상대 선호**이다. 사람에게 직접 물은 선호가 아니다.
- 서비스에 상업적으로 쓰기 전에는 CreativeRanking의 이용 권한을 확인하거나, 권리가 확인된 데이터로 다시 학습해야 한다.

## 학습과 선택

- 학습: CreativeRanking **train 쌍만**, L2=0.1, 절편 없는 logistic regression, float64 전체 배치 L-BFGS(같은 입력이면 같은 가중치). 코드 `ml/training/`, `scripts/ml_train.py`.
- 비교한 설정: 학습 데이터 3종(TASTE만 / CreativeRanking만 / 둘 다) × L2 4종. 선택 규칙은 10/30 A와 합의(CreativeRanking val 정확도 우선 → TASTE val → 더 강한 L2), test를 보기 전에 확정했다. 선택된 설정의 val: CreativeRanking 0.6835, TASTE 0.510.
- TASTE만으로 학습한 디자인 선호 모델(`bt-taste-v1`)은 test 판정 기준을 넘지 못해 **보고서에만** 남기고 서비스에 넣지 않았다.

## 평가 (test 한 번, 2026-10-30, results.json SHA-256 `67cf5319…d4a5`)

정확도는 두 광고 중 더 선호된 쪽을 맞힌 비율(동점 0.5, 무작위 0.5). 괄호는 이미지를 공유하는 상품끼리 묶어 다시 뽑은 bootstrap 95% 구간(2000회).

**CreativeRanking test (6,790쌍, 3,000상품, 2,784묶음)**

| 방법 | 정확도 [95% 구간] |
| --- | --- |
| **bt-logistic-v1** | **0.675** [0.659, 0.690] |
| 이미지 통계 규칙(어두운 쪽, train에서 선택) | 0.568 [0.552, 0.584] |
| LAION 미적 점수 | 0.523 [0.505, 0.540] |
| 무작위 | 0.503 [0.492, 0.515] |

- 규칙 대비 **+0.107** [+0.086, +0.127]. Top-1(상품 안에서 관측 클릭률 1위를 맞힘) 0.506, 무작위 0.371. Kendall's tau +0.26.
- 사전 판단 기준(정확도 하한 > 0.5, 규칙 대비 하한 > 0, Top-1 > 무작위)을 모두 넘어 **서비스 기본 순위에 사용**으로 판정.
- 전처리: 같은 모델에 center crop 특징을 넣으면 정확도가 0.009 [0.003, 0.016] 낮다. padding을 유지한다.
- TASTE test(디자이너 선호)에서는 0.536 [0.486, 0.588], Top-1은 무작위보다 낮음 → **디자이너 선호를 대표하지 않는다.**

**점수 차이와 정확도 (CreativeRanking val, '근소한 차이' 기준을 정한 근거)**

| \|s_A − s_B\| | 0–0.2 | 0.2–0.4 | 0.4–0.8 | 0.8–1.4 | 1.4 이상 |
| --- | --- | --- | --- | --- | --- |
| val 정확도 | 0.546 | 0.592 | 0.642 | 0.792 | 0.892 |
| test 정확도 | 0.514 | 0.583 | 0.658 | 0.781 | 0.912 |

`close_call_score_gap = 0.2`(A와 합의): 차이가 0.2 미만이면 거의 무작위 수준이라 순위 차이를 강조하지 않는다.

## 한계

- 도메인 차이: 학습 데이터는 전자상거래 상품 광고 이미지이다. 한장의 소상공인 광고(한글 문구, 다른 디자인 관습)에서의 정확도는 **측정하지 않았다.** test 결과는 같은 데이터셋 안의 일반화이다.
- 문구의 의미: CLIP 224px 입력이라 작은 글씨의 내용을 읽는다고 기대할 수 없다. 문구를 고친 광고의 점수 변화는 주로 시각적 변화에서 온다.
- 디자이너 선호와 다름: TASTE에서 무작위 수준. "잘 디자인된 광고"의 점수가 아니다.
- 확률 보정 미검증: `sigmoid(s_A − s_B)`는 모델의 상대 비교 값이다.
- 상품 간 비교 불가: 같은 상품의 후보끼리만 학습·평가했다. 서로 다른 상품 광고의 점수 비교는 의미가 없다.
- 데이터 권리 미확인(위). 편향 분석(업종·가격대별)은 하지 않았다.

## 실행 환경과 성능

- `.venv-rank`: Python 3.12, `ml/inference/requirements.txt`(torch 2.14.1, open_clip_torch 3.3.0, pillow 13.0.0, numpy 2.5.4, safetensors 0.8.0 등 31개). 버전이 manifest와 다르면 `ArtifactMismatch`.
- CPU 전용, 네트워크 없음. 학습 feature cache와 추론 특징의 차이: val 32장에서 CLIP 0.0, 통계 0.0.
- 맥북(Apple Silicon, `scripts/ml_benchmark_inference.py`): load 0.88초, 광고 4장 순위 중앙값 0.134초·p95 0.145초, 최대 메모리 약 1.33GB. Windows 값은 A가 같은 스크립트로 측정해 이 표에 추가한다.

## 파일, 체크섬, 확인 절차

- bundle `artifacts/models/ranking/bt-logistic-v1/`(Git 제외, 약 351MB): `manifest.json`, `model.safetensors`, `model_config.json`, `clip/ViT-B-32-openai-visual.safetensors`. 파일별 SHA-256·크기는 manifest와 `ml/inference/smoke_expected.json`(Git에 있음)에 있다.
- 확인(A, `.venv-rank`): `python scripts/ml_smoke_inference.py` → 체크섬 대조, fixture 네 장의 순위가 같고 점수 차이 1e-3 이내면 `PASS`. fixture는 합성 그림이라 순위는 재현 확인용일 뿐 광고 품질과 무관하다.
- 전달: zip으로 묶어 A와 정한 비공개 경로로만 보낸다. Git·공개 링크 금지.
