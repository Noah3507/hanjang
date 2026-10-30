# 결과 화면 및 MockRanker 검증 기록

2026-10-30, Windows 노트북, `feat/service-results`, 기준 main `e114d7d`.

## 환경과 보존

- 별도 `artifacts/worktrees/service-results` 작업 트리에서 실행했다. 기존 서비스 Python 3.12 가상환경과 Chromium 캐시를 명시적으로 재사용하고 frontend 패키지는 잠금 파일 기준 오프라인 설치했다. 새 모델·폰트·유료 API 호출은 없다.
- `HANJANG_COPY_PROVIDER=mock`, `HANJANG_COPY_ALLOW_PAID=false`, 시험 프로세스의 OpenAI 키는 빈 값이다. 기존 `.env`와 가상환경·transfer·untracked 파일은 복사하거나 변경하지 않았다.
- 기존 `feat/service-openai-validation`의 `3f4eea7`은 main 미반영 상태로 보존했으며 이번 브랜치에 이식하지 않았다.

## 최종 검증

| 실행 | 결과 | 범위 |
| --- | --- | --- |
| `RUN_RENDER_TESTS=1 python -m pytest` | 219 통과, AnyIO deprecation 경고 1건 | 서비스 전체, 실제 Chromium 렌더러, 새 ranking 단위/API/계약 통합 검사 |
| `npm --prefix frontend run typecheck` | 통과 | TypeScript |
| `npm --prefix frontend run test -- --run` | 44 통과, 11 파일 | API 검증·snapshot·늦은 응답·이미지 재시도 포함 |
| `npm --prefix frontend run build` | 통과 | 운영 번들 생성 |
| `npm --prefix frontend run test:e2e` | Chromium 25 통과 | 기존 흐름 및 결과 화면 신규 3 시나리오 |

실제 브라우저: 로컬 FastAPI/Vite, 합성 상품 PNG 업로드·입력 저장·Mock 카피·실제 1080×1350 RGB PNG 네 장·확대 보기·Enter/Tab/ESC·초점 복귀·순위 요청·새로고침 재조회·입력 변경 stale·새 revision 재생성·모바일 가로 넘침을 확인했다. 화면에는 점수나 확률을 표시하지 않으며 시연용 안내를 제공한다.

오류 경로: ranking 503, asset 410, 지연 ranking 응답은 브라우저 route 모의로 별도 검증했다. 서버 단위/API 테스트에서는 인증·소유권·만료·누락/손상 PNG·snapshot 변경·실행 실패·재시도·NaN/동점/누락 ID를 검사했다. 모의 장애 검증을 실제 장애 발생 기록으로 해석하지 않는다.

초기 E2E는 확대창 Tab 초점 유지 문제와 오래된 안내문을 찾는 기존 테스트 두 건으로 실패했다. 초점 처리와 테스트를 수정한 뒤 전체 25개를 재실행해 통과했다. 실패 기록은 Git 제외 artifacts에 보관했다. 긴 Windows 경로로 일부 진단 파일의 보조 복사는 실패했으며 원본 테스트 출력과 최초 로그를 보존했다.

## 결과물과 직접 확인

- 화면: <http://127.0.0.1:5175>, Swagger: <http://127.0.0.1:8002/docs>. 별도 작업 트리의 loopback 개발 서버를 실행했다. 기존 서버는 종료하지 않았다. 재부팅 이후 유지하지 않는다.
- `artifacts/results/pytest.log`, `e2e.log`(초기), `e2e-final.log`(최종), 서버 로그 및 `servers.json`.
- `artifacts/playwright/results/results-*/results-desktop.png`, `results-mobile.png`: 합성 사진으로 생성한 실제 화면. CI의 기존 `upload-ui-screenshots` artifact에도 새 결과 화면을 포함하도록 경로만 추가했다.
- 상품 사진과 필수 정보를 입력하고 저장 → Mock 카피 생성 → 광고 4장 생성 → 각 카드 확대 → 임시 순위 확인. 입력을 바꾸면 기존 순위는 최신 결과로 표시되지 않는다. 저장 후 카피/광고를 다시 생성하고 새 순위를 요청할 수 있다.

## 검증 한계

실제 Bradley–Terry 추론·학습·가중치·특징 추출은 실행/수정하지 않았다. rembg/CLIP 모델을 설치하지 않았으며 해당 경로의 fallback은 실제 모델 성공을 뜻하지 않는다. 임시 순위는 고정 fixture 시험값이며 광고 품질·구매율·CTR 평가가 아니다. 문구 편집·다운로드·진단·실제 모델 통합 등 10~13단계는 구현하지 않았다. 기존 `3f4eea7`의 OpenAI 보완 코드 역시 이번 브랜치 검증 범위가 아니다.

커밋·PR·CI 최종 식별자는 사용자 완료 보고 및 GitHub PR에서 확인한다. 자동 테스트 통과는 사용자 검토나 병합 승인을 대신하지 않는다.
