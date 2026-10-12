# Hanjang 협업 안내

## 기본 원칙

[GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow)를 사용합니다. main은 검증된 변경을 모으는 안정적인 통합 브랜치이며 작업은 기능별 브랜치와 PR에서 진행합니다. develop 브랜치는 만들지 않습니다. 기존 브랜치와 커밋은 보존합니다. 현재 업로드 작업은 feat/service-upload와 PR #8에서 진행 중입니다.

A는 서비스·통합, B는 모델·데이터·평가를 담당합니다. A는 B의 학습·평가 코드를 수정하지 않습니다. 모델 연결은 [API_CONTRACT](docs/API_CONTRACT.md)와 공동 합의된 인터페이스를 따릅니다. [AGENTS](AGENTS.md)의 사진·사실 보존 규칙도 적용합니다.

## 1 작업 시작 전 확인

데스크탑·노트북을 전환하는 절차는 [README의 두 컴퓨터 인계 안내](README.md#두-컴퓨터-사이의-작업-인계)를 따릅니다. 시작 전 같은 브랜치를 fetch/pull --ff-only하고 종료 전 검증한 작은 commit을 push합니다. 한 브랜치를 동시에 두 컴퓨터에서 수정하지 않습니다. 미커밋·stash·.env·가상환경·node_modules는 원격에 전달되지 않으며 각 컴퓨터에서 환경을 재구성합니다.

저장소 루트에서 실행합니다.

```powershell
git status --short --branch
git branch --show-current
git remote -v
gh pr list --state open
git fetch origin
```

현재 브랜치가 같은 작업의 진행 중인 브랜치이면 그대로 사용합니다. 새 브랜치·PR을 중복 생성하지 않습니다. 미커밋 변경을 먼저 읽고 타인의 파일을 덮어쓰거나 reset으로 없애지 않습니다. 서로 다른 기능은 기존 작업을 완료·보존한 다음 분리합니다.

기존 작업과 무관한 **새 기능**을 시작하고 작업 폴더가 깨끗할 때만 다음을 사용합니다. 진행 중인 기존 작업에서는 실행하지 않습니다.

```powershell
git switch main
git pull --ff-only origin main
git switch -c feat/product-upload
```

pull --ff-only가 실패하면 임의 reset·force push로 해결하지 말고 분기·변경 내용을 확인합니다. 공유·이미 push한 커밋은 rebase/amend로 다시 쓰지 않습니다. 작업 브랜치에 최신 main이 필요하면 변경을 저장한 뒤 git merge origin/main으로 정상 통합하고 충돌 파일을 리뷰·테스트합니다.

## 2 브랜치와 커밋 이름

브랜치는 소문자와 하이픈으로 목적을 설명합니다.

| 접두사 | 용도 | 예 |
| --- | --- | --- |
| feat/ | 기능 | feat/product-upload |
| fix/ | 오류 수정 | fix/health-timeout |
| refactor/ | 동작 유지 구조 개선 | refactor/ranking-adapter |
| test/ | 테스트 | test/upload-validation |
| docs/ | 문서 | docs/api-contract |
| chore/ | 설정·의존성·CI | chore/team-workflow |

[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) 형식으로 **영어 커밋 메시지**를 작성합니다.

```text
type(optional-scope): short English description

feat(upload): validate product image inputs
fix(api): handle health request failures
refactor(renderer): separate template context
test(api): cover rejected CORS origins
docs: document Windows setup
chore: update development dependencies
ci: validate pull request titles
```

허용 타입은 feat, fix, refactor, test, docs, chore, ci, build, perf, style, revert입니다. breaking change는 type(scope)!: 및 BREAKING CHANGE 설명으로 알리고 API version·소비자 영향을 공동 합의합니다. 기존 커밋의 형식을 맞추려고 기록을 수정하지 않습니다.

## 3 작은 단위 구현과 검증

Issue에 목적·범위·완료 기준을 먼저 적고 의미 있는 작은 단위로 작업합니다. 변경과 관련된 테스트가 통과한 후 해당 단위를 commit합니다. 실패하면 원인을 확인·수정하고 다시 검사합니다. 문서만 수정한 단위는 링크·내용 일관성·공백 검사로 확인합니다.

기능 코드의 기본 검증 명령은 다음과 같습니다. 서버나 유료 API는 필요하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test:ci
npm.cmd --prefix frontend run build
git diff --check
```

실행하지 않은 검사를 통과했다고 기록하지 않습니다. B 테스트 실패를 고치려고 A가 B 코드를 변경하지 않습니다. 모델 문제는 재현 조건·계약 위반 내용을 B에게 전달합니다.

## 4 선택해서 stage하고 commit

```powershell
git diff
git add frontend/src/App.tsx frontend/src/App.test.tsx
git diff --cached --check
git diff --cached --stat
git diff --cached
.\.venv\Scripts\python.exe scripts/service_check_repository.py
git commit -m "fix(ui): clarify backend connection status"
```

위 파일명은 예시이며 실제 변경 파일만 명시합니다. git add .는 피합니다. 저장소 검사는 Git index에 올라간 파일명과 내용을 검사하며 **키 값을 출력하지 않습니다**. .env는 제외하고 .env.example은 비밀 없는 예시만 허용합니다. API 키·개인정보·임시 파일·가중치·사용자 업로드·원본 자료를 commit하지 않습니다. .gitignore는 추적 중인 파일을 제거하지 않으므로 stage 내용을 직접 확인합니다.

검사는 흔한 비밀 패턴을 찾는 보조 장치이며 모든 개인정보·비밀 탐지를 보장하지 않습니다. 실수로 비밀을 공유하면 먼저 키를 폐기·재발급하고 사용자에게 알립니다. 이 규칙을 우회하려고 기존 기록을 임의 변경하지 않습니다.

## 5 push와 PR

작업이 완료되면 **현재 작업 브랜치만** push합니다.

```powershell
git push -u origin HEAD
gh pr list --head feat/product-upload --state open
```

동일 작업 PR이 없을 때 main 대상 PR을 생성합니다. 있으면 새 PR 대신 기존 설명을 갱신합니다. GitHub에서 PR을 생성하면 [PR 템플릿](.github/PULL_REQUEST_TEMPLATE.md)을 채우고 제목도 Conventional Commits 형식(예: feat: add product image upload)으로 작성합니다. PR 본문은 한국어로 작성해도 됩니다.

변경 목적·주요 구현·변경 파일·테스트 명령과 결과·Issue·화면 변경 시 스크린샷·확인 사항을 적습니다. 스크린샷에 키·개인정보를 넣지 않습니다. 화면 변경이 없으면 해당 없음, 미첨부면 미첨부 이유를 적습니다. .github/ISSUE_TEMPLATE에는 기능·버그·모델 연동 양식을 제공합니다. Issue 양식은 기본 브랜치에 병합된 후 GitHub에서 표시됩니다.

## 6 CI와 리뷰

모든 기능·버그 수정은 [AGENTS의 상시 검증 및 사용자 확인 규칙](AGENTS.md#개발과-검증)을 적용합니다. 관련 단위/통합·frontend 타입/build/테스트·backend pytest/API를 실행하고, 화면·흐름 변경은 실제 Playwright로 정상/예외·Console을 검증합니다. 실패 진단은 artifacts/에 저장하며 Mock과 실제 API 결과를 구분합니다. 비용이 드는 외부 시험은 사전 확인합니다. 단순 문서는 링크·일관성·공백 검사로 검증하고 불필요한 로컬 브라우저 실행을 강제하지 않습니다.

완료 시 필요한 localhost 서버를 유지·정상 응답 확인하고 URL/Swagger/PNG와 직접 확인 방법을 안내합니다. 결과를 한국어 일곱 항목(구현, 자동 테스트, Playwright, URL/경로, 직접 확인법, 알려진 문제/미구현, Git 상태)으로 보고합니다. 사용자 승인 전 merge하지 않으며 수정은 동일 진행 브랜치·PR에서 이어갑니다.

main 대상 PR과 여섯 종류 작업 브랜치 push에서 CI가 실행됩니다. backend는 pip check·pytest, frontend는 타입·Vitest·build, repository-policy는 비밀 파일/패턴·PR 제목 형식을 검사합니다. browser-e2e는 Playwright로 실제 연결과 장애 모의를 검증합니다. ML 전용 CI는 아직 없습니다. PR 제목 수정도 제목 검사를 갱신합니다. 읽기 전용 token이며 자동 배포·자동 merge를 수행하지 않습니다.

CI 실패 시 Checks 로그를 확인하고 원인 단위를 수정·테스트·추가 commit·push합니다. PR 제목 오류는 제목을 수정하며 과거 commit을 다시 쓰지 않습니다. CI가 통과해도 사용자 검토·병합 승인을 대신하지 않습니다.

리뷰에서는 범위·테스트·API 호환성·원본/사실 보존·민감 정보·A/B 소유권을 확인합니다. main에 직접 commit/push하지 않습니다. **사용자의 명시적 승인 뒤에만** PR을 수동 병합합니다. 병합 방식은 승인 때 결정하며 자동 merge는 켜지 않습니다. 병합 후에도 기존 브랜치를 자동 삭제하지 않습니다. 브랜치 삭제 등 파괴적 작업은 별도 사전 승인이 필요합니다. force push는 프로젝트 규칙상 금지합니다.

## main 보호 현황과 승인 대기 설정안

2026-10-12 최종 재조회: 기존 보호 API는 404이지만, 별도의 `protect-main` Ruleset(id 24925172)이 active이며 기본 브랜치 main에 적용됩니다. PR 필수·삭제 금지·non-fast-forward 금지, 우회 actor 없음이 확인됐습니다. 이번 점검에서 권한이나 Ruleset을 변경하지 않았습니다. 이전 요금제 제한 기록과 현재 상태를 구분합니다.

현재 승인 리뷰 요구는 0건, 필수 CI 검사와 대화 해결 요구는 없습니다. 지원 요금제 이름은 API에서 확인되지 않았으며 임의로 변경하지 않습니다. 다음 보완안은 사용자 승인 후 적용합니다.

- 상대방 승인 리뷰 1건 요구
- backend/frontend/repository-policy/browser-e2e 필수 검사
- 리뷰 대화 해결 요구 및 새 commit 뒤 승인 무효화 검토

CI가 실행되는 것과 병합을 막는 필수 검사 지정은 별개입니다. 팀 규칙상 사용자 명시적 승인 전에는 병합하지 않습니다.

## 팀원 B 첫 개발 안내

[MODEL_DEVELOPMENT](docs/MODEL_DEVELOPMENT.md)에 초대 수락, Clone, 모델 환경, 소유 폴더, 계약 합의와 첫 PR 완료 기준을 정리했습니다. 모델 코드와 의존성은 아직 없으며 B가 별도 브랜치에서 준비합니다.
