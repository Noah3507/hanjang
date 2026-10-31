# 서비스용 추론 패키지 (B, 11단계)

A와 10/31에 합의한 계약이다. 기준은 `docs/RANKING_CONTRACT_V1_1.md`와 `tests/fixtures/contracts/rank-output.schema.json`이다. 10단계 test 결과에 따라 **CreativeRanking 모델 `bt-logistic-v1`만** 담는다(TASTE 모델은 보고서에만 남음).

## 사용법 (`.venv-rank`)

```python
from pathlib import Path
from ml.inference import RankInput, RankingError, load_model, rank_ads

model = load_model(Path("artifacts/models/ranking/bt-logistic-v1"),
                   model_file=Path("artifacts/models/ranking/bt-logistic-v1/model.safetensors"))  # RANKING_MODEL_PATH
try:
    out = rank_ads([RankInput("c_emotional", Path(".../emotional.png")), RankInput("c_price", Path(".../price.png")),
                    RankInput("c_visual", Path(".../visual.png")), RankInput("c_brand", Path(".../brand.png"))], model)
except RankingError:
    ...  # 네 후보 전체를 MockRanker로 대체 (A adapter)
scores = {i["candidate_id"]: i["score"] for i in out["items"]}
close_call = abs(scores["c_visual"] - scores["c_price"]) < model.close_call_score_gap  # 0.2, 화면에는 문구로만
```

| 함수 | 반환 |
| --- | --- |
| `load_model(artifact_dir, model_file=None)` | `ModelHandle` (frozen dataclass, 배열은 읽기 전용, CLIP은 eval·gradient 없음). worker 시작 때 한 번 |
| `extract_features(image_path, model)` | `FeatureVector` = numpy float64 (516,), 유한값, 읽기 전용, 순서는 `model.feature_columns` |
| `score_ad(image_path, model)` | raw score(float). 높을수록 선호. 확률·CTR 아님 |
| `rank_ads(items, model)` | rank-output schema와 같은 dict. `items`는 입력 순서, rank는 score 내림차순(동점은 candidate_id 사전순), pairwise는 ID 사전순 6쌍의 `sigmoid(s_a - s_b)` |

- 특징은 학습과 똑같이 계산한다: 흰색 정사각형 padding(`pad-square-v1`) → CLIP ViT-B/32(QuickGELU) → L2 정규화 + 원본 이미지의 통계 4개. 이미지마다 따로 인코딩하므로 `rank_ads`와 `score_ad`의 점수가 같다.
- 입력 광고: 1080×1350 PNG, 불투명 RGB(완전히 불투명한 RGBA는 허용).
- CPU만 쓰고 네트워크를 쓰지 않는다. `ml.inference`는 pandas를 import하지 않는다.

## 예외 (모두 `RankingError` 상속)

| 예외 | 언제 |
| --- | --- |
| `ModelNotAvailable` | bundle 폴더·manifest·목록의 파일이 없거나 읽을 수 없음 |
| `ArtifactMismatch` | SHA-256·크기, 버전, 차원, 열 순서, 전처리 설정, 설치된 torch/open_clip_torch/pillow/numpy/safetensors 버전이 manifest와 다름, 설정된 모델 파일이 manifest의 파일이 아님, bundle 밖을 가리키는 파일 |
| `InvalidImage` | 파일 없음, PNG 아님, 디코딩 실패, 불투명 RGB 아님, 1080×1350 아님 |
| `InferenceFailure` | 인코딩·점수 계산 오류, 유한하지 않은 값 |

메시지에는 파일 이름까지만 넣고 절대 경로·stack은 넣지 않는다. 후보가 4개가 아니거나 ID가 겹치면 `ValueError`(호출 실수). 실패해도 다른 모델로 조용히 바꾸지 않는다.

## bundle과 manifest

```text
artifacts/models/ranking/bt-logistic-v1/      (Git 제외)
  manifest.json                    ranking-bundle-v1 (자기 자신의 해시는 넣지 않음)
  model.safetensors                가중치·scaler (ml_train.py)
  model_config.json                feature 순서·버전 (ml_train.py)
  clip/ViT-B-32-openai-visual.safetensors   CLIP 이미지 부분만 (약 350 MB)
  training_report.json, bundle_report.json  참고용, manifest 목록 밖
```

manifest 주요 항목: `model_version`, `feature_version`, `preprocessing_version`, `method`, `close_call_score_gap`(0.2), `clip`(model·pretrained·quick_gelu·input_size·embedding_dim·pad_color·weights_file), `stats`, `feature_columns`(516), `image`(PNG·opaque RGB·1080×1350), `packages`(정확한 버전), `files`(파일별 `sha256`·`bytes`), `code`(만든 commit).

만들기(B, `.venv-ml`): `python scripts/ml_build_bundle.py`. 학습 결과 폴더에 CLIP 가중치와 manifest를 더하고, 새 bundle을 `load_model`로 읽어 **val 이미지 32장의 특징이 학습 feature cache와 같은지**(CLIP 1e-5, 통계 1e-6 이내) 확인한 뒤에만 폴더를 바꾼다. 결과는 `bundle_report.json`.

## `.venv-rank`와 측정

```bash
python3.12 -m venv .venv-rank
.venv-rank/bin/pip install -r ml/inference/requirements.txt     # Windows: .venv-rank\Scripts\pip
python scripts/ml_benchmark_inference.py                        # .venv-rank에서, bundle이 있을 때
```

`requirements.txt`는 `ml/requirements.txt`를 제약으로 open_clip_torch·pillow·numpy·safetensors를 새 venv에 설치한 뒤 고정한 목록이다(pandas·pytest 없음, 실제 설치로 확인). 측정 스크립트는 load 시간, 첫 `rank_ads`, warm `rank_ads`(중앙값·p95·최대), 최대 메모리(표준 라이브러리, Windows 포함)를 JSON 한 줄로 출력한다. timeout(초기 10초)과 worker 재시작은 A의 worker가 담당하고, 이 패키지는 동기 함수로 둔다.

## 전달과 재현 확인 (12단계)

1. B: `python scripts/ml_build_bundle.py`(`.venv-ml`) → `bundle_report.json`의 cache check `ok: true`. 그다음 `.venv-rank`에서 `python scripts/ml_smoke_inference.py --record`로 `ml/inference/smoke_expected.json`(파일별 SHA-256, fixture 점수·순위·pairwise)을 기록해 Git에 올린다.
2. B: `cd artifacts/models/ranking && zip -r bt-logistic-v1.zip bt-logistic-v1` → zip의 SHA-256과 함께 A와 정한 비공개 경로로 전달. Git·공개 링크 금지.
3. A: 같은 위치(`artifacts/models/ranking/bt-logistic-v1/`)에 압축 해제 → `.venv-rank`에 `ml/inference/requirements.txt` 설치 → `python scripts/ml_smoke_inference.py`가 `PASS`인지 확인 → `python scripts/ml_benchmark_inference.py`로 시간·메모리 측정 → 결과를 B에게 공유.

모델 설명(데이터·권리·평가·한계)은 `ml/inference/MODEL_CARD.md`.
