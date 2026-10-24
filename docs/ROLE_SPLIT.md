# A와 B 역할 및 파일 소유권 초안

근거: R1–5·7–11, P19. A는 Service & Integration Engineer, B는 Preference Model & Evaluation Engineer입니다. 2026-10-12 기준 B(parkyeonwooo)는 write 권한 초대 수락 대기입니다. CODEOWNERS 같은 강제 설정은 아직 없습니다.

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

함수별 입력·출력·전처리·artifact·오류 합의와 A/B 수정 경계는 [MODEL_HANDOFF](MODEL_HANDOFF.md)에 정리합니다. 기존 소유권은 유지하며 B 승인 전 signature를 확정하지 않습니다.

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
- D01 A4 선택·필수 제외, D04 원본/사진 처리 경계, D07–08 초기 운영은 사용자 승인 완료입니다. D09 기본 업로드 제한은 사용자 승인 후 PR #8에 반영됐습니다. 외부 API 비용과 모델 계약 등 남은 제안은 구현 전 합의합니다.
- 5–10명 owner interview와 Week 9 user test, 선택 food test의 동의·설문·검수·최종 E2E/데모 리허설은 공동입니다.
- B는 학습·평가 절차와 validation 근거로 Logistic/MLP를 선택합니다. A가 원하는 demo 점수에 맞춰 split·metric을 바꾸지 않습니다.

사용자가 담당 범위를 명시해 새 작업을 요청하기 전에는 Codex가 상대 소유 영역을 수정하지 않습니다. 공용 파일 변경을 알리는 것은 계획 규칙이며 외부 Slack·email 전송 권한을 뜻하지 않습니다.

## 공통 Git 책임

A/B 모두 GitHub Flow를 따르고 작업 전 브랜치·변경·원격·PR을 확인합니다. 같은 작업 브랜치를 이어서 쓰고 새 기능은 feat/, fix/, refactor/, test/, docs/, chore/ 브랜치에서 작은 단위로 구현·테스트·영어 Conventional Commits로 commit합니다. develop은 만들지 않습니다. 완료 후 push·main 대상 PR 생성 또는 기존 PR 갱신을 수행합니다. PR 제목도 Conventional Commits이며 템플릿의 목적·구현·파일·테스트·Issue·화면 스크린샷·확인 사항을 기록합니다.

main 직접 commit/push, 자동 merge, force push, 타인의 변경 덮어쓰기를 금지합니다. 기존 기록을 다시 쓰지 않고 브랜치를 승인 없이 삭제하지 않습니다. 사용자의 검토와 명시적 병합 승인까지 기다립니다. API 키·실제 .env·임시 파일·개인정보는 commit하지 않습니다. main 보호는 적용 전 사용자 승인 사항입니다. 이미 완료한 Git 작업은 반복하지 않으며 [CONTRIBUTING.md](../CONTRIBUTING.md)와 [AGENTS.md](../AGENTS.md)를 따릅니다. A/B 소유권과 모델 API 계약은 변경하지 않습니다.

## B 환경 준비 현황

ml/, tests/ml/, 모델 의존성과 추론 코드는 아직 없습니다. [MODEL_DEVELOPMENT](MODEL_DEVELOPMENT.md)의 첫 환경 PR 절차를 따릅니다. A가 B 소유 코드를 생성하거나 수정하지 않습니다.

## 2026-10-24 모델 연동 계약 승인

확정된 출력/추론/예제와 미확정 bundle·배포 항목은 [RANKING_CONTRACT_V1_1](RANKING_CONTRACT_V1_1.md)을 따릅니다. PR 점검과 B 수정 요청·ML CI 계획은 [ML_PR_REVIEW](ML_PR_REVIEW.md)에 정리합니다. 이번은 문서·fixture·경량 검증이며 MockRanker 또는 실제 모델 기능을 구현하지 않습니다.
