# PR #11 병합 전 재검증

2026-10-24, feat/service-image-processing. 검증 대상 기능 head는 5e4e1e6이며 이 보고서 외 런타임 수정은 필요하지 않았습니다. PR #14/#15/#13은 변경하거나 병합하지 않았습니다.

## 판정

자동 검증 범위에서 병합을 막는 결함은 발견하지 못했습니다. 사용자 수동 사진 품질 검토와 최신 CI 확인 후 **승인 시 병합 가능한 상태**입니다. 이번 작업은 병합 승인이 아니며 main에 병합하지 않습니다.

## 상태와 호환성

PR은 OPEN, GitHub mergeable=MERGEABLE/mergeStateStatus=CLEAN을 확인했습니다. 기존 변경 33파일은 photo backend·비교 UI·테스트·CPU 의존성·문서/env example·합성 screenshot CI 보관 범위입니다. main의 이후 변경은 문서이며 PR 분기 기준부터 최신 main까지 backend/frontend/tests/service의 추가 변경이 없음을 diff로 확인했습니다.

업로드 Facts/InputDraft 스키마와 기존 업로드 테스트 파일은 변경하지 않았습니다. 기존 입력·JPEG/PNG 업로드·원본 byte/hash·문자열/공백·draft 재조회·session 소유권·CORS·만료 검사가 회귀 테스트에 포함됩니다. 광고 생성 endpoint와 B 코드는 추가하지 않습니다.

## 실행 결과

| 검증 | 결과 |
| --- | --- |
| pytest | 51 passed (4.66s), 기존 AnyIO alias deprecation 1건 |
| pip check | 통과 |
| TypeScript | 통과 |
| Vitest | 14 passed |
| Vite build | 통과 |
| Playwright Chrome, 실제 모델 결과 필수 | 14 passed (16.5s), Console/pageerror 검사 포함 |
| 모델 없는 실제 서버/HTTP | health 정상 → 업로드/draft → 202 → GET failed/PHOTO_MODEL_UNAVAILABLE → 원본 선택, byte/facts 보존 |
| 기존 u2netp 실제 서버/HTTP | completed + RGBA 처리본, 비리사이즈 RGB/프레임 동일, 투명 alpha 존재, 원본 재선택/byte/facts/TTL 보존 |

API 검증 입력은 Pillow 합성 그래픽입니다. 기존 승인된 로컬 u2netp를 재사용했으며 새 모델/데이터 다운로드를 수행하지 않았습니다. 모델 없는 서버는 실제로 존재하지 않는 모델 경로를 설정해 기동했습니다. 처리본 선택은 이 환경에서 409, 원본은 계속 사용 가능했습니다. pytest의 mask/실패/timeout·품질 경고는 fixture/fake 검증이고 실제 모델 실행과 구분합니다.

로컬 실행은 기존 서버를 종료하지 않고 사용 가능한 포트에 구성했습니다. UI http://127.0.0.1:5174, 모델 API http://127.0.0.1:8001/docs, 모델 없는 검증 API http://127.0.0.1:8002/docs입니다. 결과와 stdout/stderr는 주 작업 폴더 artifacts/pr11-verification/ 및 feature worktree artifacts/playwright/에 저장하며 Git에서 제외합니다. 현재 확인 서버는 유지합니다. 재부팅 이후 유지 보장은 없습니다.

## Git 포함 검사

index 비밀/파일 정책 검사와 명시적 경로 리뷰가 통과했습니다. origin/main..기능 head가 도입한 과거 blob 33개도 정책/모델 확장자/1MiB 제한으로 검사했고 위반은 없었습니다. HEAD의 가장 큰 추적 파일은 frontend/package-lock.json 72,749 bytes입니다. 실제 .env·업로드·모델·데이터 경로는 추적하지 않으며 .env.example만 공개 설정 예제로 포함합니다. 이는 흔한 패턴의 보조 검사이며 모든 비밀·개인정보 탐지를 보장하는 것은 아닙니다.

## main 보호와 CI

protect-main Ruleset(24925172)은 active, main PR 필수·삭제 금지·non-fast-forward 금지, bypass actor 없음입니다. 승인 리뷰 요구는 0건이며 **필수 status check 지정과 대화 해결 요구는 없습니다**. backend/frontend/repository-policy/browser-e2e가 실행·통과하는 것과 필수 병합 조건으로 강제되는 것은 다릅니다. 보호/권한은 변경하지 않았습니다. 기존 네 CI 성공을 확인했으며 이 보고서 커밋에도 전체 CI를 재확인합니다.

## 남은 위험과 사용자 확인

1. rembg 마스크가 상품 일부를 제거할 수 있습니다. 면적 휴리스틱은 모든 손상을 검출하지 않으며 실제 상품 사진 수동 QA가 필요합니다. 합성 fixture에서도 흰 테두리 일부가 제거됩니다. 이상하면 원본 사용을 선택합니다.
2. 단일 서버·동시 전처리 1건·기본 90초 제한, cold 모델 로딩 비용과 재시작 metadata 유실이 있습니다. timeout 시 child kill/회수, 실패/경고 시 원본 선택, 24시간 정리를 테스트했습니다.
3. 실제 배포 부하/메모리/상품별 segmentation 품질을 인증하지 않습니다. 사용자 사진 외부 전송·유료 API·ML 학습은 수행하지 않았습니다.
4. #11 병합 후 #14에 알려진 env/config/문서 충돌이 생길 수 있습니다. 이번에는 다른 PR을 수정하지 않으며 다음 단계에서 정상 merge·재검증으로 처리해야 합니다.
5. 사용자는 화면에서 상품 저장→배경 제거→원본/처리본 비교→원본 사용/처리본 사용→상태 재조회로 직접 확인한 뒤 병합을 승인해야 합니다.
