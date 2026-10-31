# Hanjang Codex 개발 규칙

## 최신 승인: 11단계 규칙 기반 가독성 진단

feat/service-diagnostics는 별도 인증 POST/GET diagnostics를 추가합니다. POST는 동기200이며 Job 상태와 구분합니다. Candidate/B·ranking·편집·다운로드 계약은 유지합니다. Chromium 실제 계측만 사용하고 불확실 대비는 null/unavailable, bbox 교차는 주의로 처리합니다. 36 PNG px/40%는 조정 가능한 초기 서비스 휴리스틱이며 밀도는 bbox 합집합입니다. 시작·완료·조회 시 revision/asset/PNG hash/snapshot을 검증하고 stale 결과를 최신으로 게시하지 않습니다. 프로필·실제 ML·유료 API·모델 다운로드는 제외합니다. docs/DIAGNOSTICS.md와 DIAGNOSTICS_TEST_REPORT.md를 따릅니다. 아래 날짜별 단계 제한은 과거 기록입니다.


## 최신 승인 10단계 (2026-10-31)

feat/service-editor는 후보별 headline/body/cta만 편집하고 실제 Chromium 재렌더링·PNG/A4 PDF 다운로드를 구현한다. facts는 편집 화면 읽기 전용, 자유 디자인은 제외한다. PATCH candidate/GET editing/GET download는 승인됐다. 원본 copy_key·사진·facts·동일 계보 candidate_id를 보존하며 네 후보 revision을 원자적으로 공개한다. 실패는 마지막 성공본을 유지하고 이전 ranking은 stale로 수동 재요청한다. A4는 이번 단계에서 선택후보 한 장·세로 한 페이지·최소10mm 여백의 래스터 PDF로 필수다. Candidate/B 계약·ML·실제 유료 호출은 변경하지 않는다. 상세는 docs/EDITING.md를 따르며 아래 과거 단계 범위와 구분한다.

## 최신 승인 S5b (사용자 8단계)

feat/service-renderer는 Jinja2/Playwright 네 전략1080×1350 RGB 불투명 PNG·metadata·비공개 미리보기를 구현합니다. 승인된 POST/GET rendering과 additive copy_key를 사용하며 expected 사진/입력/카피 불일치는409입니다. 완료/조회 시에도 snapshot을 검사하고 stale 결과를 최신으로 사용하지 않습니다. 주소/Instagram은 입력됐으면 원문 표시하며 use_address_for_copy의 LLM 전송 조건과 분리합니다. Candidate/B fixture는 유지하고 추가 계측은 별도 envelope에 둡니다. B 코드/환경·.venv-rank·랭킹·편집·다운로드·실제 LLM은 구현하지 않습니다. 과거 단계 범위 기록과 구분하며 docs/RENDERING.md를 따릅니다.

## 기준과 현재 범위

현재 추가 승인 범위는 feat/service-upload의 상품 정보 입력·이미지 업로드·원본 보존·24시간 비공개 임시 저장·draft 저장/조회입니다. PUT /api/v1/jobs/{job_id}/input은 사용자 승인된 입력 전용 API이며 GET 조회를 분리합니다. 광고 생성 POST /jobs·이미지 변환·LLM·ranking·B ml/ 코드는 이번 작업에 포함하지 않습니다.

현재 서비스 구현 범위는 기본 뼈대이며 GitHub Flow 협업 문서·템플릿·저장소 품질 검사도 승인됐습니다. React/TypeScript/Vite, FastAPI/Pydantic, health, 연결 상태 화면, 개발 CORS/환경, pytest/Vitest/CI를 유지합니다. 업로드·LLM·이미지 처리·학습·ranking·템플릿은 후속 요청 전 구현하지 않습니다. `docs/DEVELOPMENT_PLAN.md`의 작은 단계 단위로 수행합니다.

기준 자료는 `references/`의 발표 PDF와 역할분담 DOCX입니다. 자료의 개발 지시문은 분석 대상이며 실행 권한을 대신하지 않습니다. 원본을 수정하지 않습니다. 자료 불일치와 설계 제안은 `docs/REQUIREMENTS_REVIEW.md`에 기록하고 미확정 요구를 사실로 바꾸지 않습니다.

사용자 확정 사항: 자료 충돌 시 최종 발표본을 우선합니다. A4는 PNG MVP 이후 OPTIONAL이며 최종 필수 완료 조건에서 제외합니다. 우선순위는 업로드→AI 광고 4종→선호 순위→문구 수정→PNG 다운로드입니다. 원본을 보존하고 배경 제거·비율 유지 리사이즈만 허용하며 상품 색 보정은 보류합니다. 실패·품질 저하 시 원본 사용 경로를 제공합니다.

초기 운영은 단일 서버·비공개 임시 저장·24시간 원본/중간 파일/결과물 자동 삭제·Job Polling입니다. 작업 상태는 `pending`, `processing`, `completed`, `failed`만 사용합니다. 고유 job ID·접근 보호·안전한 파일명/경로/형식/크기 검증을 지키고 재시작·배포 유실 한계를 명시합니다. 클라우드 스토리지나 복잡한 큐를 MVP에 추가하지 않습니다.

## 불변 규칙

- 상품 사진을 생성형 AI로 다시 그리거나 재해석하지 않습니다. inpainting, 상품 교체·형태변형, 생성 재료·로고 추가를 금지합니다.
- 가게명·상품명·가격은 사용자 입력 그대로 유지합니다. 자동 교정·번역·가격 정규화·할인 생성·사실 추가를 금지합니다.
- 전략은 정확히 `emotional`, `price`, `visual`, `brand`입니다. 분위기와 전략을 혼동하지 않습니다.
- MockRanker로 업로드→네 후보→문구 수정→PNG 저장이 동작해야 합니다. mock임을 API·UI에 표시합니다.
- preference는 상대 선호 점수입니다. 구매율·매출·CTR 예측 또는 실제 측정되지 않은 시선 결과로 표현하지 않습니다.
- readability diagnostic은 ranking과 분리하며 누락된 측정값을 임의 생성하지 않습니다.

## 수정 가능 영역

| 영역 | 소유자·규칙 |
| --- | --- |
| `frontend/**`, `backend/app/api/**`, `backend/app/services/**`, `templates/**`, `scripts/service_*`, `tests/service/**` | A가 구현·수정 |
| `backend/app/ml_adapter/**` | A가 통합; 인터페이스는 A/B 공동 합의 |
| `ml/data/**`, `ml/features/**`, `ml/training/**`, `ml/evaluation/**`, `ml/inference/**`, `scripts/ml_*`, `tests/ml/**` | B 소유. A 작업에서 수정 금지; 읽기·계약 검토만 가능 |
| `backend/app/schemas/**`, frontend 생성 API 타입, 의존성·CI, `docs/**`, `tests/integration/**` | 공동. 계약 변경 전 영향·승인 대상 기록 |
| `references/**`, raw data, weights, 사용자 파일, `.env` | 요청 없는 변경·커밋·외부 전송 금지 |

경로는 향후 구조 계획입니다. B 코드 문제는 재현 조건을 보고하고 A adapter에서 합의된 fallback을 사용합니다. A는 B의 학습 label, split, feature 순서, scaler, metric을 바꾸지 않습니다.

## 개발과 검증

다음 상시 규칙을 앞으로 모든 기능 개발·버그 수정에 적용합니다. 사용자 요청의 범위와 A/B 소유권은 유지하며 검증 규칙을 새로운 기능 구현 승인으로 해석하지 않습니다.

현재 기본 화면의 Playwright 브라우저 테스트도 승인된 범위입니다. 실제 서버 연결과 테스트 전용 장애 모의를 구분하며 상품 입력·광고 결과 등 미구현 기능의 성공을 주장하지 않습니다. 실패 스크린샷·trace·video·오류 로그는 Git 제외 artifacts/에 남깁니다. 사용자가 유지 요청한 개발 서버는 테스트 종료 후에도 종료하지 않습니다.

작업 전 기존 파일·Git 상태·더 가까운 AGENTS.md를 검사하고 사용자 변경을 보존합니다. 기능 변경에는 동작을 검증하는 테스트를 포함하며 LLM·네트워크·모델은 fake로 격리합니다. 비용 발생 테스트·모델 다운로드는 별도 opt-in입니다.

검증 대상: factual field 동일성, 네 전략 누락·중복, 사진 원본 보존, 한글·가격 렌더링, 잘못된 LLM JSON, ranking 오류·동점·NaN·누락, 편집 후 재평가, 경로 traversal, 업로드 제한, PNG 저장.

현재 기본 환경 검증 명령입니다. integration 테스트 폴더는 후속 단계에서 추가합니다.

```powershell
.\.venv\Scripts\python.exe -m pytest
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
```

B 테스트는 제공된 절차로 실행할 수 있지만 실패를 고치려고 소유 코드를 수정하지 않습니다. 문서 변경은 링크·근거·스키마 예시·일관성과 `git diff --check`를 검증합니다. 실행하지 않은 테스트를 통과했다고 보고하지 않습니다.

### 기능 완료 검증 절차

1. 변경 기능에 적합한 단위·통합 테스트를 선택해 실행합니다. frontend 관련 TypeScript 검사·build·테스트와 backend pytest·관련 API 테스트를 실행하고 영향 없는 검사를 생략하면 이유를 적습니다.
2. 사용자 화면·흐름 변경은 Playwright 실제 브라우저 검증을 필수로 합니다. 정상 입력·주요 예외·Console/pageerror를 확인하고 모의 응답/Mock 데이터와 실제 API 검증을 분리해 기록합니다. 미구현 기능이나 수행 불가능한 단계는 통과로 보고하지 않습니다.
3. 실패 시 원인을 분석·수정·재실행합니다. 실패 스크린샷·오류 로그는 artifacts/playwright/, 생성 PNG는 artifacts/의 기능별 폴더에 저장합니다. 필요한 trace/video도 남기며 최종 실행 결과와 경로를 보고합니다.
4. 실행 명령·통과/실패/미실행·사용한 환경·남은 한계를 기록합니다. 미실행, 환경 구축 실패, 테스트용 Mock 성공을 실제 서비스 성공으로 바꾸어 보고하지 않습니다.
5. 단순 문서 변경에는 불필요한 브라우저/제품 테스트를 강제하지 않습니다. 링크·규칙 충돌·공백 검사를 사용하고 CI가 PR 전체의 기능 변경을 검증하는 것은 별도로 구분합니다.
6. 외부 서비스 호출·비용 발생 시험은 사전에 사용자 확인을 받습니다. 기본 검증은 로컬/fixture로 격리하고 API 키·민감정보가 Console·로그·스크린샷·GitHub artifact에 노출되지 않도록 입력과 기록을 검토합니다.

### 사용자 확인 환경

- 각 기능 완료 시 필요한 React/FastAPI 서버를 실행하거나 기존 서버를 안전하게 재사용합니다. 실제 HTTP 정상 응답·화면 상태·정확한 localhost 주소를 확인하고 유지 가능한 백그라운드 방식을 우선합니다. 사용자 요청으로 유지 중인 서버·개인 브라우저를 테스트 정리 과정에서 종료하지 않습니다.
- 기존 포트에 다른 프로세스가 있으면 임의 종료하지 말고 해당 서버의 정체·응답을 확인합니다. 개발 서버는 loopback에만 바인딩합니다. Vite HMR을 활용하고 설정·환경 변경으로 재시작이 필요하면 확인 환경이 정상 복구됐는지 검증합니다.
- 가능하면 사용자 컴퓨터의 기본 브라우저에서 결과를 엽니다. 브라우저 실행이 불가능하면 확인한 주소와 필요한 조치를 안내합니다. 문서만 수정했다면 페이지를 불필요하게 새로 열거나 서버를 재시작하지 않습니다.
- 웹사이트 변경은 구현된 내용·사용자가 눌러볼 버튼·입력할 예시·기대 결과를 구체적으로 안내합니다. backend만 변경하면 Swagger UI 또는 시험 가능한 API 경로·요청 예시를 제공합니다. 이미지 생성 변경은 실제 PNG 경로와 미리보기를 제공합니다.
- 실행 실패·누락 패키지·권한·포트 문제를 해결할 수 없으면 원인과 다음 조치를 명시합니다. 프로세스 유지가 전원 종료/재부팅 이후까지 보장된다고 설명하지 않습니다.

### 한국어 완료 보고 형식

모든 작업의 최종 보고에 다음 일곱 항목을 포함합니다. 문서 변경 등 해당 없는 항목도 미실행/해당 없음과 이유를 간단히 적습니다.

1. 이번 구현 기능 또는 설정·문서 변경
2. 자동 테스트 결과: 통과/실패/미실행과 검증 범위
3. Playwright 결과: 실제 실행·Mock/실제 API 구분 또는 미실행 이유
4. 사용자 확인 URL 또는 결과물 경로와 서버 실행 상태
5. 직접 테스트할 구체적인 절차와 기대 결과
6. 알려진 오류·경고·미구현·검증 한계
7. Git 브랜치·commit·push·PR·미병합/검토 상태

자동 테스트 성공은 사용자 최종 검토를 대신하지 않습니다. 결과를 확인할 환경을 준비한 뒤 사용자 검토·명시적 병합 승인을 기다립니다. 수정 요청은 같은 진행 중인 작업 브랜치와 PR에 이어서 반영하며 작은 단위 검증·commit·완료 후 push 규칙을 따릅니다. PR이 외부에서 이미 병합됐다면 상태를 확인해 필요한 새 PR로 분리하고 중복 병합·기록 재작성은 하지 않습니다.

## Git과 완료 보고

- GitHub Flow를 사용합니다. main은 안정적인 통합 브랜치이며 develop 브랜치는 만들지 않습니다. 기능 단위 브랜치 접두사는 feat/, fix/, refactor/, test/, docs/, chore/입니다. 현재 feat/service-foundation은 그대로 유지합니다.
- 먼저 현재 브랜치·Git 상태·원격·기존 PR을 확인하고 같은 작업의 브랜치가 있으면 이어서 사용합니다. 새로운 기능은 기존 작업을 보존·완료한 뒤 별도 작업 브랜치로 분리합니다. 이미 완료한 생성·커밋·push·PR 작업을 중복 실행하지 않습니다.
- Issue 1개→작업 브랜치 1개→PR 1개를 기본으로 합니다. 기존 브랜치·PR이 있으면 재사용하고 필요한 업데이트만 수행합니다.
- 의미 있는 작은 구현 단위마다 관련 테스트를 실행합니다. 실패 원인을 수정하고 테스트가 통과한 단위만 적절한 메시지로 commit합니다. 문서만 변경한 단위는 링크·일관성·공백 검사로 검증합니다.
- Conventional Commits의 type(scope): description 형식과 영어 커밋 메시지를 사용합니다. 타입은 feat, fix, refactor, test, docs, chore, ci 등이며 breaking change는 명시합니다. PR 제목도 같은 형식을 적용합니다. 기존 커밋을 맞추려고 amend/rebase로 기록을 수정하지 않습니다.
- 기능 작업 완료 후 현재 작업 브랜치를 GitHub에 push하고 main 대상 PR을 생성합니다. 기존 PR이 있으면 새 PR 대신 설명·검증 결과를 갱신합니다. 이 절차는 사용자의 지속적인 Git 작업 승인으로 적용하며 별도 commit/push 요청을 다시 요구하지 않습니다.
- main에 직접 commit/push하지 않습니다. 자동 merge는 금지하며 사용자의 검토와 명시적 병합 승인까지 기다립니다.
- 다른 사람의 변경사항을 덮어쓰지 않습니다. force push, main 기록 변경, 저장소 삭제를 금지합니다. 공유·push한 기록의 rebase/amend는 하지 않으며 충돌은 정상 merge 등 기록을 보존하는 방식으로 검토합니다. 기존 브랜치는 승인 없이 삭제하지 않고 자동 merge를 켜지 않습니다.
- `git add .` 대신 파일을 명시하고 API 키·실제 .env·임시 파일·개인정보·비밀·원본·generated output이 commit에 포함되지 않도록 검사합니다. 공개용 .env.example에는 비밀 없는 설정 예시만 둡니다.
- 외부 계정 연결·새 권한 승인은 사용자 확인을 받습니다. 지속적인 Git 승인은 새로운 계정 권한 승인까지 대신하지 않습니다.
- 공용 계약 변경은 A/B 합의 후 version·소비자를 함께 수정합니다. breaking change를 숨기지 않습니다.
- PR 템플릿에 변경 목적·주요 구현·변경 파일·테스트 결과·관련 Issue·화면 변경 시 스크린샷·확인 사항을 기록합니다. 관련 없음/미실행/미첨부는 이유를 적습니다. 템플릿과 초보자 절차는 CONTRIBUTING.md를 따릅니다.
- CI는 backend 테스트, frontend 타입·테스트·build, index 비밀 검사와 PR 제목을 확인합니다. 테스트 실패 원인을 수정·재검증합니다. 스캐너가 모든 비밀·개인정보를 탐지한다고 보장하지 않으며 수동 stage 리뷰도 수행합니다.
- main 보호는 권한·요금제를 확인하고 적용안을 제시한 뒤 사용자 승인 후에만 변경합니다. 지원되지 않으면 강제 보호 미적용 사실을 보고하고 저장소 공개·요금제 변경을 임의 수행하지 않습니다.
- 원본 계획: 최소 주 2회 통합 확인, Week 7부터 짧은 일일 확인 권장.
- 최종 보고는 변경 파일·검증 결과·미확정·실패·후속 작업을 한국어로 작성합니다.
- 두 컴퓨터 전환 시 같은 작업 브랜치의 원격·로컬 상태를 확인하고 시작 전 fetch/pull --ff-only, 종료 전 검증·commit·push·원격 일치를 확인합니다. .env·가상환경·node_modules·업로드는 Git으로 공유하지 않고 각 PC에서 구성합니다. 소스 미커밋/stash는 다른 PC에 전달된다고 가정하지 않습니다. 기본 개발 서버는 loopback(127.0.0.1/localhost)만 바인딩하며 네트워크 공개는 별도 사용자 요청 없이 하지 않습니다.

2026-10-12 최종 조회: protect-main Ruleset이 active이며 main PR 필수·삭제 금지·force push 금지입니다. 승인 리뷰는 0건이고 필수 CI·대화 해결 요구는 없습니다. 이전 요금제 제한 기록과 구분하며 추가 보호 설정은 사용자 승인 후 적용합니다.

## 2인 모델 개발 시작 안내

B의 환경 준비는 docs/MODEL_DEVELOPMENT.md를 따릅니다. 모델 의존성, 하드웨어, 데이터와 함수 계약은 B와 합의하기 전 확정하지 않습니다. 서비스 CI 통과를 모델 평가 검증으로 보고하지 않습니다. A/B 소유권을 유지하고 모델 환경 .venv-ml을 서비스 환경과 격리합니다. 권한 및 main 보호 변경은 사용자 승인 후 수행합니다.

## 현재 승인된 S3 범위

feat/service-image-processing은 rembg/Pillow/OpenCV 전처리, 비교/선택 UI, additive 사진 처리 POST/GET과 사진 선택 PUT을 구현합니다. 원본/facts 보존 및 실패/품질 경고 시 원본 선택을 유지합니다. 광고 재생성 PATCH, 생성/분석/LLM/ranking과 B 코드는 포함하지 않습니다. 모델은 명시적 다운로드만 허용하며 자동 다운로드는 금지합니다. docs/IMAGE_PROCESSING.md의 계약과 검증을 따릅니다.
## 2026-10-28 승인된 S4 사진 분석 범위

feat/service-image-analysis는 선택 상품 사진의 CLIP zero-shot·K-means·비공개 POST/GET photo-analysis·UI를 구현합니다. expected_asset_id 불일치는409이며 원본/facts/선택을 변경하지 않습니다. 현재 사진과 다른 결과는 보존하되 is_current=false로 후속 LLM context에서 제외합니다. 기존 pending/processing/completed/failed 상태를 유지합니다. A 전용 .venv-analysis·offline worker만 사용하고 서비스 .venv/B .venv-ml 및 B ml/ 코드는 변경하지 않습니다. 공식 모델 최초 다운로드는 사용자 승인됐으며 런타임 다운로드는 금지합니다. 모델·사진·벤치마크는 Git 제외입니다. LLM·광고 생성·B ranking 구현은 이 범위에 포함하지 않습니다. 상세 계약/설정은 docs/IMAGE_ANALYSIS.md를 따릅니다.
## 2026-10-28 승인된 S5a 카피 범위와 실제 호출 보류

feat/service-copy는 draft 최상위 product_features(선택 500자/null)·use_address_for_copy(false), POST/GET copy-generation, 네 전략의 copy(headline60/body160/cta30), Mock UI와 테스트를 구현합니다. 기존 Facts/B 계약은 유지하며 PUT의 새 필드 생략은 기존값 보존, 명시적 null/false만 초기화합니다. 사진·입력·특징·주소 옵션/context snapshot으로 최신 여부를 검사하고 stale 카피를 보존하되 렌더링에서 제외합니다. OpenAI adapter 방향은 승인됐지만 **유료/실제 호출은 사용자 요청으로 보류**입니다. 기본 Mock·paid gate=false를 유지하고 새 승인 없이 실제 OpenAI나 무료 대안 API도 호출하지 않습니다. 사진/Instagram은 전송하지 않고 주소는 명시 옵션 true일 때만 전송합니다. 사용자 facts/특징을 CLIP보다 우선하며 실제 검증 미실행을 Mock 통과로 대체하지 않습니다. B 코드/모델·8단계 렌더링/ranking/편집/다운로드는 범위 밖입니다. COPY_GENERATION/COPY_PROVIDER_OPTIONS/COPY_TEST_REPORT를 따릅니다.
