# 10단계 편집·다운로드 검증 — 2026-10-31

## 환경과 보존

Windows 데스크탑, Python3.12.10/Node24.20.0/npm11.19.0, 기존 서비스 .venv·분석 .venv-analysis·Chrome 재사용. 기준 main ea90b00, feat/service-editor. 패키지/모델/폰트 설치 없음. B 코드·가중치·Candidate fixture/schema 변경 없음. 실제 LLM 호출0, Mock/paid=false 및 모델 offline 유지.

## 최종 실행

| 명령 | 결과 |
| --- | --- |
| `RUN_RENDER_TESTS=1 HANJANG_RENDER_CHANNEL=chrome python -m pytest -q -p no:cacheprovider --basetemp artifacts/editor/full-ttl-final` | **291 passed**,96.42초,skipped0,AnyIO deprecated alias 경고1 |
| `npm --prefix frontend run typecheck` | 통과 |
| `npm --prefix frontend run test:ci` | **51 passed / 13 files** |
| `npm --prefix frontend run build` | 통과 |
| `npm --prefix frontend run test:e2e -- --output=../artifacts/editor/e2e-full-final --reporter=list,html` | **28 passed**,2.0분,exit0 |
| `python -m pip check`, `git diff --check`, index 보안 검사 | 통과 |

첫 행은 PowerShell 환경변수 설정 후 서비스 `.venv/Scripts/python.exe`로 실행했다. 291에는 편집23개와 기존1–9단계 서비스/계약·실제 렌더러 회귀가 포함되어 focused 테스트를 더해 합산하지 않는다. 첫 전체290개 통과 후 편집 시작 직후 TTL이 만료되는 경계의 슬롯 해제 책임을 보완하고 만료 중 완료 테스트를 추가해 전체를 재실행했다.

최종 E2E 변수: PLAYWRIGHT_CHANNEL=chrome, PLAYWRIGHT_FRONTEND_PORT=5186, PLAYWRIGHT_BACKEND_PORT=8013, DEV_BACKEND_URL=http://127.0.0.1:8013, PLAYWRIGHT_REQUIRE_PHOTO_MODEL=1, PLAYWRIGHT_REQUIRE_ANALYSIS_MODEL=1, PLAYWRIGHT_ANALYSIS_SAMPLE=artifacts/image-analysis/coffee.png, PLAYWRIGHT_HTML_OUTPUT_DIR=artifacts/editor/html-full-final(경로는 절대경로로 지정). rembg/CLIP은 로컬 실모델, 카피·ranking은 Mock이다.

## 확인한 동작

- 현재 성공 카피로 연속편집, revision1→2→3, 네 ID/strategy 유지, 미수정 세 PNG asset/bytes 재사용.
- 사진 bytes/hash·원문 facts·최초 카피/copy_key 보존. 기존 rendering POST로 편집본이 원본 카피로 복귀하지 않음.
- 중복 재사용·무변경 처리·다른 동시 편집409·expected source충돌·schema·16KiB 제한.
- 길이·HTML·이모지·ZWJ/variation selector 거부, 기존 glyph/layout/overflow 검사 유지.
- 재렌더링 실패와 처리 중 입력 변경 시 마지막 성공본 유지. 성공 후 이전 ranking stale, 새 순위는 사용자 요청.
- 다운로드 인증/소유권/TTL/최신revision/MIME/PNG해시, 안전한 파일명. PDF실패·동시 생성·완료시 source재검증 및 PNG보존/캐시.
- 실제 브라우저 PNG/PDF다운로드·확대·취소 초점·새로고침·375px 가로넘침 없음. 정상 편집 흐름 console error/pageerror0. 의도된409/410/503 route 모의는 실제 API 성공 경로와 구분한다.

## PDF 검증

실제 Chromium 편집PNG는1080×1350 RGB·불투명이며 수정 전과 bytes가 다르다. PDF는210×297mm(MediaBox 반올림 허용0.2mm) 세로 한 페이지다. image stream의 RGB bytes가 최종 PNG와 완전히 같아 한글·가격 등 내용의 손실이 없음을 확인했다. 실제 draw matrix는4:5이고 모든 여백은10mm 이상이다. 정수716×895 CSS px로 비대칭 인쇄 반올림을 피한다.

브라우저에서 다운로드한 최종PDF를 Chrome PDF viewer로 열어 한글·상품명·가격·여백·페이지 clipping을 시각 확인했다. PNG기반이므로 PDF내 검색 가능 텍스트/300dpi 인쇄 원본은 아니다. 기기·프린터별 실물 출력은 미검증이다. 모든 필드 최대길이의 무조건 수용은 보장하지 않고 기존 overflow 오류를 반환한다.

## 초기 실패와 보완

신규 editing GET의 기존 테스트 mock 누락, 취소 후 disabled버튼 초점복원, fetch mock signature 타입, 새 E2E 필수 분위기 누락, Chromium nested label 탐색 문제를 수정했다. 명시적 useId/htmlFor 연결과 렌더 후 초점복원을 사용한다. PDF검사 regex가 처음 root transform을 골라 실패했으며 image transform을 선택하도록 수정했다. 실제 PDF의 미세 비율오차도 발견해 정수4:5 크기로 보완했다. 기존 미구현 안내 assertion은 최신 범위로 갱신했다. 첫 서버 기동은 Playwright auto-start와 포트경쟁이 있어 이번 editor 서버만 재시작하고 ready응답 후 최종 전체 실행했다.

초기 실패/중단 자료는 artifacts/editor/e2e-initial·e2e-second, 최종 성공은 e2e-full-final 및 html-full-final이다. 모두 Git제외 합성 상품 자료다.

## 직접 검토와 제약

- 서비스 http://127.0.0.1:5186, Swagger http://127.0.0.1:8013/docs. service_local.ps1과 기존 로컬설정으로 실행한 loopback 서버를 유지한다. 재부팅 후 재실행한다.
- 최종 다운로드: `artifacts/editor/review/edited.png`, `ad-a4.pdf`, `pdf-browser.png`, `desktop.png`, `mobile.png`.
- 브라우저 보고서: `artifacts/editor/html-full-final/index.html`.
- 사진/상품 저장→Mock카피→렌더링→수정할광고 선택→문구편집→적용→새revision 확인→PNG/PDF다운로드. 다시 열면 최신문구가 표시된다. 임시순위는 다시 요청한다.

실제 유료 LLM·실제 B랭킹 모델·상업적 광고 디자인 품질·자유배치는 범위 밖이다. 사용자작성 문구의 의미적 진실성을 완전히 자동판정하지 않는다. 메모리 상태는 재시작복구되지 않고 업로드기준24시간 TTL을 유지한다. PDF캐시는 job메모리다. Linux검증은 PR의 Actions 결과를 별도로 확인한다. main병합은 사용자 승인대기다.
