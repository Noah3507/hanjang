# 현재 구현 브라우저 검증 결과

검증일: 2026-10-12(KST). Windows, Python 3.12, Node.js 24, Playwright 1.64.0, 설치된 Google Chrome(channel=chrome)에서 실제 실행했습니다. 제품 전체 완료 보고가 아니라 현재 기본 화면의 검증 결과입니다.

## 실행과 접속

- React: http://127.0.0.1:5173
- FastAPI 문서: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health
- 두 서버는 loopback에서 백그라운드로 실행하고 테스트 종료 뒤에도 유지했습니다. 컴퓨터 재시작 이후 실행까지 보장하지 않습니다.
- 루트와 frontend의 실제 .env가 없어서 비밀 없는 .env.example로 로컬 생성했습니다. 기존 파일을 덮어쓰지 않았고 Git에서 제외했습니다. 현재 API 키는 필요하지 않습니다.

## 실제 테스트 결과

| 검사 | 방식 | 결과 |
| --- | --- | --- |
| FastAPI·Vite proxy의 health 계약, React 연결 성공 | 실제 서버 GET·실제 Chrome 화면 | 통과 |
| 연결 대기 표시와 재시도 버튼 비활성 | 테스트 안에서만 health 응답 지연 | 통과 |
| 연결 실패 안내 후 실제 API로 재시도 | 테스트 안에서만 503 모의, 해제 후 실제 서버 요청 | 통과 |
| 잘못된 응답을 연결 성공으로 표시하지 않음 | 테스트 안에서만 잘못된 api_version 반환 | 통과 |
| 375px 모바일 상태·버튼·가로 overflow | 실제 페이지를 모바일 viewport에서 검사 | 통과 |

Playwright 5 passed, 0 failed, 0 skipped입니다. 브라우저 uncaught JavaScript 오류는 없었습니다. 503 모의 중 console/network 오류는 의도한 장애 시험이며 서버 자체 장애나 시험 실패가 아닙니다. 실패 screenshot·trace·video 저장 정책은 설정돼 있지만 이번 실행에 테스트 실패는 없어 실패 artifact는 생성되지 않았습니다.

추가 확인: Vitest 4개, pytest 16개, TypeScript·frontend build·pip check 통과. 기존 Starlette/AnyIO 폐기 예정 경고 1건은 남아 있으며 동작 오류는 아닙니다. 데스크탑·모바일 스크린샷을 직접 확인했습니다.

## 테스트 가능·불가능 범위

사용자는 Hanjang 메인 화면, 백엔드 연결 상태, 연결 다시 확인 버튼, FastAPI Swagger의 health 호출을 확인할 수 있습니다. 자동 장애 모의는 사용자 페이지에 남기지 않았습니다.

상품 정보 입력·사진 업로드·광고 4종 생성·선호 순위·문구 수정·PNG/A4 결과는 아직 구현되지 않았습니다. 실제 입력 UI가 없음을 확인했으며 입력부터 광고 결과까지 성공했다고 보고하지 않습니다. 모델 학습·LLM·사진 처리 기능을 이번 작업에서 추가하지 않았습니다.

## 재실행과 진단 파일

실행 코드는 frontend/e2e/foundation.spec.ts, 설정은 frontend/playwright.config.ts입니다. [README](../README.md#실제-브라우저-자동-테스트)에 실행 명령을 정리했습니다.

로컬 결과는 Git 제외 artifacts/playwright/에 있습니다: report/ HTML, results.json, results/의 browser.log·성공 screenshot. 실패하면 같은 폴더에 screenshot·trace·video·assertion 로그를 보관합니다. 서버 stdout/stderr는 artifacts/dev-servers/에 있습니다. 이 파일들은 새 clone에 포함되지 않으며 실행 후 생성됩니다. 원본 이미지·키·개인정보를 log/artifact에 넣지 않습니다.

별도 컴퓨터·다른 Chrome 버전에서의 성공까지 보장하지 않습니다. CI는 별도의 Linux Chromium 실행으로 확인합니다.
