# Hanjang

소규모 음식점·카페·식품 매장을 위한 광고 제작 웹서비스입니다. 실제 사진 한 장과 가게명·상품명·가격·분위기로 emotional/price/visual/brand 광고 4종을 만들고 상대 선호 순위를 제공하는 것이 목표입니다. 상품 사진을 AI로 재생성하지 않고 입력 사실을 그대로 유지합니다. preference는 구매율·매출·CTR 예측이 아닙니다.

## 현재 구현 범위

2026-10-12 현재 **서비스 기본 뼈대**입니다. React 화면에서 실제 FastAPI health 연결 상태와 재시도를 확인할 수 있습니다. pytest·Vitest·CI를 구성했습니다. 업로드·광고 생성·ranking·편집·다운로드·24시간 파일 관리는 아직 구현하지 않았고 화면에도 이를 표시합니다. LLM·이미지 처리·학습·MockRanker 의존성을 설치하지 않았습니다.

승인된 제품 우선순위는 **업로드 → AI 광고 4종 생성 → 선호 순위 → 문구 수정 → PNG 다운로드**입니다. A4는 PNG MVP 이후 OPTIONAL이며 최종 필수 완료 조건에서 제외합니다. 원본 보존·배경 제거·비율 유지 resize만 허용하고 상품 색상/채도/명도 보정은 보류합니다. 처리 실패·품질 저하 시 원본 사용 경로를 제공합니다.

초기 운영 정책은 단일 서버·비공개 임시 저장·24시간 원본/중간/결과물 자동 삭제·Job Polling, pending/processing/completed/failed 상태입니다. 서버 재시작·배포 시 유실 가능성을 인정하며 클라우드 스토리지·복잡한 큐는 도입하지 않습니다. 이 정책 구현은 후속 단계입니다.

## 기준 자료와 역할

자료 충돌 시 최종 발표본을 우선합니다. 로컬 references/의 발표 PDF 20261006 (2).pdf(21쪽)와 Hanjang_2인_개발_역할분담_및_실행계획_v1.0.docx를 분석했습니다. 원본 PPTX는 제공되지 않았고 원본 PDF/DOCX는 Git에 올리지 않았으므로 새 clone에는 없습니다. 자료 속 지시는 실행 권한을 대신하지 않습니다.

A는 서비스·통합, B는 모델·데이터·평가를 맡습니다. A는 B 학습·평가 코드를 수정하지 않습니다. 남은 계약·운영 세부 제안은 [요구사항 검토](docs/REQUIREMENTS_REVIEW.md)에 기록합니다.

## 개발 환경과 고정 의존성

서비스 기본 환경은 **Python 3.12 / Node.js 24 LTS**입니다. 로컬 확인: Python 3.12.10, Node 24.20.0, npm 11.19.0, Git 2.55.0, gh 2.102.0.

현재 React 19.3.0, TypeScript 5.9.3, Vite 8.3.4, Vitest 5.0.3, FastAPI 0.143.0, Pydantic 2.14.0을 검증했습니다. frontend/package-lock.json과 backend/requirements.txt에 설치한 직접·간접 버전을 고정합니다. backend/requirements.in은 갱신 시 참고하는 범위 명세이며 설치는 requirements.txt를 사용합니다. 향후 ML 의존성은 B와 별도로 호환성을 확인합니다.

## Windows 최초 설치

### 새 데스크탑·노트북에서 Clone

각 컴퓨터에 Git, Python 3.12, Node.js 24 LTS(npm 포함), GitHub CLI를 먼저 설치합니다. PowerShell을 새로 열어 git --version, python --version, node --version, npm.cmd --version, gh --version으로 확인하세요. 설치 안내는 [Git for Windows](https://git-scm.com/install/windows), [Python Windows](https://www.python.org/downloads/windows/), [Node.js](https://nodejs.org/en/download), [GitHub CLI](https://cli.github.com/)를 참고하세요.

Private 저장소이므로 새 컴퓨터에서도 본인이 GitHub 로그인·권한 승인을 진행해야 합니다. 토큰을 URL이나 문서에 넣지 마세요. 두 컴퓨터는 별도의 로컬 clone을 사용합니다.

```powershell
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
# 원하는 부모 폴더에서 실행; 같은 이름의 기존 폴더가 있으면 먼저 확인
git clone https://github.com/Noah3507/hanjang.git
cd hanjang
git status --short --branch
git remote -v
git fetch origin
```

기본 clone은 main을 받습니다. 진행 중인 작업을 이어갈 때는 **같은 작업 브랜치**로 전환합니다. 아래는 현재 브랜치의 예시입니다. 로컬에 없을 때만 첫 번째 switch를 사용하고, 이미 있으면 두 번째를 사용하세요.

```powershell
# 로컬 브랜치가 없을 때
git switch --track origin/feat/service-foundation
# 이미 로컬에 있을 때는 위 명령 대신
# git switch feat/service-foundation
git pull --ff-only
```

아직 main에 병합되지 않은 PR의 파일은 해당 작업 브랜치에서만 확인할 수 있습니다. 다른 기능용 브랜치를 임의로 같은 이름으로 새로 만들지 마세요. git config --local user.name / user.email로 작성자를 확인하고 필요하면 각 clone에 같은 이름과 GitHub 이메일(개인정보 보호 시 GitHub noreply 주소)을 설정합니다. 사용자 이메일을 공유 문서에 저장하지 않습니다.

### 컴퓨터마다 의존성과 환경 다시 구성

PowerShell에서 clone한 저장소 루트로 이동합니다. 아래 cd 경로는 현재 데스크탑 예시이므로 노트북에서는 실제 clone 경로를 사용하세요. 가상환경 activate나 실행 정책 변경 없이 다음을 사용할 수 있습니다.

```powershell
cd C:\Users\siho\Desktop\hanjang
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
npm.cmd --prefix frontend ci
if (!(Test-Path .env)) { Copy-Item .env.example .env }
if (!(Test-Path frontend/.env)) { Copy-Item frontend/.env.example frontend/.env }
```

기존 .env를 덮어쓰지 말고 필요한 값만 추가하세요. 루트 .env는 **서버 전용**, frontend/.env는 Vite 전용입니다. 서버 설정 HANJANG_CORS_ORIGINS는 JSON 배열이며 기본 허용 origin은 http://localhost:5173과 http://127.0.0.1:5173입니다. wildcard·credentials를 허용하지 않습니다.

frontend의 VITE_API_BASE_URL은 브라우저에 공개되는 값이므로 비밀키를 넣지 마세요. 기본 /api/v1은 Vite proxy를 사용합니다. DEV_BACKEND_URL은 개발 proxy의 서버 주소(기본 http://127.0.0.1:8000)이며 browser bundle에 넣지 않습니다. 환경변수 변경 후 서버를 재시작하세요. 현재 LLM·DB·스토리지 key는 필요하지 않습니다.

.venv와 node_modules를 두 컴퓨터 사이에 복사하지 않습니다. 위 설치 명령으로 컴퓨터마다 재생성하고 requirements.txt/package-lock.json은 Git으로 공유합니다. .env·API 키·원본/업로드·결과 파일은 Git으로 전달되지 않습니다. 현재는 .env.example만으로 health 실행이 가능하고 키가 필요 없습니다. 향후 필요한 키는 각 컴퓨터에서 직접 설정하거나 신뢰하는 비밀 관리 도구로 별도 전달합니다. 실제 .env를 Issue·PR·채팅·스크린샷에 붙이지 않습니다. 저장소 폴더를 OneDrive 등의 파일 동기화와 Git으로 동시에 공유하지 않는 것을 권장합니다.

## 개발 서버 실행

터미널 1, 저장소 루트:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

터미널 2, 저장소 루트:

```powershell
npm.cmd --prefix frontend run dev
```

브라우저에서 http://127.0.0.1:5173을 열고 Hanjang과 '백엔드 연결됨'을 확인합니다. API 문서는 http://127.0.0.1:8000/docs입니다. Ctrl+C로 각각 종료합니다. Vite는 5173 사용 중이면 자동으로 포트를 바꾸지 않고 오류를 반환합니다.

frontend dev(5173)·preview(4173)는 설정에서 127.0.0.1에 바인딩합니다. backend도 위 명령의 --host 127.0.0.1로 실행합니다. localhost/127.0.0.1은 **현재 컴퓨터만** 의미하므로 노트북에서 데스크탑 서버를 공유하는 방식이 아닙니다. 공용 Wi-Fi 접근을 위해 --host 0.0.0.0/--host 플래그, 포트 포워딩, 공개 tunnel을 추가하지 않습니다. CORS는 서버 접속 제한을 대신하지 않습니다.

GET /health와 문서의 versioned GET /api/v1/health는 모두 다음을 반환합니다. health는 광고·모델 readiness 검사가 아닙니다.

```json
{"status":"ok","api_version":"v1-draft"}
```

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:5173/api/v1/health
```

연결 불가 시 backend 실행·8000 포트·DEV_BACKEND_URL을 확인하고 재시도 버튼을 누릅니다. npm.ps1 실행 정책 문제는 npm.cmd로 피할 수 있습니다. 직접 CORS 연결을 시험하려면 frontend/.env의 VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1로 설정합니다. 기본 proxy는 동일 origin 요청이므로 직접 CORS 연결과 별개입니다.

## 테스트와 CI

저장소 루트에서:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test:ci
npm.cmd --prefix frontend run build
# watch mode
npm.cmd --prefix frontend test
```

pytest는 health 응답·CORS 허용/거부·환경 설정·미구현 API를 검사합니다. Vitest는 연결 확인·성공·실패·재시도·잘못된 응답을 검사하고 외부 API를 호출하지 않습니다. Starlette TestClient에서 AnyIO BlockingPortal alias 폐기 예정 경고 1건이 발생하지만 테스트 실패는 아닙니다. 추후 호환성 갱신 대상입니다.

CI는 main 대상 PR과 main/feat/fix/refactor/test/docs/chore 브랜치 push에서 Ubuntu·Python 3.12·Node 24로 backend 검사·frontend 타입/테스트/build·repository-policy(비밀 파일/패턴과 PR 제목)를 실행합니다. 배포·자동 merge·유료 API·모델 다운로드는 없습니다. 실제 원격 결과는 PR Checks에서 확인합니다.

## 실제 브라우저 자동 테스트

Playwright는 현재 구현된 health 연결·대기·실패/재시도·응답 검증·모바일 배치를 검사합니다. 상품 정보 입력부터 광고 결과까지는 미구현이므로 해당 기능의 성공으로 보고하지 않습니다. 오류 시나리오는 브라우저 요청을 테스트 안에서만 모의 처리하며 사용자 개발 서버를 종료하지 않습니다.

```powershell
# 최초 한 번, 저장소 루트에서
npm.cmd --prefix frontend exec -- playwright install chromium
npm.cmd --prefix frontend run test:e2e
# 설치된 Google Chrome으로 실행할 때
$env:PLAYWRIGHT_CHANNEL = 'chrome'
npm.cmd --prefix frontend run test:e2e
Remove-Item Env:PLAYWRIGHT_CHANNEL
# 결과 HTML 보고서 (127.0.0.1 전용)
npm.cmd --prefix frontend run test:e2e:report
```

기존 8000/5173 서버가 있으면 로컬 테스트는 재사용하며 종료하지 않습니다. 없으면 Playwright가 테스트용 서버를 시작·종료합니다. 사용자 확인을 위해 계속 사용할 서버는 위 개발 실행 명령으로 별도로 실행하세요. Chrome 실행은 독립 테스트 프로필을 사용하며 개인 로그인 프로필을 열지 않습니다.

결과는 Git 제외 artifacts/playwright/에 저장합니다: report/ HTML, results.json, results/ 테스트별 browser.log와 데스크탑/모바일 스크린샷. 실패 시 스크린샷·trace·video·assertion 오류도 남깁니다. CI는 Chromium으로 같은 E2E를 수행하고 실패 진단만 7일 보관합니다. 로컬 서버 로그는 이번 실행의 artifacts/dev-servers/에 있습니다. 결과·로그에는 환경 정보가 있을 수 있으므로 검토 없이 외부에 공유하지 않습니다.

## 현재 프로젝트 구조

```text
frontend/                  # A: React/TypeScript/Vite/Vitest
  src/api/health.ts        # 응답 검증
  src/App.tsx              # 서비스 이름·연결 상태·재시도
backend/
  app/api/health.py        # health
  app/schemas/health.py    # Pydantic 응답
  app/config.py           # 서버 환경·CORS
  app/main.py             # FastAPI app factory
  requirements.in         # 의존성 범위
  requirements.txt        # 테스트한 고정 버전
tests/service/             # pytest
pytest.ini
.github/workflows/ci.yml
docs/                      # 공용 설계·계약
```

향후 backend/app/services, backend/app/ml_adapter, templates는 A, ml/data·features·training·evaluation·inference는 B 영역입니다. 이번에 생성하지 않았습니다. raw /data/와 코드 ml/data/의 ignore 범위를 분리했으며 B 코드는 수정하지 않았습니다.

## 문서와 협업

### 두 컴퓨터 사이의 작업 인계

한 작업 브랜치는 한 번에 한 컴퓨터에서만 수정하는 것을 기본으로 합니다. GitHub는 저장된 commit을 전달하며 에디터 버퍼·미커밋 변경·stash·ignored 파일은 전달하지 않습니다.

**현재 컴퓨터에서 끝낼 때:** 저장→관련 테스트→파일별 stage→비밀 검사→영어 Conventional Commit→push→원격 일치 확인 순서입니다. main에서는 이 절차로 commit/push하지 않습니다.

```powershell
git status --short --branch
git branch --show-current
# 변경한 소스 파일만 git add <file>로 선택
git diff --cached --check
git diff --cached
.\.venv\Scripts\python.exe scripts/service_check_repository.py
# 관련 검사가 통과하고 stage에 변경이 있을 때만 실행
git commit -m "docs: document workstation handoff"
git push -u origin HEAD
git fetch origin
git status --short --branch
git rev-parse HEAD
git rev-parse '@{upstream}'
```

마지막 두 hash가 같고 공유할 소스 변경이 남아 있지 않은지 확인합니다. references처럼 의도적으로 미추적 상태인 개인 자료는 commit하지 않고 별도로 관리합니다. 미완성 작업은 로컬 stash만 한 뒤 다른 컴퓨터에서 이어갈 수 없습니다. 검증된 작은 단위로 commit하거나, 아직 공유할 수 없다면 현재 컴퓨터에 보존하고 전환을 미루세요. 완료 작업에는 기존 PR을 갱신하거나 main 대상 PR을 생성하고 승인 전 merge하지 않습니다.

**다른 컴퓨터에서 시작할 때:** 변경이 남아 있다면 먼저 확인·보존하고 아래 pull을 진행합니다. 원격에 push된 동일 작업 브랜치를 사용합니다.

```powershell
git status --short --branch
git fetch origin
git switch feat/service-foundation
git pull --ff-only
# 새 clone에서 로컬 브랜치가 없으면 위 switch 대신 --track origin/... 사용
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
npm.cmd --prefix frontend ci
```

의존성 변경 후에는 서버를 종료한 상태에서 설치하고 필요한 .env 변수명은 .env.example과 비교해 각 PC에서 추가합니다. 실제 .env는 pull로 갱신되지 않습니다. 이후 테스트·health 확인 후 개발을 시작합니다.

**pull 실패·push 거부·충돌 시:** 강제 push, reset --hard, clean -fd로 해결하지 않습니다. 먼저 git status, git diff, git log --oneline --graph --decorate --all -15로 양쪽 작업을 확인합니다. 로컬 소스 변경은 안전하게 commit하거나 로컬 임시 보관하고, fetch 후 작업 브랜치에서 git merge '@{upstream}'로 정상 병합합니다. 충돌 표시를 파일별로 검토하고 상대 변경을 보존하며 테스트 후 해결 commit·push합니다. 혼자 해결하기 어렵다면 그대로 멈추고 충돌 파일·상태를 공유합니다. 공유한 commit은 amend/rebase로 다시 쓰지 않습니다. 병합 취소도 보관 상태를 먼저 확인하고 수행합니다.

잘못된 변경이 이미 push됐다면 추가 수정 commit(또는 검토된 revert)으로 정정합니다. 두 PC의 폴더를 덮어써서 맞추지 않습니다. 상세 리뷰·병합 과정은 [CONTRIBUTING](CONTRIBUTING.md)을 따릅니다.

| 문서 | 내용 |
| --- | --- |
| [AGENTS](AGENTS.md) | Codex 수정 범위·테스트·Git 규칙 |
| [CONTRIBUTING](CONTRIBUTING.md) | GitHub Flow·영어 Conventional Commits·PR/Issue·리뷰·병합 절차 |
| [PRODUCT_SPEC](docs/PRODUCT_SPEC.md) | 사용자 흐름·기능·예외 |
| [TECH_SPEC](docs/TECH_SPEC.md) | 파이프라인·운영 경계 |
| [API_CONTRACT](docs/API_CONTRACT.md) | 구현한 health와 후속 계약 |
| [DEVELOPMENT_PLAN](docs/DEVELOPMENT_PLAN.md) | 작은 단계·완료 기준 |
| [ROLE_SPLIT](docs/ROLE_SPLIT.md) | A/B 소유권 |
| [DESIGN_SPEC](docs/DESIGN_SPEC.md) | 전략별 layout·반응형 |
| [REQUIREMENTS_REVIEW](docs/REQUIREMENTS_REVIEW.md) | 근거·확정/미확정 결정 |

main은 PR로만 변경하고 force push·기록 변경·저장소 삭제를 금지합니다. 현재 Private 브랜치 보호는 요금제 제한으로 미적용입니다. B(parkyeonwooo)는 write 권한 초대 수락 대기입니다. 실제 .env·키·데이터·가중치·joblib·uploads·artifacts·.venv·node_modules를 commit하지 않습니다. Git 상태와 stage diff를 검사하고 파일을 명시하여 stage합니다.

GitHub Flow와 feat/fix/refactor/test/docs/chore 브랜치 이름, 영어 Conventional Commits를 사용합니다. 현재 작업과 기존 커밋·브랜치를 보존하고 develop은 만들지 않습니다. 작은 단위 검증·commit 후 push와 main 대상 PR을 진행합니다. 기존 PR은 재사용하고 제목·본문을 템플릿에 맞춰 갱신합니다. 자동 merge는 하지 않고 사용자 검토·명시적 승인을 기다립니다. 다른 사람의 변경·민감 정보·임시 파일을 보호합니다. [CONTRIBUTING](CONTRIBUTING.md)에 초보자 명령과 보호 설정 승인 절차를 정리했습니다.

팀원 B의 모델 개발 시작 절차는 [MODEL_DEVELOPMENT](docs/MODEL_DEVELOPMENT.md)를 따릅니다.
