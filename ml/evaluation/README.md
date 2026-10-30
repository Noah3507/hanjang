# 평가와 baseline (B)

## baseline (8단계, baselines-v1)

`python scripts/ml_baselines.py`가 split 결과와 7단계 feature cache를 읽어 **val 쌍**에서 단순한 비교 기준들의 pairwise accuracy를 계산하고 `data/evaluation/baselines-v1/results.json`(Git 제외)에 저장한다. test 쌍은 최종 평가(10단계)까지 쓰지 않는다.

| baseline | 방법 |
| --- | --- |
| random | 쌍마다 seed 고정 동전 던지기. 약 0.5가 정상 |
| rule | 이미지 통계 하나(밝기·대비·채도·색 수)를 점수로 쓰고 높은 쪽 또는 낮은 쪽이 이긴다고 본다. 어떤 통계·방향을 쓸지는 **train 쌍에서만** 고른다 |
| laion_aesthetic | LAION-Aesthetics Predictor V1의 CLIP ViT-B/32용 선형 head(512→1, MIT 라이선스). 7단계의 L2 정규화 CLIP embedding에 그대로 곱한다. 선호가 단순한 "미적 점수"로 설명되는지 본다 |
| LLM-as-Judge | 보류. 유료 API와 이미지 외부 전송이 필요해서 A와 합의 전에는 실행하지 않는다 |

- 공정성: 모든 baseline을 데이터셋별로 **같은 val 쌍**에서 계산한다. 결과에 val·train 쌍 수와 표준오차를 함께 적는다.
- 동점(두 점수가 같음)은 0.5로 센다.
- TASTE는 같은 이미지 쌍에 평가자 여러 명의 표가 따로 들어 있어서, 평가자끼리 의견이 다르면 어떤 방법도 100%가 될 수 없다.
- LAION 가중치 받기: `mkdir -p data/raw/laion` 후 `curl -L -o data/raw/laion/sa_0_4_vit_b_32_linear.pth https://github.com/LAION-AI/aesthetic-predictor/raw/main/sa_0_4_vit_b_32_linear.pth`. 파일은 `torch.load(weights_only=True)`로 읽어 코드 실행 없이 가중치만 불러오고, 크기(weight 1×512, bias 1)를 검사한다. SHA-256은 results.json의 `inputs`에 기록된다.

## 최종 평가 (10단계, final-test-v1)

`python scripts/ml_evaluate.py`가 test split을 **딱 한 번** 평가하고 `data/evaluation/final-test-v1/results.json`(Git 제외)에 저장한다. 아래 계획과 판단 기준은 실행 전에 A와 확정했다(10/30, PR #41 리뷰 반영).

**실행 순서**
1. `python scripts/ml_evaluate.py --check-only`: 모델·feature·center crop feature·test 쌍의 구조(이미지·묶음)만 확인한다. test 라벨(`a_wins`) 열은 읽지 않고 아무것도 쓰지 않는다.
2. A가 확인 결과에 동의하면 `python scripts/ml_evaluate.py`를 한 번 실행한다.
3. 결과 폴더가 이미 있으면 스크립트가 멈춘다. 재실행 옵션은 없다. 결과를 쓰기 전에 실패했다면 폴더가 생기지 않으므로 그대로 다시 실행할 수 있다(쓰기는 전부 성공하거나 전혀 안 되는 방식). 그 밖의 재실행은 A의 승인과 이유 기록 후 기존 폴더를 손으로 옮겨야만 가능하다.

**평가 내용**
- 모델(고정): CreativeRanking 모델 `bt-logistic-v1`(서비스 기본 순위, train만 학습, l2=0.1)과 TASTE 모델 `bt-taste-v1`(디자인 선호 참고 지표, train+val 학습, l2=30, `python scripts/ml_train_taste.py`). test를 본 뒤 모델·설정·기준을 바꾸지 않는다.
- 주 결과: CreativeRanking 모델 → CreativeRanking test, TASTE 모델 → TASTE test. 두 모델을 반대쪽 test에서도 보고한다.
- 정확도와 95% **묶음 bootstrap** 구간(2000회, seed 0). 묶음은 이미지를 공유하는 test 쌍끼리 이은 연결 성분이다. TASTE는 이것이 6단계 `split_group`과 같은지 검사하고 다르면 멈춘다. CreativeRanking은 같은 이미지를 쓰는 상품끼리 하나로 묶인다.
- baseline 대비 차이: 주 모델의 정확도에서 각 baseline(random, train에서 고른 통계 규칙, LAION)을 뺀 값과 그 95% 구간을 같은 묶음으로 짝지은 bootstrap으로 계산한다. **가장 강한 baseline은 미리 정한 통계 규칙**(8단계 val에서 두 데이터셋 모두 가장 좋았음)이다.
- 순위 묶음(TASTE 한 표의 4장, CreativeRanking 한 상품의 관측 CTR 순서)마다 Top-1과 Kendall's tau, 무작위 Top-1 기준값.
- 점수 차이 |s_A − s_B| 구간별 정확도. sigmoid 값의 확률 보정은 검증하지 않았으므로 '예측 확률'이 아니라 '점수 차이 구간'으로 부른다. 화면의 "근소한 차이" 기준은 **CreativeRanking val**의 구간 결과로 A와 정하고, test 구간은 확인용으로만 본다.
- TASTE 디자이너 일치도: 같은 쌍의 다수 의견(그 표 자신 포함)과 맞는 표의 비율. 평가자 간 일관성의 참고값이며 독립적인 사람 성능 상한으로 해석하지 않는다.
- center crop 민감도: padding으로 학습한 같은 모델에 test 이미지의 center crop CLIP feature를 넣었을 때의 정확도와 padding과의 차이. 이미지 통계 4개는 원본 이미지 값 그대로 둔다. center crop으로 다시 학습한 모델과의 비교가 아니다(그러려면 train 이미지의 center crop feature가 필요해서 이번 범위 밖).

**판단 기준 (test 전에 확정)**
- CreativeRanking 모델을 서비스 기본 순위에 **사용**: 정확도 95% 구간 하한 > 0.5 **그리고** (모델 − 통계 규칙) 95% 구간 하한 > 0 **그리고** Top-1 > 무작위 Top-1. 하나라도 아니면 **보류**: 서비스는 MockRanker(모의 순위 표시)를 유지하고 결과를 그대로 보고한다. test 결과를 보고 모델을 고치지 않는다.
- TASTE 모델을 디자인 선호 **참고 지표로 표시**: 정확도 95% 구간 하한 > 0.5 **그리고** (모델 − 통계 규칙) 95% 구간 하한 > 0. 아니면 **보고서에만** 기록하고 화면에는 표시하지 않는다.
- 전처리: 결과와 관계없이 padding을 유지한다. center crop 민감도는 보고만 하고, 바꾸려면 새 데이터로 다시 검증해야 한다.
- 실제 서비스 연동과 PR 병합 여부는 결과를 본 뒤 A와 따로 정한다.
- 점수는 상대 선호이며 클릭률·매출 예측이 아니다. CreativeRanking은 권리 미확인 데이터라 연구용 결과로만 쓴다.
