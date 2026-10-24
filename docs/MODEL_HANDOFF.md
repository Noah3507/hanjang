# A/B 병렬 개발과 모델 전달 계약 점검

2026-10-12 점검. 문서·인터페이스 검토 결과이며 실행 가능한 추론 코드나 신규 API를 추가하지 않습니다. 기준은 [API_CONTRACT](API_CONTRACT.md), [DEVELOPMENT_PLAN](DEVELOPMENT_PLAN.md), [ROLE_SPLIT](ROLE_SPLIT.md)입니다.

## 구현 상태와 계약의 확정 수준

기본 서비스·상품 입력·원본 업로드·draft와 사진 전처리·비교·선택이 구현됐습니다. PR #11과 #14가 main에 병합되어 photo/ranking 설정이 함께 존재합니다. MockRanker, 네 광고 생성, 편집·PNG 다운로드, RealRanker와 B 추론 코드는 없습니다. 기존 문서에 적힌 모델 signature·예시 점수를 구현 완료로 해석하지 않으며 v1.1 승인 항목과 B 세부 합의 항목을 구분합니다.

| 항목 | 구분 | 적용 방식 |
| --- | --- | --- |
| 원본 사진·가게명/상품명/가격 보존 | 사용자 확정 | B 입력도 사용자 원본을 생성형 AI로 변경하지 않음 |
| 전략 4종 emotional/price/visual/brand | 사용자 확정 | 네 후보 식별 유지 |
| 모델 없이 MockRanker로 서비스 동작 | 사용자 확정 목표 | S5c/S6에서 구현·검증할 것; 현재 미구현 |
| preference는 상대 선호, 매출/구매율/CTR 예측 아님 | 확정 불변 규칙 | UI와 모델 보고서에 적용 |
| load/extract/score/rank 공개 함수 | v1.1 논리 입출력 승인 | 구체 Python 타입·모듈 경로는 공동 합의 필요 |
| 최종 RGB PNG 경로, version·ID·finite score, batch/순서·동점·선택적 pairwise | v1.1 승인 | fixture는 검증하며 실제 소비자/adapter 구현은 후속 |
| 고정 mock 점수·예외 클래스 | 기존 제안 | mock fixture 점수를 실제 성능으로 표시하지 않음 |
| 정규화·padding 색·device·timeout·bundle 상세 | 미확정 | 비율 유지 padding과 artifacts/models/ root는 확정, 나머지 공동 결정 |

## B 추론 함수 초안: 기존 API를 유지

```python
# 문서용 signature이며 실행 코드가 아닙니다.
load_model(artifact_dir: Path) -> ModelHandle
extract_features(image_path: Path, model: ModelHandle) -> FeatureVector
score_ad(image_path: Path, model: ModelHandle) -> float
rank_ads(items: list[RankInput], model: ModelHandle) -> RankOutput
# RankInput: candidate_id: str, rendered_image_path: Path
# RankOutput: model_version: str, feature_version: str,
#             items: list[{candidate_id: str, score: float, rank: int}], pairwise?: Pairwise | None
# items preserve batch input order; HTTP display order is derived separately.
```

A는 `rank_ads` 경계만 소비하고 B feature 코드를 복제하지 않는 초안입니다. `ModelHandle`/`FeatureVector`의 구체 타입, package import 경로, dataclass/Pydantic/dict 선택은 아직 확정하지 않습니다. 기존 HTTP 스키마는 변경하지 않습니다.

입력은 **상품 사진 단독이 아닌 최종 렌더링 광고 PNG 네 장**과 유일한 candidate ID입니다. A가 session 소유권·revision·허용 root 아래의 절대 경로를 검증한 뒤 내부에서 전달합니다. 외부 응답에는 파일 경로를 넣지 않습니다. B가 원격 URL을 다운로드하거나 사용자 임의 경로를 열지 않는 설계입니다. 분위기·strategy·사용자 입력 사실을 모델 feature로 전달하는 새 필드를 추가하지 않습니다. 실제 strategy feature 제외는 기존 설계 경계입니다.

출력은 같은 model/feature version으로 산출한 네 ID의 유한 scalar score와 rank 1–4입니다. score의 0–1 범위나 확률 의미를 가정하지 않습니다. ID로 결합하며 입력 배열 위치로 연결하지 않습니다. version이 다른 결과를 직접 비교하지 않습니다. B 출력에는 service의 `source`, `revision`, `warnings`를 요구하지 않고 A adapter가 서비스 Ranking 응답에 붙이는 초안을 유지합니다. 다른 revision의 점수를 재사용하지 않습니다.

## 전처리: B 책임과 공동 합의

B가 학습과 추론에 동일한 decode·색 공간·resize/crop·normalization·통계 계산·feature 순서·scaler를 소유합니다. A의 상품 배경 제거/사진 분석과 B의 추론 전처리는 별개입니다. B 전처리는 모델 입력 tensor를 위한 내부 연산이며 보존 원본과 렌더링 결과 파일을 덮어쓰지 않습니다.

합의할 전처리 manifest 항목:

- PNG decode와 RGB 변환, 투명 alpha의 합성 색, ICC/EXIF 적용 여부
- 입력 크기, interpolation, 비율 유지·crop/padding 방식; 광고 텍스트가 잘리는 조건
- CLIP 구현·정확한 encoder/가중치 식별, normalization, 통계 feature 정의·순서
- scaler 학습 범위·전달 형태, preprocessing version, CPU/GPU·dtype·seed와 허용 수치 오차
- 손상 파일·크기 제한·예상 밖 채널의 거부 조건

2026-10-24 사용자 승인으로 open_clip_torch와 전체 광고 비율 유지 padding을 적용합니다. encoder와 feature 차원은 확정하지 않으며 가중치 호환성 검증 후 결정합니다. B가 네 개의 권한 확인된 샘플 광고로 독립 smoke를 제공하고 A가 같은 fixture로 연결을 검증합니다.

## 오류와 fallback

기존 예외 이름 `ModelNotAvailable`, `ArtifactMismatch`, `InvalidImage`, `InferenceFailure`는 제안입니다. B가 발생 조건과 import 가능한 예외 계약을 제시하고 A와 합의합니다. timeout 초·실행 격리·취소 방식과 메모리 제한도 미확정이며 동기 호출에 timeout 숫자만 붙여 실제 작업이 중단된다고 가정하지 않습니다.

A는 ID 누락/중복/추가, NaN/Infinity, 잘못된 rank/version을 검증하는 설계입니다. 실제 모델 실패 시 일부 모델 점수와 mock을 혼합하지 않고 **네 후보 전체**를 `fallback_mock`으로 전환하며 경고를 표시합니다. 정상 mock은 `source=mock`, 실제 모델은 `source=model`입니다. mock은 model_version=mock-v1, feature_version=null 초안을 유지합니다. stack trace·절대 경로·비밀은 사용자 응답이나 공유 로그에 노출하지 않습니다. 입력 PNG 자체가 잘못됐거나 네 후보가 없으면 mock으로 성공을 위장하지 않고 렌더링/입력 오류를 처리합니다.

## 모델 파일 전달

B가 신뢰할 수 있는 경로로 artifact를 전달하고 A가 확인 후 load합니다. 사용자용 모델 업로드 API는 만들지 않습니다. 전달 매체·저장 위치·보관 권한은 공동 합의하며 `artifacts/models/`는 사용자 확정 기본 경로입니다. 원본 데이터·가중치·캐시는 GitHub 소스 저장소에 올리지 않습니다.

전달 묶음에는 model·scaler/config, 비밀 없는 manifest(파일 목록·checksum·model/feature/preprocessing version), 의존성 pin/lock·Python/device 조건, feature 순서, model card·평가 조건, 독립 smoke 명령과 예상 출력/허용 오차가 필요합니다. 파일 형식·manifest 실제 schema는 합의 전 제안입니다. A가 알 수 없는 출처의 pickle 등을 임의 load하지 않고 B 제공 형식·버전·checksum을 확인합니다. 누락/불일치/권한 실패의 재현 결과를 B에게 보고하며 A가 모델 내용을 수정하지 않습니다.

## A가 B를 기다리지 않는 구현 순서

기존 S5c→S6→S8 의존관계를 변경하지 않습니다.

1. S1 남은 네 후보 fixture와 공용 타입을 리뷰합니다. 합성 fixture의 facts가 동일하고 네 전략/ID가 완전한지 검증합니다.
2. S5c에서 A 소유 MockRanker를 구현합니다. 기존 제안값 visual=0.8/emotional=0.6/price=0.4/brand=0.2는 UI 시험용이며 mock 표시·finite/ID·정렬을 테스트합니다. 모델 라이브러리를 import하지 않는 독립 경계를 만듭니다.
3. S5a는 fake copy/context, S5b는 고정 copy fixture로 독립 개발합니다. fake provider와 mock ranker 설정·표시를 분리합니다. 실제 API 연결 성공과 혼동하지 않습니다.
4. S6에서 실제 업로드→네 후보→mock 순위→문구 수정→전체 재정렬→PNG 다운로드를 통합합니다. facts/원본 hash 보존, 수정 revision, 예외, 브라우저 Console과 실제 PNG를 E2E 검증합니다. 유료 LLM 연결 시험은 별도 승인합니다.
5. B6 artifact와 함수 계약·독립 smoke가 준비된 뒤 **별도 S8 PR**로 RealRanker를 연결합니다. 실패/timeout/잘못된 출력의 전체 mock fallback과 동일 UI schema를 검증합니다.

현재 S3 사진 전처리·비교·선택은 구현됐으나 S4–S6는 미구현입니다. 이번 계약 테스트로 전체 광고 흐름이 가능해지지는 않습니다. MockRanker 단독 구현도 전체 서비스 완료가 아닙니다. 모델 성능 평가는 B7의 별도 완료 조건입니다.

## 충돌 최소화와 공동 리뷰

| 담당 | 독립 수정 영역 | 경계 |
| --- | --- | --- |
| A | frontend, backend API/services, templates, service tests | 서비스·렌더링·mock·오류 UX |
| A 통합 | backend/app/ml_adapter | B 함수를 호출; feature/학습 재구현 금지 |
| B | ml/data/features/training/evaluation/inference, scripts/ml_*, tests/ml | 데이터·학습·평가·추론; A가 수정하지 않음 |
| 공동 | schemas, API 계약, integration fixture, docs, 의존성·CI | 한 변경의 담당자를 정하고 PR로 상대방 검토 |

서비스와 모델 가상환경·의존성은 분리합니다. 각자 feature 브랜치를 사용하고 공용 파일 동시 변경 전 범위/담당을 합의합니다. 공동 fixture의 위치·소유자도 먼저 합의합니다. 정상 merge로 변경을 보존하고 force push·main 직접 push·자동 merge를 금지합니다. 모델 artifact를 Git 소스 인계 수단으로 사용하지 않습니다.

## 충돌·미확정 사항 보고

| 발견 사항 | 처리 |
| --- | --- |
| S1 네 후보 fixture 미완료인데 S5c가 이를 의존 | fixture 리뷰를 S5c 선행 작업으로 유지; 완료 주장 금지 |
| 전체 흐름 준비 요청과 현재 S3–S6 미구현 사이 차이 | 이번은 점검/계획; 구현은 각 기능 PR로 진행 |
| 예외 구현·bundle manifest 등 세부사항은 아직 제안 | v1.1 논리 계약과 구분하고 B 합의 후 구현 |
| 개발 계획 S9에 S8 의존이 있으나 말미에는 실제 모델 unavailable 시 서비스 완료 유지라고 기재 | mock 서비스 MVP(S6/S7)와 실제 모델 통합 demo(S8/S9)의 완료 경계가 다소 모호함. 계획 의존관계는 변경하지 않고 A/B·사용자 리뷰에 남김 |
| 과거 온보딩의 PR #8 미병합 안내 | 현재 병합 완료이므로 B가 최신 main에서 업로드 기능을 받을 수 있음 |

공동 리뷰 완료 후 결정사항을 API_CONTRACT와 재현 fixture에 함께 반영합니다. 원본 일정 날짜는 목표이며 자동으로 완료된 것으로 처리하지 않습니다.

## 2026-10-24 데이터 및 경로 정책

[MODEL_STORAGE_AND_DATASET](MODEL_STORAGE_AND_DATASET.md)의 확인/미확인 표와 artifacts/models/ 및 RANKING_MODEL_PATH 정책을 적용합니다. 원본 라이선스와 동일성은 미검증입니다. 기존 B 코드와 파일은 변경하지 않으며 loader의 file/directory 경계는 공동 합의 사항입니다.

## v1.1 승인으로 대체되는 초안

[RANKING_CONTRACT_V1_1](RANKING_CONTRACT_V1_1.md)이 최종 광고 RGB 1080×1350, padding, batch/ID/순서, version, 선택적 pairwise의 기준입니다. 이 문서 상단의 과거 미확정 표는 해당 항목에 한해 최신 승인으로 대체됩니다. RANKING_MODEL_PATH 파일 의미는 PR #14와 동일하게 유지하며 directory loader 연결은 B와 세부 합의합니다. ViT-L/14·768은 기본값으로 확정하지 않습니다.
