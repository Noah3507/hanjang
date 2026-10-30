# HanJang 데스크탑 → Windows 노트북 복원

## 보존 기준

2026-10-30 작업 브랜치는 `feat/service-openai-validation`, 원래 기준 커밋은 `a3101da`(PR #27 병합)입니다. 원격 main은 이후 B의 PR #32까지 진행됐지만 이번 이동 작업에는 병합하지 않았습니다. **최신 main이 아니라 이 작업 브랜치를 checkout해야 현재 작업을 복원합니다.**

OpenAI adapter·예산/재시도·글리프 검증 보완은 소스에 포함됩니다. 디자인 시안과 실제 호출 결과는 Git 제외 ZIP에서 복원합니다. 시안은 사용자 품질 검토를 통과한 운영 디자인이 아닙니다. 모델/B 계약·운영 광고 디자인은 바꾸지 않았습니다.

## 1. 설치

공식 배포본 Git for Windows, Python **3.12**(데스크탑 3.12.10), Node.js **24.x**(24.20.0, npm 11.19.0), 선택적으로 GitHub CLI와 Chrome을 설치합니다. GitHub private 저장소 접근은 자신의 계정으로 직접 인증합니다. Git 사용자 이름·이메일은 각 PC에 설정합니다.

```powershell
git --version
py -3.12 --version
node --version
npm.cmd --version
git clone --branch feat/service-openai-validation https://github.com/Noah3507/hanjang.git
cd hanjang
git status --short
git log -1 --oneline
```

기존 clone이 있으면 미커밋 작업부터 확인하고 `git fetch origin`, 해당 브랜치 전환, `git pull --ff-only`를 사용합니다. reset/clean/force push로 맞추지 않습니다.

## 2. 서비스 환경

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend exec -- playwright install chromium
Copy-Item .env.example .env
Copy-Item frontend/.env.example frontend/.env
$env:HANJANG_COPY_PROVIDER='mock'
$env:HANJANG_COPY_ALLOW_PAID='false'
```

`Copy-Item`은 **새 clone에서만** 실행합니다. 기존 .env를 덮어쓰지 않습니다. 루트 .env에서도 mock/false를 유지합니다. API 키는 이번 복원에 필요 없으며 ZIP에 없습니다. 나중에 사용할 때 서버용 루트 .env에 직접 입력하고 VITE_*나 frontend에는 넣지 않습니다. PowerShell 환경변수는 .env보다 우선하므로 과거 유료 설정이 없는지 값 노출 없이 확인합니다.

동봉 Regular 폰트·OFL은 clone으로 복원됩니다. 디자인 시안의 Bold 폰트·라이선스/출처 기록은 ZIP에 있습니다. 실행 환경은 PC마다 재생성하며 .venv, node_modules를 복사하지 않습니다.

## 3. ZIP 복원

데스크탑이 제공한 ZIP 및 `.sha256` 파일을 USB나 개인 파일 전송으로 복사합니다. GitHub에는 업로드하지 않습니다. ZIP은 공유 전 별도 개인정보 검토가 필요한 로컬 실험 자료입니다.

```powershell
# 경로는 실제 복사한 ZIP으로 변경
$backupZip = 'C:\Users\YOUR_NAME\Downloads\hanjang-laptop-backup.zip'
Get-FileHash -Algorithm SHA256 -LiteralPath $backupZip
# 제공된 .sha256과 일치하는지 확인 후, 새 clone 루트에서 실행
Expand-Archive -LiteralPath $backupZip -DestinationPath .
Start-Process .\artifacts\campaign-prototype-v2\gallery.html
Start-Process .\artifacts\image-edit-experiment-v1\comparison.html
Start-Process .\artifacts\openai-validation\live-generation\gallery.html
```

ZIP의 `transfer/MANIFEST.json`에 항목별 SHA256, 제외 목록, 원래 Git 상태가 있습니다. `transfer/source-snapshot/`과 `transfer/working-tree.patch`는 비상용 소스 사본입니다. **브랜치 checkout 후 patch를 다시 적용하거나 사본을 덮어쓰지 않습니다.**

갤러리의 상대 경로는 그대로 유지합니다. 일부 과거 보고서의 데스크탑 절대경로는 노트북 경로로 읽어야 합니다. 이미지 편집 prototype.py의 외부 Codex imagegen CLI 경로는 별도 도구에 의존합니다. 결과 PNG/갤러리 열기에는 그 도구나 키가 필요 없습니다. 해당 유료 스크립트는 복원 검증 중 실행하지 않습니다.

## 4. 모델과 독립 환경 — 선택

모델이 없어도 원본 fallback·CLIP unavailable·Mock 카피를 사용할 수 있습니다. 모델은 ZIP/Git에 포함하지 않습니다. 기존 데스크탑 모델을 별도 복사하려면 `transfer/LOCAL_ONLY.json`의 경로·해시·용량과 비교하고 동일 상대 경로에 놓습니다. 다운로드는 별도 승인 후 공식 다운로드 스크립트와 IMAGE_PROCESSING/IMAGE_ANALYSIS 문서를 따릅니다.

- rembg: `artifacts/models/rembg/u2netp.onnx`
- 분석 CLIP: `artifacts/models/analysis/ViT-B-32.pt`
- 랭킹: B와 합의된 `artifacts/models/` 파일, `RANKING_MODEL_PATH`로 참조. 실제 모델 없이 개발 가능.

```powershell
# 실제 CLIP 분석이 필요할 때만 설치, 서비스/ML 환경과 분리
py -3.12 -m venv .venv-analysis
.\.venv-analysis\Scripts\python.exe -m pip install -r backend/requirements-analysis.txt
.\.venv-analysis\Scripts\python.exe -m pip check
# B의 모델 작업이 필요할 때만 docs/MODEL_DEVELOPMENT.md를 먼저 읽기
py -3.12 -m venv .venv-ml
.\.venv-ml\Scripts\python.exe -m pip install -r ml/requirements.txt
.\.venv-ml\Scripts\python.exe -m pytest tests/ml -q
```

GPU/드라이버와 다운로드 가능 여부에 따라 설치가 다를 수 있습니다. 실패해도 버전을 임의로 바꾸거나 환경을 합치지 않습니다. references/ 원본 자료는 Git/이번 ZIP에서 제외되므로 필요하면 소유권·개인정보를 확인하고 별도 복사합니다.

## 5. 자동 검증 — 유료 호출 없음

```powershell
$env:HANJANG_COPY_PROVIDER='mock'
$env:HANJANG_COPY_ALLOW_PAID='false'
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test:ci
npm.cmd --prefix frontend run build
$env:RUN_RENDER_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/service/test_rendering.py -q
npm.cmd --prefix frontend run test:e2e
git status --short
```

기존 Chrome을 사용할 경우 `HANJANG_RENDER_CHANNEL=chrome`, `PLAYWRIGHT_CHANNEL=chrome`을 설정합니다. 기본은 위에서 설치한 Playwright Chromium입니다. 이미지 API prototype.py --approved 및 live-generation 실제 호출 스크립트는 실행하지 않습니다. 과거 비용 원장은 ZIP에 보존되며 삭제/초기화로 한도를 우회하지 않습니다.

## 6. 실행과 직접 확인

터미널 1:

```powershell
$env:HANJANG_COPY_PROVIDER='mock'
$env:HANJANG_COPY_ALLOW_PAID='false'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

터미널 2:

```powershell
npm.cmd --prefix frontend run dev
```

- 서비스: http://127.0.0.1:5173
- Swagger: http://127.0.0.1:8000/docs
- 상태: http://127.0.0.1:8000/health

frontend/.env의 DEV_BACKEND_URL이 있다면 8000으로 맞춥니다. 상품 입력→업로드→저장/재조회→원본/처리본 선택→분석(모델 없으면 경고)→Mock 네 전략→실제 PNG 미리보기를 확인합니다. 서버 상태·세션·기존 업로드 job은 메모리/24시간 임시 자료라 다른 PC로 이어지지 않습니다. 새로 업로드해야 합니다. 서버는 localhost만 공개하며 재부팅 후 다시 실행합니다.

## 7. 두 PC 전환 규칙

시작 전 branch/status/fetch/pull --ff-only, 종료 전 검증/commit/push와 원격 일치를 확인합니다. 다른 PC에서 같은 작업을 동시에 수정하지 않습니다. .env·가상환경·모델·실험 자료는 Git과 별도로 관리합니다. main에 직접 push하거나 사용자 승인 없이 merge하지 않습니다.

이번 준비는 데스크탑 검증입니다. **노트북 설치·실행·테스트는 아직 미실행**이며 동일 하드웨어 성능이나 모든 외부 도구의 재현을 보장하지 않습니다.

2026-10-30 데스크탑 재검증: pytest 207 passed / 18 skipped(브라우저 opt-in), 별도 실제 Chrome 렌더링 35 passed(기본 테스트와 일부 중복), Vitest 30 passed, TypeScript/build/pip check 통과. 노트북에서도 위 명령으로 새로 검증해야 합니다. 최초 pytest의 미생성 basetemp 부모 경로 오류는 테스트용 디렉터리 생성 후 해소했습니다. AnyIO deprecated alias 경고는 남아 있습니다.

데스크탑 준비 과정에서 기존 `uploads/originals` 접근 권한으로 E2E 서버가 시작하지 못한 경우가 있었습니다. 노트북에서도 같은 문제가 있으면 권한 있는 테스트 전용 폴더를 만들고 `$env:HANJANG_UPLOAD_ROOT=Join-Path $PWD 'artifacts/laptop-validation/e2e-uploads'`로 지정합니다. 기존 업로드를 삭제하거나 ACL을 무조건 변경하지 않습니다. 서비스 입력·사진은 새 작업으로 다시 업로드합니다.
