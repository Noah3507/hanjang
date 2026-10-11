# A와 B 역할 및 파일 소유권 초안

근거: R1–5·7–11, P19. A는 Service & Integration Engineer, B는 Preference Model & Evaluation Engineer입니다. 현재 개발자 A 작업이며 B 계정 초대는 추후 진행합니다. CODEOWNERS 같은 강제 설정은 아직 없습니다.

자료 충돌 시 최종 발표본을 우선합니다. 사용자 확정 우선순위는 업로드→AI 광고 4종→선호 순위→문구 수정→PNG입니다. A4는 이후 OPTIONAL이며 A/B 최종 필수 완료 조건에서 제외합니다. 원본 보존·색 보정 보류·원본 fallback, 단일 서버·비공개 24시간 저장·Job Polling은 A의 서비스 책임입니다.

## 독립 책임과 산출물

| 구분 | A 서비스·통합 | B 모델·데이터·평가 |
| --- | --- | --- |
| 최종 책임 | 사용자 입력→광고 4개→수정→저장 흐름 | 재현 가능한 학습·평가와 새 광고 scoring |
| 구현 | React UI, FastAPI, 업로드, rembg/사진 분석, LLM copy, templates/Playwright, readability, adapter, 배포 | 데이터 접근·pair·split, frozen CLIP cache·통계, shared scorer, baseline·metric, inference package |
| 산출물 | 실행 가능한 web MVP·API·PNG·진단·mock/real 통합. A4는 PNG MVP 이후 선택 산출물 | model/scaler/config·feature spec·checksum·model card·평가 report·inference surface |
| 금지 경계 | B 학습·평가·split·label·feature 코드를 수정하지 않음 | A React·renderer를 직접 수정하거나 서비스 계약을 일방 변경하지 않음 |

## 소유 파일 계획

| 경로 | 소유 | 수정 절차 |
| --- | --- | --- |
| frontend/** | A | UI/API client/type 소비 |
| backend/app/api/**, backend/app/services/** | A | service tests와 함께 변경 |
| templates/**, scripts/service_*, tests/service/** | A | 사진·한글·레이아웃 QA |
| backend/app/ml_adapter/** | A | 내부 구현 A, public interface 공동 합의 |
| ml/data/**, ml/features/**, ml/training/**, ml/evaluation/**, ml/inference/** | B | A는 읽기·문제 보고만, 수정 금지 |
| scripts/ml_*, tests/ml/** | B | 재현 config와 검증 유지 |
| backend/app/schemas/**, frontend 생성 API 타입 | 공동 계약/A 구현 | OpenAPI 변경·호환성·version A/B 승인 |
| tests/integration/**, docs/**, 루트 의존성·CI·설정 | 공동 | 상대 트랙 영향 확인 |
| /data/**, /artifacts/models/**, /weights/**, /uploads/** | Git 제외 런타임 | private 외부 저장, manifest/checksum만 commit |

경로는 계획이며 이번에 코드 폴더를 만들지 않습니다. 원본의 backend/models artifact 경로와 초기 ignore의 models/·data/ 충돌을 해결하려고 artifacts/models를 제안합니다(D18). 확정 전에 B 경로를 옮기지 않습니다.

## 접점 제공과 고정 시점

| 시점 | A가 제공 | B가 제공 | 공동 게이트 |
| --- | --- | --- | --- |
| Week 5 | candidate/HTTP 초안, MockRanker 계약 | 필요 feature와 sample 입력 조건 | ID·이미지·ranking input 합의 |
| Week 6 | 실제 PNG 20–40장, renderer metadata | feature smoke와 score output spec | candidate_id/score/rank/model_version 확정 |
| Week 7 | loader·failure·local smoke adapter | frozen v1 artifact, dependencies·feature version·exception | 실패·timeout·tie·checksum 계약 |
| Week 8 | real UI 연결·10개 이상 E2E | 최종 test 결과·95% CI·model card | 모델 version freeze·통합 검증 |

A는 MockRanker로 B를 기다리지 않고, B는 sample ad folder로 renderer를 기다리지 않습니다. A의 photo analysis CLIP과 B ranking CLIP feature는 용도가 다르며 전처리를 공용이라고 가정하지 않습니다.

## 공동 의사결정

- API/schema 변경·version·breaking change·fallback 표시를 합의합니다.
- 네 전략 geometry가 충분히 다른지 함께 리뷰합니다.
- preference 표시를 구매율·매출·CTR 예측으로 쓰지 않습니다.
- D01 A4 선택·필수 제외, D04 원본/사진 처리 경계, D07–08 초기 운영은 사용자 승인 완료입니다. D09 입력 제한·D10 외부 API 비용 등 남은 제안만 구현 전 합의합니다.
- 5–10명 owner interview와 Week 9 user test, 선택 food test의 동의·설문·검수·최종 E2E/데모 리허설은 공동입니다.
- B는 학습·평가 절차와 validation 근거로 Logistic/MLP를 선택합니다. A가 원하는 demo 점수에 맞춰 split·metric을 바꾸지 않습니다.

사용자가 담당 범위를 명시해 새 작업을 요청하기 전에는 Codex가 상대 소유 영역을 수정하지 않습니다. 공용 파일 변경을 알리는 것은 계획 규칙이며 외부 Slack·email 전송 권한을 뜻하지 않습니다.
