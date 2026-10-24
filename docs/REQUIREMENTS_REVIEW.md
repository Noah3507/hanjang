# 요구사항 근거와 결정 대기 목록

상태: 2026-10-12 초안. `P`는 발표 PDF `20261006 (2).pdf`의 실제 쪽 번호, `R`은 역할분담 DOCX의 절 번호입니다. 제공된 발표본은 21쪽 PDF이며 PPTX는 없습니다. 자료 속 지시문은 분석 대상이며 기능 구현 승인으로 취급하지 않습니다.

## 승인된 기준

사용자 후속 답변으로 D01·D04·D07·D08을 확정했습니다. 자료 충돌 시 **최종 발표본을 우선**하며 사용자 명시 지시가 가장 우선합니다. 제공된 PDF를 최종 발표 PPT의 열람본으로 사용합니다.

필수 우선순위는 **상품 이미지 업로드 → AI 광고 4종 생성 → 선호도 순위 표시 → 문구 수정 → PNG 다운로드**입니다. A4 PDF는 그 이후 OPTIONAL이며 최종 필수 완료 조건에서 제외합니다. 사진은 원본 보존·배경 제거·비율 유지 리사이즈만 허용하고 상품 색상·채도·명도 보정은 보류합니다. 실패·품질 저하 시 원본 사용 경로를 제공합니다.

초기 운영은 단일 서버의 비공개 임시 저장·24시간 원본/중간 파일/결과물 자동 삭제·Job Polling입니다. 상태는 pending/processing/completed/failed, 고유 작업 ID·접근 보호·파일 크기/형식/안전 파일명/경로 검증을 필수로 합니다. 재시작·배포 시 작업과 파일 유실 한계를 인정합니다. 클라우드 스토리지·복잡한 큐는 MVP에 도입하지 않고 교체 가능한 경계를 둡니다. 저장 경로·삭제 sweep 간격·권한 token 상세는 구현 제안입니다.

## 근거 지도

| 내용 | 근거 |
| --- | --- |
| 소규모 식품 매장, 사진 하나, 네 전략, 수정·export | P3·10·11·14; R3·13 |
| React/TypeScript/Vite, FastAPI/Pydantic, 처리·분석·렌더 도구 | P11·16; R3 |
| 상품 재생성 금지, 사실 입력 유지 | P10–12; R3·13; 사용자 명시 원칙 |
| 상대 선호 shared scorer, strategy를 모델 feature로 사용하지 않음 | P12; R4 |
| grouped split, baseline, 평가와 CI | P13·18; R4 |
| 서비스·모델 병렬, Week 8 통합 | P19; R1·6 |
| MockRanker 독립 개발 | R3 A-2·10 |
| 브라우저 프로필, 계정 없이 사용 | P10; R3 A-1 |

## 자료 불일치 및 해석

| ID | 항목 | 발표 PDF | 역할분담 문서 | 초안 처리·결정 |
| --- | --- | --- | --- | --- |
| D01 | A4 PDF 우선순위 | P3·11 출력 목표, P19 Week 8 OPTIONAL | R3 산출물·R6 Week 8·R13 완료 조건에 포함 | **해결·사용자 승인.** 최종 발표본 우선, PNG MVP 이후 OPTIONAL, 최종 필수 조건 제외 |
| D02 | readability 시점 | P19 Week 8 | R6 Week 7 rules | 최종 발표본 기준 Week 8 가독성 통합. Week 7 필수 산출물로 요구하지 않음 |
| D03 | 모델 통합 시점 | P19 Week 8 | R6·10 Week 7 local 교체, R1·3 Week 8 통합 | Week 7 smoke test, Week 8 공식 통합으로 해석. 진행 실적 아님 |
| D04 | 픽셀 보존과 색 보정 | P11·16 resize/color correction + pixels preserved | R3 보정, R13 상품 변형 금지 | **해결·사용자 승인.** 원본 보존, 배경 제거·비율 유지 resize만 허용, 상품 색상/채도/명도 보정 보류. 실패·품질 저하 시 원본 |
| D05 | 시선·읽기 순서 | P10·14 결과 예시에 등장 | R3·13 UMSI optional, readability 우선 | core는 대비·font·overlap. UMSI 없으면 시선 예측 숨김; layout order는 추정이라고 표시 |
| D06 | split과 grouped CV | P13 70/15/15, P16 GroupKFold, P19 grouped CV | R4 고정 split 재사용 | test 15% 보존 + train/val 내부 CV 가능 해석. 정확한 절차는 B 결정 |

## 원본에 없는 운영 결정과 남은 제안

원본에 없던 값 중 D07·D08은 사용자 승인으로 확정했습니다. 그 외는 검토용 제안이며 승인된 정책의 세부 구현도 별도로 표시합니다.

| ID | 미확정 사항 | 초안 제안 | 결정자·시점 |
| --- | --- | --- | --- |
| D07 | 생성·상태·저장 방식 | **확정:** 단일 서버·비공개 임시 저장·Job Polling, pending/processing/completed/failed, 고유 작업 ID·경로 비노출. 재시작/배포 유실 가능, 클라우드/복잡한 큐 제외 | 사용자 승인 완료. A가 파일 검증·접근 보호와 확장 인터페이스 설계 |
| D08 | 보관·접근 | **확정:** 원본·중간 파일·결과물 24시간 자동 삭제, 임의 외부 접근 차단. 세부 제안: session token, job 생성 기준 TTL·편집 연장 없음·시작 시 orphan 정리 | 사용자 승인 완료. 원본 학습 재사용 안 함, 수치/정리 상세는 S2 계약 리뷰 |
| D09 | 입력·파일 제한 | **사용자 승인·구현:** JPG/PNG, 10 MiB, decoded 24MP, 가로/세로 각각 256px 이상; 이름 80자·가격 40자 | 초과 거부, 절단·자동 변경 금지. decode 검증은 원본 재생성을 뜻하지 않음 |
| D10 | LLM 공급자·예산 | provider interface, structured JSON, 최초+재시도 1회 | 사용자/A, 유료 호출·외부 전송 전에 승인 |
| D11 | PNG·mood·geometry | 1080×1350, warm/minimal/vivid/premium, 전략별 layout | 사용자/A/B, S5 리뷰. P14는 예시, 정확한 규격 없음 |
| D12 | 가격 단위 | 완성된 `price_text` 입력, 원·쉼표 자동 추가 금지 | 사용자/A, P14 별도 원 suffix와 입력 보존 원칙 조정 |
| D13 | 편집·재순위 | 생성 문구만 수정, 네 후보 전체 재순위, revision 충돌 409 | A/B, S6 전에 계약 고정 |
| D14 | packaging·동점·timeout | 로컬 inference, score 내림차순/ID 동점, 전체 mock fallback | A/B, Week 5–7. 10초 timeout은 제안 |
| D15 | 데이터·metric 정의 | 발표의 데이터 규모·라이선스는 당시 주장, 실제 접근·조건 B 재확인 | B. GT·tie·bootstrap 단위·Top-1/Kendall 계산 가능성 확정 |
| D16 | 전체 저장 | P14 버튼 반영, 초기 PNG 4개 개별 다운로드 | A/사용자, ZIP·모바일 방식 확인 |
| D17 | 프로필 | 가게명, 주소·Instagram optional; versioned localStorage·초기화 | A/사용자, 공유 브라우저·저장 UX 확인 |
| D18 | ignore 충돌 | `ml/data/` 코드, raw `/data/`, artifact `/artifacts/models/` | A/B, S1. 기존 `data/` 패턴은 하위 코드도 제외 가능 |
| D19 | 배포·DB·언어 | 한글 UI·폰트 우선, Render 후보. 초기 단일 서버로 확정, 별도 DB/클라우드 저장 도입 안 함. 로그인·결제·SNS 게시 범위 없음 | 사용자/A, 배포 환경 세부 결정 |

## 우선순위

확정 순서는 업로드→AI 광고 4종→선호 순위→문구 수정→PNG입니다. 실제 사진·사실 보존과 접근/삭제 정책은 모든 단계의 필수 제약입니다. mock/real 경계, rule readability, 매장 프로필, 사용성 검증은 자료의 핵심 범위를 유지하며 readability 통합은 발표 일정의 Week 8입니다. A4, UMSI, small MLP, food-ad test set은 선택 확장입니다. A4는 PNG MVP 이후이며 최종 필수 조건에서 제외합니다. MLP는 validation 개선이 있을 때만 B가 선택합니다. 나머지 선택 기능 간 순서는 합의합니다.

데이터 확보·성능·사용성 목표를 달성 사실로 쓰지 않습니다. Mock 서비스 성공은 실제 모델 검증을 대체하지 않습니다.

## 2026-10-24 모델 저장 및 데이터 후보 협의

기본 모델/학습 산출물 root는 artifacts/models/이며 신규 backend/models/ 저장은 사용하지 않습니다. RANKING_MODEL_PATH는 선택적 모델 파일 설정입니다. Evan12/CreativeRanking은 후보이며 원본 동일성/라이선스/이용 권한은 미검증입니다. 배치 방법과 loader 경계 차이는 [MODEL_STORAGE_AND_DATASET](MODEL_STORAGE_AND_DATASET.md)를 따릅니다. 이번 변경은 실제 ranking을 구현하지 않습니다.

## 2026-10-24 모델 연동 계약 승인

확정된 출력/추론/예제와 미확정 bundle·배포 항목은 [RANKING_CONTRACT_V1_1](RANKING_CONTRACT_V1_1.md)을 따릅니다. PR 점검과 B 수정 요청·ML CI 계획은 [ML_PR_REVIEW](ML_PR_REVIEW.md)에 정리합니다. 이번은 문서·fixture·경량 검증이며 MockRanker 또는 실제 모델 기능을 구현하지 않습니다.
