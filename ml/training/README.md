# 선호 모델 학습 (B, 9단계)

`python scripts/ml_train.py`가 7단계 feature cache와 6단계 split을 읽어 **Logistic Bradley–Terry** 모델을 학습하고 `artifacts/models/ranking/bt-logistic-v1/`(Git 제외)에 저장한다.

- 점수: 이미지마다 `s = w · z`. `z`는 CLIP embedding(512) + 이미지 통계(4)를 **train 이미지의 평균·표준편차로만** 표준화한 값. 두 광고의 선호 확률은 `sigmoid(s_A − s_B)`로 계약의 `bradley_terry_sigmoid_v1`과 같다.
- 학습: feature 차이에 대한 절편 없는 logistic regression + L2 규제. CPU float64 전체 배치 L-BFGS라 같은 데이터·config면 항상 같은 가중치가 나온다(seed 불필요).
- 설정 비교(`ml/training/config.json`): 학습 데이터 3종(TASTE만, CreativeRanking만, 둘 다) × L2 4종. 둘 다 쓸 때는 데이터셋마다 같은 비중을 준다.
- 모델 선택(10/30 A와 합의, test 평가 전 확정): **CreativeRanking val 정확도**가 가장 높은 설정을 고른다. 같으면 TASTE val 정확도, 그래도 같으면 더 강한 L2. 서비스 대상(상품 광고 비교)과 가깝고 val 7,067쌍으로 안정적이기 때문이다. TASTE는 val 서로 다른 비교가 144개뿐이라(표준오차 약 ±0.04) 선택 기준으로는 흔들리므로 보조 결과로 보고한다. test 결과를 본 뒤 이 기준을 바꾸지 않는다.
- 입력 검사: feature cache의 `feature_version`이 config와 같은지, CLIP 폭이 manifest의 `embedding_dim`과 같은지, 통계 열이 manifest와 같은지, 두 데이터셋의 열 순서가 같은지, NaN·무한대가 없는지, 이미지가 index에 한 번만 있는지, 쌍의 split과 cache에 기록된 이미지 split이 같은지 확인한다. 하나라도 어긋나면 학습 전에 멈춘다.
- test split은 읽지 않는다. 최종 평가는 10단계에서 한 번만 한다.
- 저장 파일: `model.safetensors`(weights, scaler_mean, scaler_std; pickle 아님), `model_config.json`(feature 열 순서, CLIP·통계·전처리 버전, 선택된 설정), `training_report.json`(모든 설정의 train/val 결과, 8단계 baseline 비교, 코드 커밋, 입력 SHA-256).
- v2 MLP는 Logistic보다 val에서 분명히 좋을 때만 검토한다.
- TASTE 디자인 선호 모델(10/30 A와 합의, 9-7 결과): `python scripts/ml_train_taste.py`가 `ml/training/taste_config.json`대로 TASTE train+val을 l2=30으로 학습해 `artifacts/models/ranking/bt-taste-v1/`에 같은 형식으로 저장한다. 서비스 기본 순위에는 쓰지 않고 별도 참고 지표로만 쓴다. 모델 폴더는 `load_model()`로 읽으며 크기·유한값을 검사한다.
