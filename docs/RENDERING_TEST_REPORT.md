# S5b 광고 렌더링 검증 (2026-10-28 Windows)

기준 main9fee198(PR #25 병합), 작업 feat/service-renderer. 실제 OpenAI/대안 API 호출0회·비용$0입니다. ranking은 구현하지 않았습니다.

| 검사 | 결과 |
| --- | --- |
| 전체 서비스/계약 pytest | 172 passed, 브라우저 opt-in18 skipped, 기존 AnyIO 경고1건 |
| 렌더링 Store/API + 실제 Chromium 별도 실행 | 35 passed, 70.24초, skip0 |
| 기존 B 계약 | 기존38개 포함, fixture/schema 수정 없음 |
| Vitest | 30 passed |
| TypeScript / Vite build | 통과 |
| pip check | No broken requirements found |
| 전체 Playwright E2E | 최종22 passed, 57.0초 (이전22 passed, 58.9초) |
| 실제 LLM/순위 모델/배포 | 미실행·이번 범위 밖 |

기본 pytest의18 skip은 브라우저 설치가 필요한 명시적 opt-in입니다. 같은18개를 실제 브라우저로 별도 실행했고, Store/API17개와 합해35개가 통과했습니다. 독립 테스트는172+18=190개이며 중복 실행을 합산하지 않습니다.

## 환경·명령

Python3.12.10 서비스 .venv, Node24.20.0, Playwright1.64.0, 설치된 Windows Chrome channel입니다. Jinja2 3.1.6/MarkupSafe3.0.4를 추가했고 rembg/Pillow 버전과 A .venv-analysis/B .venv-ml은 변경하지 않았습니다. CI는 고정 Playwright Chromium을 사용하므로 Ubuntu 결과와 Windows 결과를 구분합니다.

```powershell
New-Item -ItemType Directory -Force artifacts/renderer | Out-Null
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp artifacts/renderer/final-regression
$env:RUN_RENDER_TESTS='1'
$env:HANJANG_RENDER_CHANNEL='chrome'
.\.venv\Scripts\python.exe -m pytest tests/service/test_rendering.py -q -p no:cacheprovider --basetemp artifacts/renderer/final-boundaries
npm.cmd --prefix frontend run test:ci
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -m pip check
$env:PLAYWRIGHT_CHANNEL='chrome'
$env:PLAYWRIGHT_FRONTEND_PORT='5183'
$env:PLAYWRIGHT_BACKEND_PORT='8013'
npm.cmd --prefix frontend run test:e2e
git diff --check
```

## 검증 범위

- 원문·copy_key 유지, 세 expected 불일치409, stale 카피 차단, 렌더링 도중 입력/사진 변경 시 stale 보존.
- 네 Candidate의 같은 revision/facts·고유ID·기존JSON Schema 호환, 같은 snapshot 재사용·다른 snapshot 새 결과.
- 인증401/타 소유자404/만료410·body16KiB·path traversal·TTL 파일 정리·부분 저장 실패 정리·timeout/worker 실패와 재시도.
- 실제 Chromium 정상출력17사례를 네 전략 모두 검사하고, 별도 극단값1사례는 명시 실패를 확인했습니다. 일반, 카피 최대 길이, 공백 없는/있는 한글, 긴 영어 단어, 혼합, 빈body/CTA/둘다, 긴 가게명/상품명/가격, 주소만/Instagram만/둘다, HTML 유사facts, 투명 이미지, 전체 필드 극단값을 포함합니다.
- PNG decode·1080×1350·RGB 불투명·contain 비율·안전 여백·text bbox/overflow/겹침·최소32px·CDP 실제 글꼴·전략별 geometry 차이.
- 극단적인 모든 필드 동시 최대값은 RENDER_LAYOUT_OVERFLOW를 기대하는 테스트입니다. 이를 PNG 성공으로 보고하지 않습니다. Facts/Copy의 기존 줄바꿈 금지422도 유지합니다. 특징의 허용 줄바꿈은 저장되며 직접 광고에 출력하지 않습니다.

## E2E·시각 확인

실제 FastAPI/React에서 입력/업로드→Mock 카피→실제 Chromium PNG 네 장→재조회→특징 변경/stale→카피 재생성→재렌더링→375px 화면을 검증했습니다. Mock은 고정 카피 내용이며 API·PNG 생성은 실제 처리입니다. 별도 사례에서503 worker 장애를 모의했습니다. 기존 업로드/rembg/사진 분석/카피 회귀도 포함합니다. 성공 흐름 Console/pageerror는0이며 의도한 장애의 HTTP 오류는 구분합니다.

로컬 실제 음식 PNG는 `artifacts/renderer/coffee/emotional.png`, `price.png`, `visual.png`, `brand.png`, DOM 계측은 같은 폴더의 `measurements.json`입니다. 이전 단계의 scikit-image coffee 검증 사진을 사용했고 네 장을 직접 열어 확인했습니다. contain 여백으로 상품 전체 frame을 보존합니다. 첫 수동 PowerShell fixture는 기본 인코딩으로 한글이?로 변환돼 UTF-8을 명시하고 다시 생성했습니다. UTF-8 소스 기반 pytest/E2E에서는 이 문제가 없었습니다.

스크린샷·로그·trace·HTML 보고서는 `artifacts/playwright/`에 있습니다. PNG·metadata·사용자 사진은 Git에 포함하지 않습니다. 픽셀/bbox 검증은 완전한 가독성·OCR 일치·상품 마스크 품질·모든 Unicode 지원의 보증이 아닙니다. 미지원 글꼴 fallback은 명시적으로 실패하며 OS간 pixel-perfect 일치는 미검증입니다.

## 직접 확인·한계

첫 Ubuntu CI는 렌더러 실행 전 pytest --basetemp의 부모 artifacts/renderer가 없는 새 checkout에서32개 fixture setup 오류로 실패했습니다(3개 통과). CI에 부모 폴더 명시 생성을 추가했습니다. 로컬에 이미 있던 폴더에 의존한 CI 설정 오류이며 제품 렌더링 오류와 구분합니다. 수정 후 최신 CI 결과를 PR에서 확인합니다.

최종 확인 서버: React http://127.0.0.1:5183 / Swagger http://127.0.0.1:8013/docs. Mock/paid=false·loopback으로 유지하며 재부팅 이후 유지나 서버 메모리 작업 복구는 보장하지 않습니다.

상품 사진과 정보 저장→4전략 카피 생성→광고4장 렌더링→전략별 배치/원문 가격/상품/가게 확인→특징 변경/저장→이전 광고 경고→카피 재생성→재렌더링을 시험합니다. 입력된 주소/Instagram은 별도 정보 영역에 표시하며 주소 LLM 전송 옵션과 분리합니다.

모든 필드 동시 최대값은 공간 부족으로 명시 실패할 수 있습니다. 절단·축약·32px 미만 축소는 하지 않습니다. 실제 LLM 품질·의미적 사실 보호·랭킹·readability·편집·다운로드·PDF·운영 CPU/RAM은 미검증/미구현입니다. 초기 폰트 metric과 CDP CSS 초기화 오류는 수정 후 다시 검증했습니다. 실제 LLM/모델 다운로드는 없으며 CI는 PR 결과로 별도 확인합니다.
