# 11단계 가독성 진단 검증 기록

## PR #46 교차 리뷰 보완 (2026-11-01)

이 절이 아래 2026-10-31 초기 검증보다 최신입니다. 큰 글자3:1 분기를 제거하고 모든 텍스트에 보수적 참고 기준4.5:1을 적용합니다. 캔버스의 px는 모바일 실제 표시 크기가 아니므로 WCAG 큰 글자 분류에 사용하지 않습니다. 정확히4.5는 정상, 미만은 문제이며 반올림하지 않습니다. WCAG 인증·모든 출력 환경의 가독성 보장이 아닙니다.

대비 측정과 판정은 value/threshold/status/reason으로 구분합니다. 색 근거가 있으면 글꼴 크기·굵기가 불완전해도 균일 기준으로 판정하고 그 이유를 표시합니다. 근거 없는 항목은 null/unavailable이며 partial을 정상으로 숨기지 않습니다. GET은 원본·선택 사진 및 광고 PNG 무결성 실패를 오류로 반환하고, 입력·카피·사진·revision 변경 또는 최신 렌더링 부재는 이전 결과를 stale로 보존합니다. disabled는 실제 snapshot과 분리하며 마지막 확인 결과 안내·재활성화 시 GET 재검증·늦은 응답 차단을 유지합니다.

### 보완 후 최종 회귀 결과

| 실제 실행 검사 | 통과 | 실패 | skip |
| --- | --- | --- | --- |
| 전체 backend(service/integration, 실제 Chromium 포함) | **390** | 0 | 0 |
| 그중 diagnostics(기존45 + 추가25) | **70** | 0 | 0 |
| frontend Vitest / 15 files | **61** | 0 | 0 |
| 전체 Playwright / 실제 API·Mock 카피·실제 Chromium | **30** | 0 | 0 |

backend 최종137.07초, Playwright 최종2.5분. TypeScript·production build·pip check·문서 링크·diff 공백 검사도 통과했습니다. 기존 AnyIO deprecated alias 경고1건 외 신규 경고·실패는 없습니다. B ML 테스트·유료 API·새 모델 검증은 범위 밖이며 실행하지 않았습니다.

추가 테스트는 원본/광고 asset의 삭제·변경·손상·소유권 오류, 입력/카피/사진/revision/렌더링 부재의 stale 조회, 입력 변경과 무결성 오류의 동시 발생, 유효하지 않은 글꼴 계측의 균일 대비 판정,32px 본문3~4.5 대비·부분 측정·정확한4.5 경계, disabled 중 성공본 유지와 늦은 응답 무시를 검증합니다. 기존 만료·권한·편집·ranking stale·PNG/PDF·원본 보존 검사도 전체 재실행했습니다.

최종 로그는 `artifacts/diagnostics/review-backend-final.log`, `review-frontend-final.log`, `review-build.log`, `review-e2e-final.log`입니다. 브라우저 결과·PNG/PDF·합성 스크린샷은 `artifacts/diagnostics/e2e-review-final/`, HTML은 `artifacts/diagnostics/html-review-final/index.html`에 보관합니다. 진단 E2E의 Console/pageerror0,30개 전체 pageerror 검사 통과입니다. 서버 http://127.0.0.1:5188 / http://127.0.0.1:8015/docs 는 Mock/paid=false·localhost로 유지합니다. PC 재시작 후 유지는 보장하지 않습니다.

### 추가 배경 캡처 성능: 실제 측정

Windows10 19045, Intel Core i7-9700F 3.00GHz, Python3.12.10, Node24, Chrome156.0.8078.76, 기존 `.venv`/Playwright, 동일 네 전략 HTML·동일 합성 RGB PNG·동봉 Noto 폰트·1080×1350/배율1에서 측정했습니다. 측정 중 다른 렌더링 테스트를 병행하지 않았습니다. 각 방식1회 워밍업을 제외한 뒤5회씩 번갈아 실행했습니다. 각 실행은 새 worker와 브라우저를 사용하는 기존 서비스 방식입니다.

| 방식 | 원시 측정5회(ms) | 중앙값(ms) |
| --- | --- | --- |
| 추가 배경 캡처 없음 | 3715.5, 3700.0, 3679.2, 3696.8, 3610.4 | **3696.8** |
| 추가 배경 캡처 있음 | 3917.2, 3933.9, 3986.5, 3895.4, 3882.0 | **3917.2** |
| 차이 | 중앙값 차이 / 기준 중앙값 | **+220.4ms / +5.96%** |

워밍업은 각각3679.7ms/3905.9ms였습니다. 측정 범위는 네 광고 worker subprocess 시작부터 PNG·metadata JSON 전체 응답 수신까지입니다. HTML/Jinja 준비, Python 증거 후처리, HTTP·파일 저장 시간은 제외됩니다. 현재 worker의 로컬 복사본에서 optional 배경 캡처 블록만 제거한 비교본을 사용했으며 공통 glyph/eligibility 계측은 양쪽에 유지했습니다. 따라서 역사적 renderer 전체와의 비교가 아니라 **배경 캡처 자체와 그 응답 데이터 증가의 추가 비용**을 분리한 시험입니다. 모든12회(워밍업 포함)의 원래 네 PNG bytes/SHA-256이 동일했고 현재 방식의 배경 캡처도 모두 생성됐습니다.

실험 스크립트·worker 복사본·원시 JSON은 Git 제외 `artifacts/diagnostics/benchmark_review.py`, `artifacts/diagnostics/performance-review/`에 보관했습니다. 운영 worker·설정은 성능 비교 때문에 변경하지 않았습니다. 단일 합성 입력·이 PC 결과이며 다른 상품·하드웨어·서버 부하의 성능을 보장하지 않습니다. 유료 호출·다운로드는 없었습니다.

2026-10-31 Windows, Python 3.12 서비스 `.venv`, Node24, 기존 Google Chrome/Playwright, 동봉 Noto Sans KR. 최신 main `2cf0890`(PR45 병합 확인)에서 `feat/service-diagnostics`로 분리했습니다. B 코드·Candidate/B schema/fixture는 수정하지 않았습니다.

## 초기 구현 실행 결과 (2026-10-31)

| 검사 | 결과 | 범위 |
| --- | --- | --- |
| backend 전체 pytest | **365 passed**, 실패/skip 0, 133.37초 | tests/service + tests/integration; 실제 Chromium opt-in 포함 |
| 신규 diagnostics | 위 결과 중 **45 tests** | 경계·유효성·소유권·TTL·동시성·stale·실제 계측 |
| frontend Vitest | **60 passed**, 15 files | 신규 API3 + 진단UI6, 기존 회귀 포함 |
| TypeScript / frontend build | 통과 | tsc --noEmit + production Vite build |
| Playwright 전체 | **30 passed**, 2.5분 | 실제 localhost API/Chromium + 명시적 장애 모의 |
| pip check | 통과 | 서비스 환경 의존성 충돌 없음; 추가 설치 없음 |

백엔드 경고 1건은 기존 Starlette TestClient의 AnyIO BlockingPortal deprecated alias입니다. 실패는 아닙니다. B `tests/ml`은 pytest 기본 경로 밖이며 이번 범위에서 실행·수정하지 않았습니다. 실제 LLM·실제 ML 선호도 모델 검증은 하지 않았으며 Mock 카피/MockRanker를 사용했습니다. 유료 API 호출·모델 다운로드 0회입니다.

```powershell
$env:RUN_RENDER_TESTS='1'
$env:HANJANG_RENDER_CHANNEL='chrome' # Windows 기존 Chrome 사용; CI는 설치된 Chromium
$env:HANJANG_COPY_PROVIDER='mock'
$env:HANJANG_COPY_ALLOW_PAID='false'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp artifacts/diagnostics/final --tb=short
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test:ci
npm.cmd --prefix frontend run build
$env:PLAYWRIGHT_FRONTEND_PORT='5188'
$env:PLAYWRIGHT_BACKEND_PORT='8015'
$env:PLAYWRIGHT_CHANNEL='chrome'
npm.cmd --prefix frontend run test:e2e -- --output=../artifacts/diagnostics/e2e-final
```

## 검증한 내용

- 알려진 대비21:1/1:1/4.478…, 큰 글자 경계, 반올림 전4.5 판정, 36px/40% 경계, bbox 합집합 중복 제외·clipping, NaN/Infinity/누락을 정상·0으로 바꾸지 않는 동작.
- 실제 Chromium 네 후보의 PNG에 결합된 배경 픽셀 증거, 편집 후 새 PNG 해시, 단색 대비. 실제 gradient/opacity는 unavailable이며 다른 유효한 측정값 유지.
- 동기 POST200, GET 복원, 동일 snapshot 재사용, 동시 실행503, revision/asset 충돌409, 계산 중 입력 변경·편집 완료 시 오래된 결과409, busy 해제·재시도.
- 인증·다른 세션·TTL·413/422, 누락/손상/변경 PNG, 전체 계산 실패·복구, 개별 규칙 실패 시 부분 결과.
- 원본 bytes·facts·Candidate 계약·ranking·render active 불변. 편집 실패는 성공 진단 유지, 편집 성공은 stale 처리. 실제 PNG 재편집과 A4 PDF 규격·페이지 수·표시 검사는 기존 회귀를 실행.
- UI 네 후보, 정상/주의/문제/측정 불가와 coverage, 펼침 가능한 근거·조치, 키보드 details, 375px 가로 넘침 없음. 대상 진단 E2E Console/pageerror 0건.
- 실제 API 일반 흐름과 Playwright route로 모의한 늦은 이전 응답/503을 구분. 장애 모의 후에도 네 PNG 유지 및 실제 API 재시도 복구.

## 발견하고 수정한 문제

최초 실제 Chromium 시험에서 JS 비활성 페이지의 addStyleTag가 load를 기다려 worker가 90초 timeout되었습니다. DOM style 직접 설정으로 변경하고 선택적 배경 캡처는 2초 제한·실패 시 unavailable로 처리했습니다. 최종365개/30개는 수정 후 전체 재실행 결과입니다. 공개 PNG는 계측 변경 전에 먼저 확보하므로 배경 캡처 실패가 광고 생성 실패로 이어지지 않습니다.

## 결과물과 직접 확인

- 로그: `artifacts/diagnostics/backend-final.log`, `frontend-final.log`, `e2e-final.log`.
- desktop/mobile 스크린샷과 실제 다운로드: `artifacts/diagnostics/e2e-final/diagnostics-actual-measure-49074-gnose-and-PNG-PDF-downloads-chromium/`의 `diagnostics-desktop.png`, `diagnostics-mobile.png`, `diagnosed.png`, `diagnosed.pdf`.
- Playwright HTML: `artifacts/diagnostics/html-final/index.html`. 생성물은 Git 제외, CI는 기존 방식으로 스크린샷과 실패 artifact를 보관합니다.
- 확인 URL: http://127.0.0.1:5188, Swagger: http://127.0.0.1:8015/docs. 이번 서버는 Mock/paid=false이며 기존 다른 포트 서버는 변경하지 않았습니다. PC 종료 후 유지는 보장하지 않습니다.

사진·상품 정보 저장→4전략 Mock 카피 생성→광고 네 장 렌더링→**가독성 진단 실행**→네 후보의 근거 펼침→문구 편집·재렌더링→이전 진단이 최신으로 표시되지 않는지 확인→재진단→PNG/A4 PDF 다운로드 순서로 확인합니다. 긴 제목60자/본문160자는 compact 배치의32px 주의가 나올 수 있으며 짧게 재편집해 개선을 비교할 수 있습니다. 진단은 문구·색을 자동 수정하지 않습니다.

## 한계와 CI

36px/40%는 초기 서비스 휴리스틱입니다. 텍스트 면적은 block bbox이며 교차의 디자인 의도를 판별하지 못합니다. gradient/image/투명 합성은 보수적으로 측정 불가입니다. 자유 색상·배치 편집, OCR·시선·종합 점수는 없습니다. 이전 renderer의 증거 없는 metadata는 추정하지 않고 측정 불가로 처리합니다.

CI는 기존 네 jobs를 유지하고 browser-e2e의 실제 renderer pytest에 진단 테스트 파일과 스크린샷 glob을 포함합니다(최초45개, 리뷰 보완 후70개). 의존성·유료 서비스·새 job은 없습니다. Windows 로컬 결과와 GitHub Ubuntu 결과는 구분하며 PR의 최신 Checks에서 확인합니다.
