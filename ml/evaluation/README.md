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
