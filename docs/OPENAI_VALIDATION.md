# OpenAI 실제 연동 사전 보완 — 2026-10-30

## 노트북 이동 시점의 최신 상태

아래 본문은 실제 호출 전 사전 보완 기록입니다. 이후 사용자 승인으로 합성 상품 3사례의 실제 카피 생성 5회(재시도 2회 포함), 입력 2,931 / 출력 1,195토큰, 추정 $0.00757575 및 PNG 12장을 검증했습니다. 별도 이미지 편집 실험은 1회·27.301초·추정 $0.049817이며 상품 동일성 미통과로 서비스 채택하지 않았습니다. 실제 호출 결과를 기존 본문의 “0회/미검증”과 혼동하지 않습니다. 현재 기본은 Mock / paid=false이고 이번 이동 준비에서는 유료 호출하지 않습니다. 실제 결과·사용량 원장은 Git 제외 백업 ZIP에 보존하며 [LAPTOP_SETUP](../LAPTOP_SETUP.md)을 따릅니다. 디자인 시안들은 사용자 품질 승인을 통과하지 않았습니다.

PR #27 병합 main `a3101da`에서 `feat/service-openai-validation`으로 분리했습니다. 기존 카피·렌더링 HTTP schema와 Candidate/B 계약을 유지합니다. 실제 API 호출·유료 요청은0회이며 commit/push/PR 생성도 사용자 승인 전 보류합니다. OpenAI Docs 스킬로 공식 문서만 조회했습니다.

## 모델과 단가 확인

[공식 GPT-5.4 mini 모델 문서](https://developers.openai.com/api/docs/models/gpt-5.4-mini)에서 `gpt-5.4-mini-2026-03-17`, Responses/Structured Outputs 지원, 표준 텍스트 입력$0.75/출력$4.50(각100만 토큰)을 확인했습니다. cached input 할인은 예산 계산에 적용하지 않습니다. 모델명/SDK3.40.0/출력2048/timeout30초/SDK retry0을 유지합니다. 실제 계정 접근 권한·청구·생성 품질은 미검증입니다. 모델을 임의로 바꾸지 않습니다.

[Structured Outputs 문서](https://developers.openai.com/api/docs/guides/structured-outputs)에 따라 거절은 schema 성공과 분리합니다. adapter가 refusal·불완전 응답·usage 누락을 구분하고 안전한 코드만 반환합니다. 원문 API 예외·키·응답 거절 원문을 로그/HTTP 오류에 넣지 않습니다.

## 환경변수와 활성화 조건

| 서버 환경변수 | 기본값 / 의미 |
| --- | --- |
| HANJANG_COPY_PROVIDER | mock. openai 선택과 별도 유료 허용이 모두 필요 |
| HANJANG_COPY_ALLOW_PAID | false. 이번 작업에서는 항상 false |
| OPENAI_API_KEY | 서버 환경 또는 루트.env에서만 읽는 SecretStr. frontend/.env/VITE_*에 넣지 않음 |
| HANJANG_COPY_MODEL | gpt-5.4-mini-2026-03-17, 다른 ID는 차단 |
| HANJANG_COPY_MAX_REQUESTS | 기본6, 0..6. 재시도를 포함한 누적 요청 예약 상한 |
| HANJANG_COPY_BUDGET_USD | 기본0.10, 0..0.10. 누적 실측/불명 예약액 합계 상한 |
| HANJANG_COPY_MAX_RETRIES | 기본1, 0..1. 최초 시도 외 앱 재시도 수 |
| HANJANG_COPY_BUDGET_PATH | 기본 artifacts/copy-usage/ledger.json. 서버 전용; 기존 원장을 삭제/경로 변경해 한도를 우회하지 않음 |

실제 테스트를 승인받은 뒤에만 provider=openai·allow_paid=true와 로컬 서버 키를 설정하고 서버를 재시작합니다. 이번에는 .env를 읽거나 수정하지 않았습니다. 기본 Mock은 SDK/adapter를 초기화하지 않고 비용 원장을 만들지 않습니다. 서버를 단순 실행하거나 화면을 여는 것으로 생성 요청을 보내지 않습니다.

합성3사례×각 최대2시도=생성 최대6회입니다. 한 요청 예약액은 `(6000×0.75 + 2048×4.50)/1000000 = $0.013716`, 여섯 번이면 `$0.082296`입니다. 설정 총 예산$0.10보다 작고, 예산을 더 낮추면 다음 요청을 보내기 전에 차단합니다. 메타데이터 조회를 제거했으므로 추가 모델 조회 요청은 없습니다. 이는 표준 단가·입력 상한 가정의 애플리케이션 추정 상한이며 외부 서비스의 청구 차단 기능을 대신하지 않습니다. 입력 검사는 byte 기반 보수 추정이지 공식 토큰 계수기가 아닙니다. 실제 usage가 입력6000/출력2048을 넘으면 알려진 비용을 원장에 그대로 기록하고 COPY_USAGE_LIMIT_EXCEEDED로 재시도 없이 중단합니다. 외부 요금 변경·세금 등은 별도 확인 대상입니다.

## 원장·오류·재시도

생성 전 reserve → dispatched 기록 → SDK responses.create 한 번 → 실측 settle 또는 실패 코드를 기록합니다. 각 재시도도 별도 예약합니다. 기존 calls 기록은 그대로 포함하며 설정 변경/재시작으로 초기화하지 않습니다. 원장에는 ID·상태·사용 토큰·비용·안전한 오류 코드만 기록하고 facts·사진·prompt·키는 저장하지 않습니다.

state는 reserved/dispatched/completed/failed입니다. usage_known=false인 timeout/429/통신 오류는 최대 예약액을 유지하고0원으로 가정하지 않습니다. API 시도와 실제 서버 도착/청구는 같은 개념이 아니며, 프로세스가 기록과 네트워크 송신 사이에 죽으면 dispatch 여부를 완벽히 증명할 수 없습니다. 불확실한 예약을 한도에 포함해 보수적으로 차단합니다. API 응답의 attempts는 로컬 예산 차단을 포함할 수 있지만 원장의 calls는 실제 송신 전 예약 단위이므로 개수를 혼동하지 않습니다.

모델 조회는 별도로 호출하지 않습니다. SDK retry0이며 정상 Structured Outputs·schema 오류·거절·불완전 응답·timeout·429·quota·401·404를 fake client로 검사합니다. 실패 시 Mock으로 몰래 전환하지 않고 입력/사진을 유지한 failed 상태를 반환합니다. 모델이 준비되지 않았다고 모델 ID를 자동 변경하지 않습니다.

## 글리프 정책

fontTools4.68.0으로 동봉 Noto Sans KR2.004의 실제 cmap과 SHA256을 검사해 지원 코드포인트를 읽고 캐시합니다. 프롬프트와 내부 정책 version을 올려 오래된 카피 캐시와 구분합니다. font 사전 확인 실패는 비용 발생 전에503 COPY_FONT_UNAVAILABLE입니다.

생성 문구는 `validate_copy()`에서 미지원 코드포인트·이모지 그림문자 범위·ZWJ 등 format 문자·variation selector·keycap 결합을 거부하며 COPY_GLYPH_UNSUPPORTED를 기존 제한 재시도 경로로 처리합니다. 일반 한글/영문/숫자/문장부호·원화 기호는 실제 폰트 지원 여부로 허용합니다. broad pictograph 범위는 일부 기호를 보수적으로 거부할 수 있습니다.

facts는 LLM의 생성 문구와 분리하며 삭제·정규화·치환하지 않습니다. placeholder가 사용자 원문을 연결하는 경우 원문을 그대로 유지합니다. 사용자 facts는 생성용 이모지 금지 정책을 강제하지 않고 실제 폰트 coverage를 렌더링 전에 검사합니다. 지원하지 않는 경우 RENDER_UNSUPPORTED_GLYPH와 이해 가능한 안내를 제공하며 원문은 보존합니다. 기존 Chromium/CDP 최종 글리프 검사도 유지합니다. cmap은 shaping·모든 결합문자·실제 가독성 전체를 보증하지 않습니다.

## 테스트·결과

유료 호출 없이 fake SDK와 외부 socket 차단(Windows asyncio 내부 loopback만 허용)을 사용합니다. 정상 JSON·스키마 오류·글리프·timeout/429/quota·refusal/incomplete·호출/비용 한도·실측 불명·API 키 비노출·앱 재시도·Mock/렌더링 회귀를 검사합니다. 최초 테스트에서 Windows asyncio 내부 socket까지 막아2 setup 오류가 났으며 loopback 예외를 넣어 수정했습니다.

전체pytest207 passed / 브라우저 opt-in18 skipped(14.02초), Vitest30 passed, TypeScript/build/pip check 통과입니다. 같은18개를 실제 Chrome으로 별도 실행했고 렌더링 Store/API17개와 합해35 passed(76.47초)입니다. 독립 backend 검증은225개이며 중복 합산하지 않습니다. 전체E2E23 passed(약1.2분), 실제 FastAPI/React·Mock카피·실제PNG 흐름과 모의503을 구분했습니다. 새 E2E는 사용자 가게명의 미지원 이모지 원문 보존과 렌더링 오류 안내를 확인합니다. 실제 OpenAI 계정 접근·한국어 문구 품질·실측 과금·네트워크 지연은 미검증입니다. commit/push하지 않았으므로 새 GitHub Actions 실행도 없습니다.

실행 환경은 Windows/Python3.12.10/Node24.20.0/설치 Chrome channel입니다. 결과는 Git 제외 artifacts/openai-validation/과 artifacts/playwright/report/index.html·results.json에 있습니다. 사용자 확인 서버는 http://127.0.0.1:5190 / Swagger http://127.0.0.1:8020/docs 이며 Mock/paid=false·loopback으로 유지합니다. 기존 서버를 종료하지 않았고 재부팅 후 유지는 보장하지 않습니다.

```powershell
New-Item -ItemType Directory -Force artifacts/openai-validation | Out-Null
$env:HANJANG_COPY_PROVIDER='mock'
$env:HANJANG_COPY_ALLOW_PAID='false'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp artifacts/openai-validation/full
$env:RUN_RENDER_TESTS='1'
$env:HANJANG_RENDER_CHANNEL='chrome'
.\.venv\Scripts\python.exe -m pytest tests/service/test_rendering.py -q -p no:cacheprovider --basetemp artifacts/openai-validation/rendering
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test:ci
npm.cmd --prefix frontend run build
$env:PLAYWRIGHT_CHANNEL='chrome'
$env:PLAYWRIGHT_FRONTEND_PORT='5190'
$env:PLAYWRIGHT_BACKEND_PORT='8020'
npm.cmd --prefix frontend run test:e2e
.\.venv\Scripts\python.exe -m pip check
```
