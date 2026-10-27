# S5a / 7단계 Mock 카피 검증 보고서

검증일: 2026-10-28, Windows Python3.12.10/Node24.20.0. 기준 main627ddeb(PR #24 병합)에서 feat/service-copy로 작업했습니다. **사용자 요청으로 실제 OpenAI 결제/호출은 보류**입니다. 실제 호출0회·비용$0, 실제 모델 접근·카피 품질·실제 토큰·네트워크 지연은 미검증입니다.

## 구현/미검증 경계

구현: 호환 draft 특징/주소 옵션, snapshot 일치409, copy-generation POST202/GET, 네 전략/길이/plain text/사실 검사, 제한 retry, 입력/사진/context/설정별 캐시·stale gate, Mock 네 카드, 사용량/오류 모델, 유료 gate와 향후 비용 상한 원장입니다.

OpenAI adapter/요청 구조는 fake client로만 시험했습니다. 실제 API가 schema를 받아들이는지, SDK 네트워크 성공, 사용자 계정의 model 접근, 한국어 생성 품질, usage/요금 실측은 시험하지 않았습니다. Gemini/Groq/Ollama 설치·키·호출·사진 직접 전송도 하지 않았습니다. Mock 통과를 실제 LLM 기능 검증 완료로 보고하지 않습니다.

## 자동 테스트

| 검사 | 결과 |
| --- | --- |
| 전체 서비스·계약 pytest | 150 passed, 기존 AnyIO deprecation1건 |
| 신규 copy 테스트 | 38개 포함: 호환 필드 생략/명시 초기화·검증·네 전략·원문/hash 보존·가격 표기·캐시·snapshot/진행 중 변경·stale·인증·만료·요청 제한·비용/paid gate·fake SDK |
| 기존 B 연동 계약 테스트 | 전체 pytest에38개 포함, Facts/Candidate schema 변경 없음 |
| Vitest | 22 passed (신규 카피4개 포함) |
| TypeScript/Vite build | 통과 |
| Chrome Playwright | 20 passed (41.8초): 카피 신규3개+기존17개 |
| 서비스 pip check | 통과 |

명령:

```powershell
.\.venv\Scripts\python.exe -m pytest
npm.cmd --prefix frontend run test:ci
npm.cmd --prefix frontend run build
$env:PLAYWRIGHT_CHANNEL='chrome'
$env:PLAYWRIGHT_FRONTEND_PORT='5180'
$env:PLAYWRIGHT_BACKEND_PORT='8010'
npm.cmd --prefix frontend run test:e2e
```

브라우저는 실제 로컬 FastAPI+Mock copy provider입니다. 상품 특징 저장·개행 재조회·카피4개·중복 요청·새로고침·특징 변경 후 stale 경고·재생성·모바일·500자 제한을 확인했고 정상 카피 흐름 Console/pageerror도 검사했습니다. copy409/잘못된 응답 화면은 모의입니다. 기존 사진 분석과 배경 제거는 로컬 가중치가 있는 환경에서 실제 실행됐으며 외부 LLM 호출과 별개입니다. CI는 로컬 가중치 없이 offline fallback/합성 fixture를 사용합니다.

## 합성3사례 — Mock만 실행

artifacts/service-copy/mock-cases/examples.json에 실제 로컬 Mock 응답을 저장했습니다. 각 사례의 facts/특징이 원문으로 유지되고 네 전략/스키마가 일치함을 확인했습니다.

| 합성 사례 | 특징 | 주소 옵션 | 결과 |
| --- | --- | --- | --- |
| 합성 카페/디카페인 커피/4,500원 | 고소한 풍미 | false | Mock4개, 원문 유지 |
| 합성 베이커리/우유 빵/3,000원 | 바삭한 식감·우유 사용 | false | Mock4개, 원문 유지 |
| 합성 분식/야채 김밥/5,000원 | 매콤한 소스 | true | Mock4개, 원문 유지 |

고정 Mock 예시: emotional='일상에 더하는 작은 여유', price='가격을 확인하고 선택하세요', visual='사진 속 상품을 만나보세요', brand='우리 가게와 만나는 시간'. 이는 LLM의 맞춤 생성·전략 품질 평가가 아닙니다. 특징이 달라도 고정 예시를 반환하며 UI에 Mock을 표시합니다. 원문 가격의 공백/단위를 정규화하지 않습니다.

## 발견·수정·한계

- 최초 숫자 검사는 substring이라10,500원에 없는500원을 통과시켰습니다. 숫자 토큰 집합의 정확한 일치로 바꾸고 회귀 테스트로 남겼습니다. 숫자가 같아도 가격의 공백/단위를 바꾼 통화 표기는 거부하고 서버 원문 연결을 검사합니다. 이 보수 규칙은 특징에 적힌 별도 금액 표현도 거부할 수 있습니다.
- draft 확장으로 프론트 saveInput의 인자가 추가돼 기존 단위 테스트1개가 실패했습니다. facts 검증은 유지하면서 승인된 새 기본값까지 검사하도록 갱신·재실행했습니다.
- 생성 문구의 일부 금지 주장/새 숫자/HTML/제어 문자/길이·중복 전략은 거부하지만, 모든 의미적 허위·새 고유명사·부정 문맥을 탐지하는 검증기는 아닙니다. 사용자 검토가 필수입니다.
- SDK OpenAI3.40.0과 추가 의존성만 서비스 .venv에 설치했습니다. 기존 httpx·Pillow/rembg 버전은 유지했고 .venv-ml/.venv-analysis의 pip freeze 전후 일치를 확인했습니다. B ml/·scripts/ml_*·tests/ml은 변경하지 않았습니다.
- 키/이미지/가중치/원문 로그를 Git에 추가하지 않았습니다. 실제 비용 원장 artifacts/copy-usage/ledger.json은 생성되지 않았으며, budget 시험은 pytest 임시 원장과 fake client를 사용했습니다.
- 재시작 시 RAM 세션·결과 유실, 단일 서버·동시 카피1개, 24h TTL, 보수 입력 예산과 사실 검사에 따른 오탐 가능성이 남습니다. 실제 네트워크 timeout/429/모델 접근·OpenAI 한국어 품질은 미검증입니다.

## 사용자 확인 환경

화면 http://127.0.0.1:5180, API http://127.0.0.1:8010/docs. Mock/paid=false로 실행하고 프로세스를 유지합니다. 기존 사용자 서버를 종료하지 않습니다. 재부팅 이후 유지나 다른 PC 접근을 보장하지 않습니다.

사진·가게명·상품명·가격·특징 저장 → 필요 시 사진 선택/분석 → '4전략 카피 생성' → Mock 카드4개와 원문 facts 확인 → 특징 변경/저장 → 이전 결과 경고 → 재생성 → 저장 정보 다시 조회 순서로 검토합니다.

브라우저 보고서: artifacts/playwright/report/index.html, results.json, results/의 copy-mock.png·copy-mobile.png·browser.log. 결과물은 Git 제외이며 검토 없이 외부 공유하지 않습니다. 무료/저비용 대안과 미승인 이미지 A/B 계획은 [COPY_PROVIDER_OPTIONS](COPY_PROVIDER_OPTIONS.md)를 따릅니다.
