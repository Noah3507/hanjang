# 선호 모델 학습 (B, 9단계)

`python scripts/ml_train.py`가 7단계 feature cache와 6단계 split을 읽어 **Logistic Bradley–Terry** 모델을 학습하고 `artifacts/models/ranking/bt-logistic-v1/`(Git 제외)에 저장한다.

- 점수: 이미지마다 `s = w · z`. `z`는 CLIP embedding(512) + 이미지 통계(4)를 **train 이미지의 평균·표준편차로만** 표준화한 값. 두 광고의 선호 확률은 `sigmoid(s_A − s_B)`로 계약의 `bradley_terry_sigmoid_v1`과 같다.
- 학습: feature 차이에 대한 절편 없는 logistic regression + L2 규제. CPU float64 전체 배치 L-BFGS라 같은 데이터·config면 항상 같은 가중치가 나온다(seed 불필요).
- 설정 비교(`ml/training/config.json`): 학습 데이터 3종(TASTE만, CreativeRanking만, 둘 다) × L2 4종. 둘 다 쓸 때는 데이터셋마다 같은 비중을 준다. **val 정확도의 두 데이터셋 평균**이 가장 높은 설정을 고른다(같으면 더 강한 L2).
- test split은 읽지 않는다. 최종 평가는 10단계에서 한 번만 한다.
- 저장 파일: `model.safetensors`(weights, scaler_mean, scaler_std; pickle 아님), `model_config.json`(feature 열 순서, CLIP·통계·전처리 버전, 선택된 설정), `training_report.json`(모든 설정의 train/val 결과, 8단계 baseline 비교, 코드 커밋, 입력 SHA-256).
- v2 MLP는 Logistic보다 val에서 분명히 좋을 때만 검토한다.
