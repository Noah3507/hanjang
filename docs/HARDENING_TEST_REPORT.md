# OpenAI 보완 통합 및 로컬 모델 실행 안정화 검증

2026-10-30, `fix/service-openai-hardening`, 기준 main `369592e` (PR #39 병합).

## 적용과 보존

- `3f4eea7` 변경을 새 worktree에 --no-commit으로 적용했다. main.py는 자동 병합됐고 수동 충돌 해결은 없었다. CopyStore 재시도 설정과 RankingStore·라우터가 모두 유지된다.
- 기존 두 브랜치/worktree, main, transfer, 실제 .env, 모델·가상환경·B 소유 코드를 변경하지 않았다. 기존 5175/8002 확인 서버도 종료하지 않았다.
- 변경 영역: 카피 설정/adapter/예산/글리프·render 오류 분류, fonttools 의존성, 관련 테스트, Windows 실행 스크립트·모델 점검·예시 설정, 문서. Candidate/HTTP rendering/ranking 계약·운영 템플릿은 유지했다.

## 자동 검증

| 명령 | 최종 결과 |
| --- | --- |
| `RUN_RENDER_TESTS=1 python -m pytest -q -p no:cacheprovider` | 268 passed, AnyIO deprecation 경고1건, skip0 |
| `npm --prefix frontend run typecheck` | 통과 |
| `npm --prefix frontend run test:ci` | 44 passed / 11 files |
| `npm --prefix frontend run build` | 통과 |
| `npm --prefix frontend run test:e2e` | Chromium 26 passed / 1.8분 |
| 실행 스크립트 `-CheckOnly -VerifyModels` | 기존 두 모델 실제 로딩/추론 통과 |

backend에는 OpenAI fake SDK·소켓 차단, 요청/비용한도·usage·오류·재시도·원장 손상/쓰기 실패·실패 기록 오류, 글리프·원문 보존·폰트 누락/손상, prompt/glyph 정책 변경 후 copy/render/ranking stale 및 재생성, Ranking 계약·권한·revision/ID/asset 검증을 포함한다. 확장 프롬프트의 상한 초과는422로 거절하고 원문을 유지한다.

Windows launcher 실패 테스트3개도 로컬 통과했다. Linux CI에서는 Windows 전용으로 명시적으로 skip한다. 별도 실제 파일 검증으로 기존 일반 디렉터리/비ASCII junction 경로를 오류로 거절하고 marker가 보존됨을 확인했다. 올바른 junction은 반복 실행에서 재사용했다.

## 새 셸에서 정상 종료와 재실행

로컬 JSON은 `artifacts/local-dev.json`이며 Git ignore를 확인했다. 기존 환경변수를 비우고 `powershell.exe -NoProfile ... service_local.ps1`로8003 서버를 실행했다. 첫 서버는 자신 콘솔에 Ctrl+C를 전달해 `Application shutdown complete` 로그를 확인했다. 같은 명령을 새 PowerShell에서 다시 실행해 다른 PID와 HTTP200을 확인했다. 임시 변수나 기존8002 프로세스에 의존하지 않는다.

CLIP은 로컬 설정에서 해석한 기존 캐시를 `%LOCALAPPDATA%/HanJang/model-links/<해시>` junction으로 참조한다. 원본과 해시가 동일하며 모델 복사/다운로드가 아니다. Windows PyTorch의 한글 파일 경로 제약을 실행 설정으로 우회한다. 잘못된 junction은 삭제/교체하지 않는다. 개인 경로는 Git 제외 JSON/로그에만 둔다.

## 실제 상품 API와 브라우저

기존 에스프레소 상품 사진으로 새 업로드·한글 가게명/상품명·공백 포함 가격 저장을 확인했다. 배경 제거 약5초, 투명 alpha0..255, 원본 바이트 동일. 처리본을 선택해 CLIP 약10초, available·시각단서12개·대표색5개·경고0. Mock카피4종, RGB1080×1350 PNG4장, Mock 순위와 GET 동일 재조회가 통과했다. facts는 원문과 동일하다.

전체 E2E는 실제 로컬 FastAPI/Vite와 Chromium을 사용했다. `PLAYWRIGHT_REQUIRE_PHOTO_MODEL=1`, `PLAYWRIGHT_REQUIRE_ANALYSIS_MODEL=1`로 fallback을 성공 처리하지 않았다. CLIP E2E 입력도 실제 에스프레소이다. 결과 확대·키보드 초점·모바일·재조회·stale·새 revision을 확인했다. 잘못된 세션/오류/지연 응답은 별도 route 모의 또는 API 테스트로 구분한다. 점수·확률 대신 시연용 안내를 유지한다.

## 결과물·실행

- `artifacts/hardening/pytest.log`, `e2e.log`, `targeted.log`
- `launch-first*`, `launch-second*`: 정상 종료·새 프로세스 실행 로그
- `actual-models/verification.json`, `espresso-processed.png`, 전략별 PNG4장
- `artifacts/playwright/results/`: 데스크톱/모바일·CLIP·배경 제거 화면, report/에 HTML 보고서
- 사용자 화면 http://127.0.0.1:5176 / Swagger http://127.0.0.1:8003/docs, 기존 화면5175는 별도 유지

실행 방법과 다른 PC 설정은 [LAPTOP_SETUP](../LAPTOP_SETUP.md)을 따른다. 사진·정보 저장 → 배경 제거 → 처리본 선택 → 사진 분석 → Mock카피 → PNG → 임시 순위로 확인한다. 재시작 후 새 job을 만든다.

## 한계와 검토

실제 OpenAI 호출0회·신규 모델/패키지 다운로드0회. frontend 패키지는 기존 오프라인 캐시에서 잠금 기준 설치했고 기존 가상환경은 재설치하지 않았다. 실제 유료 카피 품질·과금은 검증하지 않는다. 모델 실행 성공이 모든 상품의 분리 품질이나 CLIP 사실 정확도를 보장하지 않는다. B 학습/추론·디자인/Figma/Typography·10~13단계는 미구현/미실행이다.

기존 메모리 metadata·24시간 TTL·단일 서버 제약을 유지한다. Windows 실행 스크립트는 로컬 개발용이며 배포/자동 시작 서비스가 아니다. 원장 I/O 장애 시 완전한 청구 감사는 보장하지 않으며 보수 예약을 유지한다. 생성형 문구 검사는 의미 전체의 사실성 검증이 아니다. 새 PR의 커밋·CI 식별자는 사용자 완료 보고와 GitHub에서 확인하며 main은 사용자 승인 전 병합하지 않는다.
