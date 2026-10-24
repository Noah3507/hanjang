# PR #15 최신 main 통합 검증

2026-10-24. PR #14 병합 commit `21ea54e`를 docs/ranking-contract에 기록 보존 merge했습니다. main 병합이나 B PR #13 수정은 수행하지 않으며 6단계 CLIP/K-means 분석은 시작하지 않습니다.

## 충돌 해결과 보존

README.md와 docs/API_CONTRACT.md, DEVELOPMENT_PLAN.md, MODEL_DEVELOPMENT.md, MODEL_HANDOFF.md, REQUIREMENTS_REVIEW.md, ROLE_SPLIT.md, TECH_SPEC.md에서 8파일·9block 충돌을 해결했습니다.

- 사진 전처리·원본 fallback·비교/선택 API와 main의 설정/실행 안내를 보존했습니다.
- artifacts/models/ 기본 root, RANKING_MODEL_PATH의 선택적 파일 의미, 후보 데이터셋의 동일성·라이선스·권리 미확인 정책을 보존했습니다.
- v1.1 문서 계약과 선택적 pairwise 타입을 유지하고 구체 Python 타입·loader/manifest·배포 설정은 B 합의 사항으로 구분했습니다.
- API_CONTRACT의 중복 버전 문단을 정리하고 현재 photo endpoint를 구현 목록에 추가했습니다. MODEL_HANDOFF의 S3 미구현이라는 과거 상태를 바로잡았습니다.
- RANKING_CONTRACT_V1_1과 실행 명세/JSON Schema/예제의 필드·ID·순서·동점·확률·mock 규칙이 일치함을 계약 테스트로 확인했습니다.

최신 main 대비 backend/frontend/.env.example/backend requirements의 diff는 없습니다. 사진 전처리 런타임·Pillow/rembg 의존성과 모델 경로 설정을 다시 구현하거나 변경하지 않았습니다. tests/ml와 ml/도 수정하지 않았습니다.

## 실행 결과

| 검사 | 결과 |
| --- | --- |
| 전체 pytest | 95 passed(3.89s): main 서비스 57 + 계약 38 |
| 계약 별도 실행 | 38 passed(0.22s), 예제 validation·export schema drift·PNG RGB/크기 포함 |
| pip check | 통과 |
| frontend TypeScript | 통과 |
| frontend Vitest | 14 passed |
| frontend build | 통과 |
| Playwright Chrome | 14 passed, 종료 코드 0(임시 서버 정리 포함 2.7m) |

로컬 브라우저는 이번 브랜치의 임시 localhost 5176/8004에서 실행했습니다. 실제 HTTP 업로드·draft·원본 byte/문자열·모델 없는 원본 fallback과 모바일·오류 UI를 검증했습니다. 시간 초과/저장 오류 UI는 모의 응답 테스트이며 실제 모델 추론 시험과 구분합니다. 가중치·데이터 다운로드나 CLIP 실행은 하지 않았습니다.

Windows에서 14개 assertion 완료 후 Playwright 임시 webServer 종료가 지연됐습니다. 이번 실행이 소유한 5176/8004 프로세스 트리만 확인해 정리한 뒤 reporter의 최종 14 passed와 정상 종료를 확인했습니다. 기존 사용자 서버·개인 브라우저는 변경/종료하지 않았습니다. 결과는 이 worktree의 artifacts/playwright/report/index.html 및 results/에 Git 제외로 남습니다.

기존 AnyIO alias deprecation 경고 1건이 있습니다. 문서 링크·공백·충돌 marker·index 비밀 검사를 수행하고 merge commit을 push한 뒤 GitHub Actions backend/frontend/repository-policy/browser-e2e와 병합 상태를 확인합니다. 자동 검증 성공은 사용자 병합 승인을 대신하지 않습니다.

## 남은 위험

실제 모델/MockRanker 엔진·광고 생성과 모델 성능·padding 품질·CPU 메모리는 이번 검증 대상이 아닙니다. 상품 마스크의 손상 가능성·재시작 metadata 유실 등 main의 기존 한계는 유지됩니다. B의 구현 타입·manifest·예외·encoder/가중치·배포 자원은 별도 합의/검증이 필요합니다.
