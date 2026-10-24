# A/B 모델 연동 계약 v1.1

2026-10-24 사용자 승인 방향과 실행 가능한 계약 예제를 정리합니다. 서비스 기능·B 학습 코드를 추가하지 않습니다. 이 문서는 [API_CONTRACT](API_CONTRACT.md), [MODEL_HANDOFF](MODEL_HANDOFF.md)의 과거 제안 중 아래 항목을 대체합니다. 배포·가중치·encoder와 실제 adapter는 미구현/미확정입니다.

## 확정한 경계

| 항목 | 계약 |
| --- | --- |
| 라이브러리 | open_clip_torch, Python import는 open_clip. 서비스/ML 환경 분리 |
| 최종 광고 | 1080×1350 PNG, 불투명 RGB, 네 전략 emotional/price/visual/brand |
| 전처리 상품 | 배경 제거용 RGBA PNG 가능. 최종 광고와 다른 asset이며 ranking 입력 아님 |
| CLIP 입력 | 최종 광고 전체를 비율 유지 resize + padding. 중요한 문구를 자르는 후속 center crop 금지 |
| feature | encoder·pretrained·입력 크기·feature 차원은 metadata에서 결정. ViT-L/14·768을 기본 모델로 확정하지 않음 |
| batch | 정확히 네 candidate ID, 입력 배열 순서 유지. rank는 별도 필드 |
| 버전 | 같은 batch는 동일 model_version/feature_version. 전처리 version은 bundle manifest에 고정 |
| score | 유한한 상대 선호 scalar, 0..1 제한 없음. 매출/구매율/CTR 예측 아님 |
| mock | source=mock 또는 fallback_mock, model_version=mock-v1, feature_version=null, pairwise=null 또는 생략 |
| 파일 | 기본 root artifacts/models/. 실제 env RANKING_MODEL_PATH는 모델 파일 의미 유지 |

padding 색·보간·input size·정규화·ICC 정책은 B가 학습/추론에 동일하게 고정하고 가중치와의 호환성을 검증합니다. 전체가 보이는 것만으로 작은 글자의 의미 인식이 보장되지 않습니다. A의 사진 분석과 B의 ranking CLIP은 사용 목적이 다르며 가중치·feature·전처리를 자동 공유하지 않습니다.

## Candidate JSON

[candidates.json](../tests/fixtures/contracts/candidates.json)은 네 Candidate의 예제 wrapper입니다. 각 후보는 기존 candidate_id/strategy/revision/facts/copy/png/renderer/diagnostics 필드를 유지합니다. 외부 응답에 로컬 파일 경로나 모델 경로를 넣지 않습니다. 새 RGB/opaque 필드를 중복 추가하지 않고 실제 이미지 형식을 검사합니다. fact 문자열·revision·네 ID/strategy 일치를 검증합니다.

합성 fixture의 diagnostics는 unavailable/null입니다. 예제의 renderer 정보와 source hash는 fixture 생성기의 인공 geometry/색 블록을 설명하며 실제 광고 renderer·제품 사진·가독성 측정 실적이 아닙니다. 원본 상품을 AI로 재생성하지 않습니다.

## 함수 계약

아래는 B가 구현할 인터페이스 문서이며 이번에 해당 함수를 서비스나 ml/에 구현하지 않습니다.

```python
load_model(artifact_dir: Path) -> ModelHandle
extract_features(image_path: Path, model: ModelHandle) -> FeatureVector
score_ad(image_path: Path, model: ModelHandle) -> float
rank_ads(items: list[RankInput], model: ModelHandle) -> RankOutput
```

- artifact_dir: 신뢰된 bundle 디렉터리. manifest·model·scaler/config·checksum·의존성·전처리 version을 검증합니다. 원격 URL/자동 다운로드를 허용하지 않습니다.
- ModelHandle: model_version, feature_version, preprocessing_version, encoder 식별, 입력 크기/feature 순서/차원, device·dtype와 로드된 scorer 상태를 담는 논리 타입입니다. 구체 Python 타입과 import 경로는 B 합의가 필요합니다.
- FeatureVector: B가 정의한 순서와 차원의 유한 수치 벡터. Python list/NumPy/Tensor 중 전달 타입은 B가 제안하고 A는 내부 feature를 재구현하지 않습니다.
- score_ad: 같은 feature/scaler/scorer로 단일 이미지의 float score를 반환합니다. sigmoid 변환을 강제하지 않습니다.
- RankInput: candidate_id:string, rendered_image_path:Path. A가 허용 root/session/revision을 검증한 최종 RGB PNG의 내부 절대 경로만 전달합니다. strategy를 실제 모델 feature로 넘기지 않습니다.
- rank_ads: 네 장을 batch 처리하는 경계입니다. 구현은 내부 batch extraction을 사용할 수 있고 단일 함수를 네 번 호출하도록 강제하지 않습니다. source/revision/warnings는 A adapter 책임입니다.
- RankOutput: model_version, feature_version, items[4], 선택적 pairwise. items의 candidate_id는 **입력과 같은 순서**이고 각 item은 candidate_id/score/rank입니다. [B 응답 예제](../tests/fixtures/contracts/rank-output.model.json)를 참고합니다.

rank는 score 내림차순, 동점은 candidate_id 사전순으로 1..4를 유일하게 부여합니다. 동점에 실제 선호 차이가 있다는 의미를 붙이지 않습니다. 서비스 Ranking.items와 기존 화면 후보는 rank 순 표시를 유지하며 A가 복사본을 정렬하고 ID로 연결합니다. B 입력/출력 배열을 표시 순서로 덮어쓰지 않습니다.

## Ranking JSON과 선택적 pairwise

[ranking.model.json](../tests/fixtures/contracts/ranking.model.json)은 실제 모델 실행이 아닌 **합성 계약 예제**입니다. top-level model_version/feature_version은 네 후보 모두에 적용됩니다. 후보별로 다른 model version을 섞지 않습니다. [mock](../tests/fixtures/contracts/ranking.mock.json)과 [fallback](../tests/fixtures/contracts/ranking.fallback.json)은 확률을 제공하지 않습니다.

pairwise는 null/생략 가능하며 제공 시 다음 형식입니다.

```text
pairwise = {
 method: "bradley_terry_sigmoid_v1",
 comparisons: [
   {candidate_a_id, candidate_b_id, probability_a_preferred}, ... 6개
 ]
}
```

- 네 ID를 사전순으로 정렬한 뒤 a<b인 unordered pair 6개를 한 번씩 제공합니다. self/unknown/중복/역방향 중복을 거부합니다.
- probability_a_preferred는 **A가 B보다 선호될 모델 상대 비교 값**이며 유한한 0..1입니다. 반대 방향은 1-p, 동점은 0.5입니다.
- 이 method의 계산은 sigmoid(score_A-score_B), temperature=1이며 예제 검증 허용 오차는 절대 1e-6입니다. 안정적인 sigmoid 계산으로 overflow를 피합니다.
- 검증된 보정 확률·구매 확률·CTR·매출 예측·실측 소비자 선호로 표현하지 않습니다. 다른 방법/temperature/calibration을 도입하면 method/schema version과 합의를 갱신합니다. 임의의 확률을 기존 method로 위장하지 않습니다.
- MockRanker는 pairwise를 생성하지 않습니다. 전체 모델 실패 시 네 후보 모두 mock fallback으로 전환하고 모델 확률도 제거합니다.

HTTP schema의 additive pairwise 확장은 이번 사용자 승인에 따른 문서/fixture 계약입니다. 현재 실제 광고/ranking endpoint는 없으므로 런타임 API가 바뀐 것은 아닙니다. 과거 unknown field 거부 규칙에 따라 소비자는 v1.1을 함께 적용해야 합니다.

## 모델 파일과 loader의 호환 방안

RANKING_MODEL_PATH는 PR #14의 **파일** 의미를 유지합니다. 이를 directory로 조용히 바꾸지 않습니다. 제안 배치:

```text
artifacts/models/ranking/<version>/
  manifest.json
  model.<B가 합의한 형식>
  scaler/config 등
```

향후 A adapter가 env 파일 경로를 검증한 뒤 부모 directory를 load_model에 넘기는 방안을 제안합니다. manifest가 명시한 model 파일과 env의 파일이 정확히 일치해야 하며 폴더에서 임의 파일을 선택하지 않습니다. **manifest 실제 schema·모델 파일명·safe loader·예외 import 경로는 B 합의 전**입니다. PR #14를 이 브랜치에서 중복 구현하지 않습니다.

## 오류와 독립 개발

누락/손상 artifact, checksum/version/feature 차원 불일치, invalid PNG, inference 오류·timeout을 구분하는 기존 예외 이름은 B 합의 전입니다. timeout·process 격리·취소·메모리 제한은 배포 측정 후 결정합니다. 사용자 응답에 stack/path/비밀을 노출하지 않습니다. 네 후보 자체가 없거나 렌더링이 실패한 경우 mock으로 성공을 위장하지 않습니다.

실제 모델이 없어도 A는 fixture와 mock 응답으로 소비자 계약 검증을 계속할 수 있습니다. **현재 MockRanker 구현·광고 전체 흐름은 없습니다.** 이번 예제는 엔진 구현이나 E2E 서비스 완료가 아닙니다. S5c/S6 mock 서비스와 B6 이후 S8 실제 adapter를 별도 단계로 유지합니다.

## 예제/검증 실행

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration -q
.\.venv\Scripts\python.exe -m pytest
# fixture 재생성 (기존 합성 fixture를 의도적으로 갱신하므로 diff 리뷰 필요)
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe scripts/service_generate_contract_fixtures.py
```

tests/fixtures/ads/에는 사용자 자료가 아닌 소형 합성 RGB PNG 네 장만 commit합니다. tests/fixtures/contracts/에는 CandidateSet, 서비스 Ranking, B RankOutput JSON과 각 JSON Schema를 둡니다. tests/integration/contract_models.py는 **계약 명세 전용** Pydantic 모델이며 실제 app schema/adapter가 아닙니다. JSON Schema는 shape를 표현하고 ID/순서/수식/사실 동일성은 Pydantic의 semantic validator로 추가 검사합니다. schema export와 예제의 drift도 검사합니다.
