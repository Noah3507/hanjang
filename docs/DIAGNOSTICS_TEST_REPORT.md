# 11단계 가독성 진단 검증 기록

2026-10-31 Windows, Python 3.12 서비스 `.venv`, Node24, 기존 Google Chrome/Playwright, 동봉 Noto Sans KR. 최신 main `2cf0890`(PR45 병합 확인)에서 `feat/service-diagnostics`로 분리했습니다. B 코드·Candidate/B schema/fixture는 수정하지 않았습니다.

## 최종 실행 결과

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

CI는 기존 네 jobs를 유지하고 browser-e2e의 실제 renderer pytest 대상에 신규45개와 스크린샷 glob만 추가합니다. 의존성·유료 서비스·새 job은 없으며 추가 실행 시간은 로컬 기준 십여 초입니다. Windows 로컬 결과와 GitHub Ubuntu 결과는 구분하며 PR의 최신 Checks에서 확인합니다.
