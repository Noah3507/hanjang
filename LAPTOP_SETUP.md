# Windows 로컬 개발 환경과 worktree 실행

## 현재 기준

PR #39가 병합된 main에 OpenAI 보완 커밋 `3f4eea7`을 통합한다. 기존 브랜치와 worktree를 보존한다. transfer 소스를 덮어쓰거나 과거 브랜치로 되돌려 복원하지 않는다. 기본 Mock/paid=false이며 유료 호출은 별도 승인 대상이다.

## 리소스 재사용

Python 3.12, Node.js 24를 사용한다. 서비스는 `backend/requirements.txt`, 분석 전용 환경은 `backend/requirements-analysis.txt`, frontend는 `frontend/package-lock.json` 기준이다. 기존 가상환경은 재설치하지 않고 재사용한다. B 환경과 섞지 않는다.

- 서비스 Python: 기존 프로젝트의 `.venv/Scripts/python.exe`
- 분석 Python: 기존 프로젝트의 `.venv-analysis/Scripts/python.exe`
- rembg: `artifacts/models/rembg/u2netp.onnx`
- CLIP: `artifacts/models/analysis/ViT-B-32.pt`

모델 버전·체크섬은 [IMAGE_PROCESSING](docs/IMAGE_PROCESSING.md), [IMAGE_ANALYSIS](docs/IMAGE_ANALYSIS.md)을 따른다. 없는 파일은 기존 PC에서 가져오거나 공식 다운로드 절차를 별도 승인받는다. 실행 스크립트는 패키지·모델·브라우저를 다운로드하지 않는다. 기존 `.env`, 가상환경, 캐시, 업로드를 삭제하거나 초기화하지 않는다.

## 최초 로컬 설정

현재 worktree에서 실행한다. 파일이 이미 있으면 복사하지 않고 기존 설정을 확인한다.

```powershell
New-Item -ItemType Directory -Force artifacts | Out-Null
if (-not (Test-Path artifacts/local-dev.json)) {
    Copy-Item scripts/service_local.example.json artifacts/local-dev.json
}
git check-ignore artifacts/local-dev.json
```

편집기로 JSON의 `resource_root`에 모델과 가상환경이 있는 기존 프로젝트의 절대경로를 지정한다. 개인 경로는 Git 제외 파일에만 기록한다. API 키는 넣지 않는다. 각 PC에서 별도로 지정한다.

| 선택 필드 | resource_root 기준 기본값 |
| --- | --- |
| service_python | `.venv/Scripts/python.exe` |
| analysis_python | `.venv-analysis/Scripts/python.exe` |
| photo_model | `artifacts/models/rembg/u2netp.onnx` |
| clip_model | `artifacts/models/analysis/ViT-B-32.pt` |
| clip_junction | 필요 시 직접 지정하는 영문 절대경로 |

각 필드로 기본값을 재정의할 수 있다. 서버 코드와 작업 디렉터리는 현재 worktree이고 리소스만 기존 프로젝트에서 읽는다. `.env`를 복사하지 않는다.

## 검사·실행·종료·재실행

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/service_local.ps1 -CheckOnly -VerifyModels
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/service_local.ps1 -Port 8003 -FrontendPort 5176
```

`-CheckOnly`는 서버 없이 경로·해시·import를 확인한다. `-VerifyModels`는 명시적인 실제 모델 로딩·추론 검사로 시간이 걸린다. 합성 입력으로 실행 가능성을 확인하며 품질 평가는 아니다. Ctrl+C로 정상 종료하고 같은 명령으로 재실행한다. 스크립트는 로컬 JSON에서 매번 환경을 구성하므로 이전 프로세스의 변수에 의존하지 않는다.

`HANJANG_PHOTO_MODEL_PATH`, `HANJANG_ANALYSIS_MODEL_PATH`, `HANJANG_ANALYSIS_PYTHON`을 설정한다. Mock/paid=false·빈 프로세스 API 키·offline 설정을 강제하고, 종료 시 호출 셸 환경을 복원한다. `.env`는 덮어쓰지 않으며 키를 출력하지 않는다. 저장은 현재 worktree의 `artifacts/local-dev/uploads`, 서버는 loopback 전용이다. 사용 중인 포트의 프로세스를 종료하지 않는다. 재시작 시 메모리 세션/job은 유실되므로 새 업로드가 필요하다. 기존 파일을 수동 삭제하지 않는다.

프론트엔드는 별도 터미널에서 실행한다.

```powershell
$env:DEV_BACKEND_URL='http://127.0.0.1:8003'
npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 5176
```

화면 http://127.0.0.1:5176 / Swagger http://127.0.0.1:8003/docs. 다른 포트를 사용하면 두 명령을 함께 변경한다.

## CLIP 한글 경로와 junction

일부 Windows PyTorch 로더는 한글 경로에서 `Illegal byte sequence`를 발생시키고 TorchScript/weights_only 오류로 이어진다. 동일 모델을 ASCII 경로의 directory junction으로 참조한다. 기본 위치는 `%LOCALAPPDATA%/HanJang/model-links/<대상 경로 해시>`이며 임시 폴더 정리에 의존하지 않는다. 사용자 경로 자체가 비ASCII라면 `clip_junction`에 쓰기 가능한 영문 절대경로를 지정한다.

기존 junction은 유형과 대상이 일치할 때만 재사용한다. 일반 디렉터리·잘못된 대상이면 중단하고 삭제/덮어쓰지 않는다. 다른 경로를 지정하거나 소유자가 확인한다. 모델 이동·복사·자동 다운로드는 없다.

## 검증과 복구

새 사진 업로드·정보 저장 → 배경 제거 → 처리본 선택 → CLIP available/단서12개·대표색 → Mock 카피4종 → RGB1080×1350 PNG4장 → Mock 임시 순위 생성·재조회로 확인한다. fallback 경고는 실제 모델 성공이 아니다. 이전 completed 결과가 재사용될 수 있으므로 새 업로드로 확인한다. 처리 품질은 사람이 검토한다.

- 설정 누락: 예시를 Git 제외 위치에 복사하고 PC별 경로 지정
- 파일 누락/해시 불일치: 원본 위치와 문서 지정 버전 확인, 다운로드는 별도 승인
- import 실패: 서비스/분석 Python과 잠금 의존성 일치 확인, 실행 스크립트는 설치하지 않음
- junction 충돌: 기존 대상을 건드리지 말고 새 영문 경로 지정
- 글리프/폰트 실패: 원문은 보존하며 지원 문자와 동봉 폰트 상태 확인

## 테스트·과거 자료

전체 pytest, `RUN_RENDER_TESTS=1` 렌더러, frontend typecheck/test:ci/build/test:e2e를 실행한다. 실제 모델 E2E는 `PLAYWRIGHT_REQUIRE_PHOTO_MODEL=1`, `PLAYWRIGHT_REQUIRE_ANALYSIS_MODEL=1`, `PLAYWRIGHT_ANALYSIS_SAMPLE`로 fallback을 차단한다. 다른 worktree의 Python은 `PLAYWRIGHT_PYTHON`으로 지정한다.

ZIP manifest·transfer는 비상 사본이다. 기존 checkout에 patch/source-snapshot을 재적용하지 않는다. 실험 시안·사용량 원장·모델은 Git 제외한다. 디자인 시안이 운영 승인 또는 Figma/Typography System 구현을 뜻하지 않는다. 과거 실제 호출과 이번 무료 회귀 결과는 [OPENAI_VALIDATION](docs/OPENAI_VALIDATION.md), [통합 검증](docs/HARDENING_TEST_REPORT.md)을 구분해 확인한다.
