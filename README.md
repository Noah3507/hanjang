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

PowerShell에서 저장소 루트로 이동합니다. 가상환경 activate나 실행 정책 변경 없이 다음을 사용할 수 있습니다.

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

main은 PR로만 변경하고 force push·기록 변경·저장소 삭제를 금지합니다. 현재 Private 브랜치 보호는 요금제 제한으로 미적용입니다. B 초대는 추후 진행합니다. 실제 .env·키·데이터·가중치·joblib·uploads·artifacts·.venv·node_modules를 commit하지 않습니다. Git 상태와 stage diff를 검사하고 파일을 명시하여 stage합니다.

GitHub Flow와 feat/fix/refactor/test/docs/chore 브랜치 이름, 영어 Conventional Commits를 사용합니다. 현재 작업과 기존 커밋·브랜치를 보존하고 develop은 만들지 않습니다. 작은 단위 검증·commit 후 push와 main 대상 PR을 진행합니다. 기존 PR은 재사용하고 제목·본문을 템플릿에 맞춰 갱신합니다. 자동 merge는 하지 않고 사용자 검토·명시적 승인을 기다립니다. 다른 사람의 변경·민감 정보·임시 파일을 보호합니다. [CONTRIBUTING](CONTRIBUTING.md)에 초보자 명령과 보호 설정 승인 절차를 정리했습니다.
