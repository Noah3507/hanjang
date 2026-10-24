# PR #14 최신 main 통합 기록

2026-10-24. PR #11 병합 commit `7312bff`를 chore/model-storage-policy에 정상 merge했습니다. 기존 기록을 rebase/amend하거나 force push하지 않습니다. PR #14의 main 병합은 사용자 승인 전 수행하지 않습니다. PR #15와 B PR #13은 수정하지 않았으며 6단계 이미지 분석은 시작하지 않았습니다.

## 충돌 해결

| 파일 | 보존한 내용 |
| --- | --- |
| .env.example | HANJANG_PHOTO_MODEL_PATH/TIMEOUT_SECONDS/MAX_SIDE 안내와 별도 RANKING_MODEL_PATH 모두 유지 |
| backend/app/config.py | 원래 photo 필드·제한값과 ranking 파일 alias/상대 root 해석을 함께 유지 |
| README.md | S3 전처리/원본 fallback 실행 안내와 모델 저장/데이터 후보 정책 모두 유지 |
| docs/DEVELOPMENT_PLAN.md | S3 구현 범위·후속 미구현 경계와 모델 경로/권리 미확인 안내 모두 유지 |
| docs/TECH_SPEC.md | 전처리 기술/원본 보존 정책과 별도 ranking 설정 정책 모두 유지 |

자동 통합된 API_CONTRACT.md에도 사진 처리 계약 링크와 모델 정책 링크가 모두 남아 있습니다. artifacts/models/ 기본 root, 원본 데이터 동일성/라이선스/이용 권한 미확인, RANKING_MODEL_PATH의 선택적 파일 의미를 유지합니다. 기존 모델이나 사용자 파일은 이동·삭제하지 않습니다.

## 검증

- backend pytest: 57 passed(3.83초), pip check 통과. 기존 AnyIO alias deprecation 경고 1건.
- 새 회귀 검사: photo 환경변수와 RANKING_MODEL_PATH를 동시에 지정해 경로·timeout·최대변 값·서버 기동 확인.
- frontend TypeScript·Vitest 14개·Vite build 통과.
- 최신 main과 frontend·photo API/services/schemas·app startup·backend requirements의 diff 없음. 이미지 전처리 구현과 의존성을 그대로 보존.
- 충돌 marker·문서 링크·공백·Git index 비밀 검사 수행. 모델/업로드/실제 env를 stage하지 않음.
- 화면/사진 처리 코드는 main과 동일하므로 로컬 브라우저를 반복 실행하지 않습니다. PR 전체 CI의 browser-e2e를 별도로 확인합니다. 기존 사용자 서버·브라우저는 변경하거나 종료하지 않습니다.

GitHub에서는 최신 merge commit의 backend/frontend/repository-policy/browser-e2e와 충돌 상태를 확인한 뒤 PR #14를 리뷰해야 합니다. CI 성공은 사용자 병합 승인을 대신하지 않습니다. 실제 ranking/MockRanker 엔진·모델 학습·이미지 분석은 추가하지 않습니다.
