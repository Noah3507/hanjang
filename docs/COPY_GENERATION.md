# S5a / 사용자 가이드 7단계: 4전략 광고 카피

2026-10-30 통합: 기존 API와 Mock 경로를 유지하며 호출 통제·폰트 검증을 보완했습니다. 이번 통합은 실제 호출0회·비용$0이며 과거 승인된 실제 시험 기록과 구분합니다. 현재 계정 접근·실제 문구 품질·과금은 재검증하지 않았습니다. 상세 설정·원장 의미·시점별 기록은 [OPENAI_VALIDATION](OPENAI_VALIDATION.md)을 따릅니다. 다른 제공자나 사진 입력은 추가하지 않습니다.

## 현재 범위

상품 정보 저장 → 현재 사진/입력/context snapshot → 명시적 카피 요청 → Mock 네 전략 → 상태 조회/원문 facts와 카피 분리 표시입니다. LLM은 render-ready Candidate/PNG/rank를 반환하지 않습니다. 후속 S5b 렌더링은 [RENDERING](RENDERING.md)에서 별도 구현하며, 이 카피 단계에서는 선호 순위·편집·다운로드와 B ml/을 구현하지 않습니다. copy-generation 응답의 additive copy_key는 렌더링 요청에서 완성 카피 결과를 검증하는 불변 식별자입니다.

| 전략 | 목적 | Mock 예시 headline |
| --- | --- | --- |
| emotional | 일상의 여유·공감 | 일상에 더하는 작은 여유 |
| price | 입력 가격 확인, 할인/가성비를 만들어내지 않음 | 가격을 확인하고 선택하세요 |
| visual | 실제 상품 사진 확인, CLIP을 사실로 단정하지 않음 | 사진 속 상품을 만나보세요 |
| brand | 가게와의 만남·인상 | 우리 가게와 만나는 시간 |

위 문구는 고정 **Mock 데모**이며, 사용자 특징에 맞춰 LLM이 생성한 결과나 품질 증거가 아닙니다. 실제 모드에서도 한 번에 네 전략을 요청하도록 adapter를 준비했습니다.

## 입력 확장과 하위 호환성

기존 Facts(store_name/product_name/price_text/address/instagram_handle)는 그대로입니다. B 후보 v1.1 스키마/예제를 수정하지 않습니다. `InputDraft`와 `DraftResponse`의 최상위에 다음을 추가합니다.

- product_features: string|null, 최대500 Unicode code point, 기본null. 맛·식감·재료·장점의 사용자 제공 근거입니다. 원문 공백/개행을 보존하며 공백만·잘못된 타입·제어 문자(개행 외)는 거부합니다. 허용은 LF/CRLF이며 저장 시 자동 교정/정규화하지 않습니다.
- use_address_for_copy: strict bool, 기본false. 주소가 있고 true일 때만 LLM payload에 주소를 추가합니다.
- 기존 클라이언트의 PUT에서 두 필드가 **생략되면 기존 값 유지**, 최초 생성 시null/false입니다. 명시적인 null/false만 초기화합니다. facts/mood는 기존처럼 필수이며 공백·가격 표기를 변경하지 않습니다.
- 새 프론트는 구버전 응답의 누락 필드를null/false로 읽습니다. 새 필드를 구버전 서버에 보낼 수 있다는 의미는 아닙니다. 서버를 먼저 업데이트해야 합니다.
- 저장값/특징/주소 옵션/선택 사진/provider·model·prompt/context가 달라지면 cache key가 달라지고 이전 카피는 is_current=false입니다. 같은 snapshot으로 돌아오면 해당 캐시를 재사용합니다. 광고 생성은 입력 저장만으로 시작하지 않습니다.

## 전송 데이터와 사실 보호

provider_payload는 가게명·상품명·가격·분위기·사용자 특징·현재 선택 사진의 CLIP 단서만 만듭니다. 주소는 명시 옵션에 따라 추가합니다. Instagram·사진 bytes/URL·파일 경로·세션 token·K-means palette는 보내지 않습니다. 특징 등 자유 입력이 전송 제외 주소나 Instagram을 그대로 반복하면 COPY_PRIVATE_INPUT으로 거부합니다. 같은 문자열이 다른 필드에도 포함되는 드문 경우 보수적으로 거부할 수 있습니다.

AnalysisStore.context()의 is_current/completed gate를 사용하고 잠금 아래 facts/선택 asset/context를 함께 고정합니다. stale 또는 분석 미완료·실패·CLIP unavailable은 시각 단서 없이 생성 가능합니다. 사용자 facts와 특징이 CLIP과 충돌하면 사용자 정보를 우선합니다. 생성 도중 입력/사진/context가 달라져도 요청 snapshot의 결과를 보존하고 최신 여부를 다시 계산합니다. 미래 renderer는 current_for_render()를 통해 current+completed만 읽고 실제 render 시에도 snapshot을 확인해야 합니다.

LLM 출력은 `{variants:[{strategy,copy:{headline,body,cta}}]}`뿐입니다. 서버 facts는 응답과 카드에 원문으로 별도 연결합니다. 이름/가격/주소를 카피에 반복할 때는 내부 `[[store_name]]`/`[[product_name]]`/`[[price_text]]`/`[[address]]` token을 서버 원문으로 치환하고 길이를 재검사합니다. 주소 미사용 시 주소 token은 허용하지 않습니다. 80자 이름을60자 headline에 무리하게 넣으면 거부하고 이름을 자르지 않습니다.

Pydantic은 네 전략 각각1개·필드 누락/추가·문자 길이(60/160/30)·plain text·제어 문자·완전히 같은 네 문구를 검사합니다. 증거에 없는 숫자 **토큰**·할인/이벤트/일부 재료/원산지/맛/효능 표현·연락처/URL을 보수적으로 검사합니다. 새 사실이나 문제를 발견하면 응답을 버리고 제한된 재시도 후 failed로 처리합니다. 생성 문구를 임의로 고치거나 실제 제공자 실패를 Mock 성공으로 바꾸지 않습니다.

이 검사는 의미적 사실 검증기가 아닙니다. 새로운 고유명사/동의어/부정 표현/미등록 재료/논리적 모순 등을 전부 탐지한다고 보장하지 않습니다. 사용자 특징 자체도 외부 검증된 사실은 아닙니다. review_required=true와 사용자 검토 안내를 유지합니다. 고정 facts 보존과 생성 문구의 의미적 진실성 보장을 혼동하지 않습니다.

## Provider·중복·실패·비용

기본 Mock은 네 고정 예시만 반환하고 네트워크를 사용하지 않습니다. OpenAI Python SDK3.40.0, Responses API Structured Outputs, model `gpt-5.4-mini-2026-03-17`, reasoning none, store=false, SDK retries=0 adapter를 준비했습니다. 공식 모델 카탈로그의 ID/Structured Outputs 지원은 확인했으나 해당 사용자 계정의 접근 가능 여부는 미검증입니다. URL은 공식 api.openai.com으로 고정합니다.

현재 실제 호출은 보류입니다. 운영 모드를 자동 전환하지 않으며, 키가 있어도 기본 Mock입니다. 미래 별도 승인 후 provider=openai와 paid gate를 모두 켜야 합니다. 키는 서버 환경변수/비공개 .env에서만 읽고 로그·API·프론트 VITE_*에 넣지 않습니다. 모델 조회/최초 요청도 지금은 실행하지 않았습니다. store=false가 공급자 측 보안 로그의 무보관까지 뜻하지 않습니다.

입력 예산은 전체 prompt·payload·schema의 UTF-8 byte 수+1024 여유를 검사하며6000 초과 시422입니다. 이는 실측 토큰 수가 아닙니다. 출력max2048·timeout30초·SDK retry0을 유지합니다. 앱 재시도는 HANJANG_COPY_MAX_RETRIES=0 또는1(기본1), schema/사실/글리프·일부 일시 오류만 대상이며 대기는1초입니다. timeout·인증·모델·키·quota·거절·불완전 응답은 재시도하지 않습니다. 모델 metadata 조회를 제거해 생성 외 API 요청을 보내지 않습니다. 성공 여부로 계정 접근을 확인하는 작업은 별도 승인 후입니다.

provider/model/prompt/input/photo/context가 같은 processing/completed 요청은 재사용합니다. 다른 작업은503(COPY_BUSY), 실패 작업은 재요청할 수 있습니다. 단일 서버·한 카피 작업 실행을 가정하며 복잡한 큐를 도입하지 않습니다. 업로드의 동일24h TTL·소유권·no-store와 재시작 RAM 유실 한계를 유지합니다.

향후 실제 시험의 과거 승인 한도는 총6회/$0.10이며 현재는 집행 보류입니다. CopyBudget은 Git 제외 artifacts/copy-usage/ledger.json에 호출/비용 상한을 기록합니다. 호출 전에최대비용을 예약하고 사용량을 확인하면 실제 토큰 기반 추정치로 정산합니다. timeout/사용량 불명은0원으로 취급하지 않고 예약액을 유지합니다. 프로세스 재시작 시 원장을 지워 예산을 초기화하면 안 됩니다. 파일 잠금이 남으면 다른 프로세스 실행 여부를 검토해야 하며 자동 삭제하지 않습니다.

실제 SDK usage로 input/output tokens·추정USD·시도·지연을 기록하도록 준비했으나 현재 실사용 계측은 없습니다. Mock 토큰/비용은null(미측정)이며 실제 API 호출비용은 발생하지 않았습니다. 원장에는 원문/키/사진을 쓰지 않습니다. 예상비용은 공급자 청구서가 아니며, 실제 호출 한도나 모델 가격 변경 시 승인 후 다시 검토합니다.

## Windows 실행·확인

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
# 기본 Mock / paid disabled. API 키 불필요.
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
# 다른 터미널
npm.cmd --prefix frontend run dev
```

기본 URL5173/8000. 이번 확인용 서버는 http://127.0.0.1:5180, Swagger http://127.0.0.1:8010/docs입니다. 상품 정보·특징 저장 → 사진 선택/분석(선택) → '4전략 카피 생성' → Mock 카드4개 확인 → 특징 변경/저장 → 이전 결과 경고 → 재생성 → 다시 조회·새로고침 순서로 확인합니다. 모델/LLM 키 없어도 Mock 카피는 동작합니다. 기존 사용자 서버는 종료하지 않습니다.

## 검증과 다음 단계

단위/API·브라우저·Mock/실제 구분은 [COPY_TEST_REPORT](COPY_TEST_REPORT.md), 제공자 비교와 사진 전송 비교 계획은 [COPY_PROVIDER_OPTIONS](COPY_PROVIDER_OPTIONS.md)를 따릅니다. 다음 구현은 사용자 승인 후 렌더링 단계이며 이번에는 이미지 생성이나 B ranking을 구현하지 않습니다.

## 제공자 의존성 분리 보완

PR #25의 같은 브랜치에서 기존 API/UI를 유지하고 아래 경계를 분리했습니다. 제공자를 추가하거나 이미지 입력을 구현한 변경은 아닙니다.

- `copy_contract.py`: SDK와 요금에 의존하지 않는 `CopyProvider` Protocol, 텍스트 전용 `CopyPayload`, `ProviderResult`/`ProviderUsage`, 공통 오류입니다. 사용량은 각 호출의 불변 결과/오류에 포함되며 provider의 이전 요청 상태를 조회하지 않습니다.
- `copy_provider.py`: Mock과 명시적인 factory입니다. Mock 선택 시 OpenAI adapter나 SDK를 import/초기화하지 않습니다. API 키 없이 사용하며 다른 제공자로 자동 전환하지 않습니다.
- `copy_openai.py`: 승인된 OpenAI adapter의 SDK 요청·오류 변환·단가 계산입니다. 실제 호출은 계속 보류하고 paid gate=false를 유지합니다. 기존 OpenAI용 비용 원장도 이 adapter에서만 연결합니다.
- `CopyStore`: 공통 텍스트 payload·응답 검증·snapshot/TTL/캐시를 담당합니다. SDK, OpenAI 단가, provider의 last_usage 같은 내부 속성을 알지 않고 사용량 결과를 그대로 API에 매핑합니다. JSON/사실 검사에서 재시도해도 각 시도의 사용량을 유지합니다.

향후 다른 제공자를 승인하면 adapter와 factory 선택, 해당 제공자의 인증·요금·schema 매핑을 추가하고 공통 계약 시험을 통과시켜야 합니다. 현재 public provider enum은 mock/openai로 유지하므로 새 제공자 ID 공개는 별도 API 계약 승인 사항입니다. 이름만 바꾸거나 OpenAI base URL을 교체하는 방식으로 지원한다고 가정하지 않습니다.

이미지 입력도 현재 payload에 빈 image 필드를 미리 넣지 않습니다. 현 경로는 텍스트 전용이며 사진/Instagram 전송 금지와 주소 명시 옵션을 유지합니다. 미래 별도 승인 후 이미지 전송용 입력 계약·동의/원본 보존·예산·별도 payload builder/adapter를 설계해야 합니다. 현재 텍스트용 snapshot/검증·UI를 유지할 수 있는 경계를 마련한 것이며 멀티모달 지원 완료를 뜻하지 않습니다.
