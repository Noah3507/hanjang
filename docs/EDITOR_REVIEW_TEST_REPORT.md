# PR #44 안정성 리뷰 보완

## 원인과 수정

| 항목 | 원인 | 수정 |
| --- | --- | --- |
| PDF 실패 | Popen이 try 밖, finally에서 미생성/정리 예외 가능 | proc=None 이후 생성부터 보호, 미생성 정리 생략, bounded cleanup 및 정리 오류 비노출, PDF_FAILED503 |
| 공개 원자성 | 새 asset/derived/hash 등록 후 실패하면 부분 metadata 가능 | 공통 copy-on-write publication과 이전 참조 rollback. 편집 성공상태도 같은 transaction. exclusive 생성 파일만 정리 |
| PDF캐시 | 과거 revision 결과 누적 | 성공본 공개 시 비움, 동일revision/PNG 재사용. 실패 시 유지. PDF완료 재검증과 만료 캐시 참조 해제 |
| busy 복구 | boolean만 있고 dispatch/실행 소유권 불명확 | token과 예약/claim 구분. 미실행30초 예약만 요청 시 회수. running은 시간 회수 금지, late/duplicate callback fencing, 소유 token만 해제 |

원본 사진·facts·copy_key·네 후보 ID·revision/stale ranking·세션/소유권/TTL 계약을 유지한다. ML 점수캐시·B코드·fixture/schema·프론트엔드·외부 인프라/런타임 의존성 변경은 없다. 실제 유료API/모델 다운로드/추가 설치도 없다.

## 변경 파일

- `backend/app/services/export_service.py`
- `backend/app/services/editor_store.py`
- `backend/app/services/render_store.py`
- `backend/app/services/render_slot.py` (신규, 내부예약 소유권)
- `backend/app/services/uploads.py` (만료 PDF캐시 해제)
- `backend/app/api/editing.py`, `backend/app/api/rendering.py` (dispatch등록 실패 정리)
- `tests/service/test_editor_resilience.py` (신규)
- `docs/EDITING.md`, `docs/EDITING_TEST_REPORT.md`, 이 문서

## 추가 회귀 29개

Popen의 파일부재/권한/OSError/생성RuntimeError, worker비정상종료/timeout/잘못된JSON/base64/오류응답/cleanup오류를 직접·HTTP 경계에서 검증한다. 안전한503과 내부경로 미노출을 확인한다.

derived/assets/asset_hashes/exports/edited_renders/edits의 **실제 대입 직후** 각각 예외를 주입하여 기존 성공본·다른job·파일/인덱스/해시/캐시 보존, 실패상태, 재시도를 확인한다. 기존 PNG파일명 충돌 시 파일을 삭제하지 않는다. 최초 렌더링 등록 및 원본읽기 preflight 실패도 재시도 가능하게 검증한다.

PDF의 동일버전 재사용, 편집실패 시 유지, 성공 시 제거, 생성 중 새revision 차단, 만료 정리를 확인한다. 렌더링과 편집 양쪽에서 clock주입으로 미실행 예약복구/latecallback차단을 확인하고, 실제 thread+Event로 실행 중 worker를 오래 기다려도 회수/이중실행하지 않음을 검증한다. dispatch등록 예외와 worker인터럽트 후 failed·슬롯해제·재시도도 포함한다.

## 환경·실행

2026-10-31 Windows, Python3.12.10/Node24.20.0/기존 Chrome. 서비스 .venv·분석 .venv-analysis·공식 로컬모델 재사용. Mock/paid=false, HF/transformers offline. 기존 서버를 유지하고 검증은 React5187/FastAPI8014에서 수행했다.

- `RUN_RENDER_TESTS=1 HANJANG_RENDER_CHANNEL=chrome python -m pytest -q -p no:cacheprovider --basetemp artifacts/editor-review/full`: **320 passed**,105.75초,skipped0,AnyIO deprecated alias 경고1. 편집23·새 회귀29·기존1–9단계/실제Chromium/PDF를 포함하며 중복 합산하지 않는다.
- `npm --prefix frontend run typecheck`, `test:ci`, `build`: 통과, **51 tests / 13 files**.
- `python -m pip check`, `git diff --check`, index 비밀검사 수행.
- 전체 Playwright: **28 passed (2.0m), exit0**. 실제 PNG/PDF 결과는 `artifacts/editor-review/html/index.html`, `e2e/`에 보관한다. 정상 편집 console/pageerror를 별도 확인한다. 모든 검사는 실제 실행했으며 환경 문제로 미실행한 필수 검사는 없다.

PowerShell에서 환경변수를 먼저 설정하고 기존 `.venv/Scripts/python.exe`를 사용했다. E2E는 PLAYWRIGHT_CHANNEL=chrome, FRONTEND_PORT=5187/BACKEND_PORT=8014 및 DEV_BACKEND_URL=http://127.0.0.1:8014, 실제 rembg/CLIP 필수 옵션과 기존 coffee.png를 사용한다. 카피/임시순위는Mock, 오류 route는 모의다.

## 제약·병합 검토

진행 중인 실제 worker가 영구 정지했고 종료를 증명할 수 없으면 자동 슬롯 해제를 하지 않는다. 정상90초 worker timeout/정리·예외는 복구하지만 OS수준의 종료 실패·프로세스 hard kill은 관리자 확인/재시작이 필요하다. 파일 cleanup이 OS권한으로 실패하면 미등록 파일이 TTL sweep까지 남을 수 있고 공개되지 않는다. 인메모리 상태는 재시작복구를 보장하지 않는다.

Linux/GitHub Actions는 로컬 Windows 결과와 별도로 확인한다. 유료LLM/실제B모델·새 랭킹점수캐시는 범위 밖이다. 기존 PR #44에서만 업데이트하고 main병합은 사용자 승인대기다.
