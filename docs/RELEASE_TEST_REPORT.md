# 13단계 로컬 릴리스 검증 (2026-11-02)

## 최종 보완: 조사와 기존 다운로드 검사

- 추가 유료 호출·발표 서버 재시작·외부 공개 없음. 기존 원장7건·$0.01102125 보존, 누적 제한10회/$0.10. B 코드·환경·모델·사용자 다운로드 보존.
- prompt version `copy-v3-particles`, 중립 문형 지시, 치환 후 최종 가격/상품명 경계 조사 검사 추가. 명확한 오류/발음 불확실은 별도 safe code·자동 재시도 없음. facts를 고치거나 미승인 재생성하지 않음.
- 무료 backend130 PASS, frontend68 PASS, 타입·빌드 PASS. 조사 오류·직접 인용·ㄹ 예외·불확실 발음·유효 결합·세 필드·원문 보존·재시도 방지 포함. Playwright 합성 조사 오류1 PASS: 오류 표시·가격 원문·렌더링 비활성화·copy POST는 브라우저에서 대체. 최초 fixture asset 불일치로 엄격 locator 오류가 발생해 실제 요청 asset에 맞춘 후 재실행. 전체 실제 광고 생성 흐름은 다시 실행하지 않음.
- 기존 사용자 PNG:1080×1350 RGB, verify/load 성공. 서버 저장 PNG와 SHA-256 일치. PDF:strict 구조 검사·1페이지 A4 약210×297mm·PDFium 실제 렌더링 성공. 내장 이미지1080×1350의 모든 RGB 픽셀이 다운로드 PNG와 동일. PDF는 여백/비율 축소 후 같은 내용을 표시하며 searchable/vector PDF로 주장하지 않음.
- 로컬 PNG와 렌더링 PDF에서 요청된 편집 제목의 글자 반영을 육안 확인. 긴 상품명과 본문의 단어 중간 줄바꿈도 확인. 다운로드 시점r2 파일/저장 asset 일치는 확인했지만 현재 메모리의 최신 후보 JSON은 소유 세션 없이 조회할 수 없어 별도 대조가 남음. 인증 우회·브라우저 프로필 추출·Chrome Computer Use 재시도 없음.
- PDF 검사 도구는 Git 제외 별도 `artifacts/release/file-review-tools-20261102`에 설치했으며 기존 가상환경을 변경하지 않음. 실제 사용자 파일·이미지·연락처·asset 식별자는 Git/CI artifact에 올리지 않음.
- 결과는 로컬 `artifacts/release/final-file-review-20261102/`의 렌더링 PNG·report.json·테스트 로그에 보존. 구체적인 사용자 제목/파일 대조 정보는 로컬과 완료 보고에서만 제공.
- 14단계 작업 후보는 [PHASE_14_BACKLOG](PHASE_14_BACKLOG.md)에 기록. 템플릿/디자인/폰트 변경은 이번 범위 아님. 최신 PR CI는 후속 commit의 Actions 결과 참조.

## 후속: OpenAI 발표 설정 준비 (추가 유료 호출 미승인)

- 기본6회 유지, 명시적 누적 호출 상한10 지원. 예산0.10/기존 원장 유지. 발표 wrapper는 모델 고정·재시도0·provider/paid/max_requests를 자식 환경에 적용하고 종료 후 복원합니다.
- 기존 원장 6건·$0.00906225의 준비 전후 SHA-256을 대조합니다. 실제 원장은 테스트 fixture로 사용하거나 수정하지 않습니다.
- 새 `artifacts/release/presentation-openai-20261102.json` 및 별도 preflight 설정 생성. 기존 `.env`/local-actual.json/모델/환경/transfer 보존.8014 Mock 서버는 중단·재시작하지 않습니다.
- CheckOnly: OpenAI·gpt-5.4-mini-2026-03-17·paid=true·누적10·예산0.10·재시도0 준비 확인. 실제 호출 아님.
- 실제 브라우저 preflight: 임시8018, 외부 네트워크 차단, 카피 생성 POST0, 합성 사진/상품 저장 후 pending 상태의 OpenAI 모델명 표시 확인. 유료 전체 흐름은 미실행입니다.
- `release.spec.ts`는 기본 Mock이며 server provider가 다르면 생성 전에 중단합니다. 실제 카피 경로는 별도 승인 플래그 필요, copy 생성 POST 최대1회, 기존 PNG4/실제 순위/진단/편집/다운로드 흐름을 재사용합니다.
- 합성 원장·fake SDK 검사로 6건 보존·추가4회·11번째 차단·별도 예산 제한·재시도0 검증. 관련 backend101 PASS, frontend67 PASS, 타입/빌드 PASS. OpenAI 표시-only preflight1 PASS, 기존8014 Mock카피+실제 모델 전체 흐름1 PASS. 유료 OpenAI 전체 흐름은 미실행입니다. CI는 PR #51 후속 commit의 Actions 결과를 참고합니다.
- 임시8018 서버 종료 후 실제 원장 SHA-256 동일, 6건·$0.00906225 유지 확인. 기존8014 ready·Mock 유지 확인. 현재 서비스의10회/OpenAI 설정 적용은 아직 하지 않았습니다.
- 로컬 근거: `artifacts/release/presentation-preparation-tests.log`, `browser-openai-preflight-20261102/`, `browser-preparation-mock-20261102/`, `ledger-before-preparation-20261102.json`. 비밀·원본·로그는 Git 제외.

아래는 최초13단계 릴리스 검증 이력입니다. 후속 준비 작업을 실제 유료 E2E 성공으로 해석하지 않습니다.

## 범위와 환경

`cb71c09` 최신 main에서 `feat/service-release` 생성. PR #49 병합 상태 확인 후 fetch/ff-only 확인. 기존 브랜치·worktree·transfer·모델·`.env`·가상환경 보존. B 소유 파일 변경 없음. Windows, Python 3.12, Node24, 기존 서비스/분석/rank 환경과 Chromium 재사용. Docker/WSL/cloudflared 미설치, 이번에 설치하지 않음.

이번 릴리스는 **배포 준비와 로컬 검증**입니다. 실제 HTTPS 공개 및 실제 OpenAI 유료 smoke는 사용자 조건에 따라 미실행입니다. 13단계 전체 공개 배포 완료라고 보고하지 않습니다.

## 구현

- `scripts/service_presentation.ps1`, `service_serve.py`: built frontend와 API 단일 origin·loopback·단일 worker, 서버 환경만 설정. 기존 누적 비용 원장 재사용. 모델·환경 자동 설치/다운로드 없음.
- `presentation.py`: origin 전체 Basic 인증, 전체/쓰기/실패 인증의 rolling60초 제한, 교차 Origin 쓰기 차단·보안 헤더. 기존 Job/session 계약 유지.
- `/ready`: 파일·Node/Chromium·폰트·저장소·카피 설정 준비 검사, 30초 캐시. 설정 검사와 실제 추론을 분리. 경로/키 비노출.
- TTL: 잠긴 파일 때문에 다른 만료 파일이 굶지 않도록 정리 계속, 경로 없는 경고·503 후 재시도. 활성 추론 snapshot 보호, 새 전용 마커의 24시간 지난 파일만 정리. 알 수 없는 파일·이전 unmarked 디렉터리 보존.
- 유료 smoke는 기존 provider/validator/누적 원장 재사용, 기본은 계획 출력만. 원격 read-only smoke도 별도 opt-in, 인증정보 포함 URL과 redirect 차단.
- 기존 CI 4개 유지 + 모델 다운로드 없는 authenticated built UI job 추가. 공개·유료 호출 없음.

## 실행 결과

| 검사 | 결과·범위 |
| --- | --- |
| backend 전체, 렌더러/실제 B opt-in | 최종 420 PASS, 실패0/skip0, 332.13초; Starlette/anyio deprecated alias 경고1 |
| release/실행 guard/업로드 대상 검사 | 35 PASS (후속 fake smoke 추가 전) |
| frontend 단위 | 67 PASS / 15 files |
| TypeScript·production build | PASS |
| 기존 Playwright | 30 PASS, opt-in 실제 모델/발표 2 SKIP, 실패0 |
| authenticated built UI, 실제 모델3종 | 1 PASS, Mock 카피, 실제 사진, 네 PNG·순위·편집·다운로드·모바일 |
| 최종 서버 재시작 후 실제 모델3종 | 별도 1 PASS, 최신 코드 로딩·전체 흐름 재확인 |
| authenticated built UI, 모델 없음 | 1 PASS, rembg/CLIP fallback·Mock 순위 표시 명시; 실제 모델 성공으로 계산하지 않음 |
| 실제 B fixture·cache benchmark | 1 PASS, 가중치/기준 score 오차 허용 범위, 역순 후보 매핑·모델 1회 로딩 |
| 단일 호출 smoke guard | 7 PASS, 기존 provider factory에 fake 주입; 유료 요청0 |
| pip check·repository policy·diff check·문서 로컬 링크 | PASS (최종 stage 후 재확인) |
| 정적 번들 검사 | 파일3개, 실제 서버 key 값 비포함·흔한 secret 패턴 없음 |
| 실제 유료 API / Tunnel·공개 URL | 미실행: 별도 승인 필요 |
| 신규 Windows 완전 신규 설치 | 미실행: 기존 가상환경 보존·재사용 검증 |
| CI Linux 신규 설치 | PR CI에서 판정. 모델 없는 fresh clone 검증이며 Linux 실제 ML 성공이 아님 |

첫 backend 실행은 `--basetemp` 상위 경로 누락으로 274 setup error/138 PASS였고 경로 생성 후 재실행했습니다. 첫 발표 검사는 Playwright config 미적용(Invalid URL), 다음 검사는 기존 명시적 ‘저장 정보 다시 조회’ 단계 누락으로 실패했습니다. 별도 포트 회귀 첫 시도는 Vite proxy가 기본8000을 가리켜 중단했고 config에서 backend 포트와 연결했습니다. 해당 오류와 로그는 보존하고 최종 재실행과 구분합니다.

실제 E2E는 상품명·가격 원문, rembg 처리본 표시/선택, 원본 복귀, CLIP 실제 단서/대표색, Mock 카피, 실제 Chromium 4개 PNG, 모델 source/version·후보 ID/revision·내림차순 score/1~4위, 진단 분리, 편집 후 이전 순위 숨김·재계산, PNG/PDF, 새로고침 후 명시적 조회, 375px 넘침 없음, console/pageerror를 확인했습니다. 편집 PNG는 RGB1080×1350으로 별도 확인했습니다. 기존 회귀의 API 오류·stale·만료·권한·편집 실패 모의 검사는 실제 API 정상 경로와 구분됩니다.

로컬 결과: `artifacts/release/browser-actual-final/`, `browser-ci-local/`, `browser-regression-final/`, `backend-tests.log`, `backend-final.log`, `model-benchmark.log`, `process-memory.json`, `bundle-security.json`. 이미지·로그·토큰·설정은 Git에 넣지 않습니다. 실제 서버 재시작 후 최종 결과는 별도 `browser-actual-restarted/`에 보존합니다.

## 모델·비용·성능

- rembg: resource root의 `artifacts/models/rembg/u2netp.onnx`.
- CLIP: `artifacts/models/analysis/ViT-B-32.pt`, Windows TorchScript는 검증된 `%LOCALAPPDATA%/HanJang/model-links/<tag>/ViT-B-32.pt` junction 사용.
- B: `artifacts/models/ranking/bt-logistic-v1/model.safetensors`와 기존 manifest/관련 파일. B `load_model/rank_ads` 그대로 사용.
- 실제 상품 PNG의 초기 score: price -1.1534828598447122, visual -1.272531617524746, emotional -1.4995509213600162, brand -1.7345923428478727. 후보·문구가 바뀌면 점수도 달라지며 확률·성과/객관적 품질 보증이 아닙니다.
- 별도 B fixture 측정: 로딩1.144초, 첫 추론0.530초, warm0.321초, 모델 load count1, worker peak1250.3MiB. 이전 Windows20회 benchmark 중앙값0.344/p950.4298초와 **표본 수·동시 작업 조건이 달라 직접 성능 개선으로 주장하지 않습니다**.
- 전체 흐름 뒤 프로세스 관측: backend98.5MiB, 두 모델 Python935/1280MiB, Python launcher/console 포함 현재 합계 약2.3GiB. 개별 peak214.5/1250/1296.5MiB는 서로 다른 시점의 값이며 동시 총 peak가 아닙니다. 렌더링 Chromium/rembg 일시 peak와 OS·다른 앱은 별도 여유가 필요합니다. 최소 사양 보증은 아니며 발표 노트북에서 여유 RAM/디스크를 다시 확인하세요.
- 유료 호출0, 모델 다운로드0, 클라우드 리소스0. `service_openai_smoke.py` 계획 출력: 최대1회·재시도0·예약 상한$0.013716. 실제 계정/응답 품질은 미검증입니다. fake SDK 테스트를 실제 API 성공으로 보고하지 않습니다.

## 재현

README 설치 후 기존 모델·세 환경을 설정합니다. `.env`를 덮어쓰지 않습니다.

```powershell
$env:RUN_RENDER_TESTS='1'; $env:RUN_RANKING_TESTS='1'
# 새 경로의 상위 폴더를 먼저 준비하고 기존 basetemp를 재사용하지 않습니다.
.\.venv\Scripts\python.exe -m pytest -q --basetemp artifacts/release/backend-new-run
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test -- --run
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe scripts/service_openai_smoke.py
# DEPLOYMENT의 비밀번호·ConfigFile 설정으로 발표 서버8014 실행 후:
.\.venv\Scripts\python.exe scripts/service_deploy_smoke.py
$env:PLAYWRIGHT_EXTERNAL_SERVER='1'; $env:PLAYWRIGHT_FRONTEND_PORT='8014'
$env:PLAYWRIGHT_RELEASE='1'; $env:PLAYWRIGHT_RELEASE_MODELS='1'
# 허가된 실제 사진 선택 가능. 미지정 시 synthetic 상품을 만듭니다.
# $env:PLAYWRIGHT_RELEASE_SAMPLE='C:/path/to/approved-product.png'
npm.cmd --prefix frontend run test:e2e -- release.spec.ts --reporter=list --output=../artifacts/release/browser-new-run
```

일반 개발 회귀에서는 위 presentation flag를 제거하고 별도 포트/저장소를 사용합니다. 이번 발표 서버는 `http://127.0.0.1:8014`에 유지하며 인증 필요합니다. 테스트용 비밀번호는 Git 제외 로컬 `artifacts/release/test-credentials.json`에만 보관합니다. 실제 발표 전 사용자 고유 비밀번호로 실행하세요. 다른 기존 서버는 종료하지 않았습니다.

## 제약과 후속 승인

Windows clean install, Linux 실제 모델, 외부 HTTPS 접근·Tunnel 종료·외부 제한, 실제 OpenAI smoke는 미검증입니다. CI 통과와 로컬 성공은 이를 대체하지 않습니다. Job·세션은 재시작 시 유실, 단일 프로세스 공유 rate limit/Basic 비밀번호 한계, 오래된 unmarked snapshot 수동 검토, 절전/인터넷 단절을 유지합니다. Figma/타이포그래피/광고 디자인 고도화는 미구현·범위 밖입니다. 외부 공개와 유료 smoke는 이 로컬 결과를 리뷰한 뒤 별도 승인합니다. main 자동 병합하지 않습니다.
