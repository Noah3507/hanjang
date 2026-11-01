# S5b / 사용자 8단계 광고 렌더링

## 11단계 계측 확장

기존 디자인·PNG·Candidate/B 계약을 유지하고 별도 measurements에 실제 glyph rect와 contrast evidence를 추가합니다. 원본 PNG 캡처 후 글자 fill만 숨긴 배경 캡처와 실제 paint eligibility를 검사하고 최종 PNG SHA-256으로 결합합니다. CSS 배경색만으로 대비를 추정하지 않으며 gradient/image/transparency 등 불확실 항목은 unavailable입니다. 원본 PNG를 먼저 확보하므로 optional 계측 실패는 기존 렌더링을 실패시키지 않습니다. template version은 four-layouts-v2-evidence이며 자세한 계약은 [DIAGNOSTICS](DIAGNOSTICS.md)를 따릅니다.


2026-10-31 후속10단계: [EDITING](EDITING.md)에 승인된 문구 편집·최신 성공 revision 다운로드와 A4 PDF를 추가한다. 기존 rendering 요청/응답·Candidate는 유지하며 같은 생성 snapshot의 POST/GET은 최신 편집 성공본을 반환한다. 편집 상태는 별도 editing envelope, 실패는 마지막 성공 rendering을 보존한다. 실제 renderer는 기존 네 전략 생성 외에 편집 대상 한 전략의 내부 실행도 지원한다. 아래 미구현 설명은8단계 당시 범위 기록이다.

2026-10-30 사전 보완: 사용자 facts의 실제 동봉 폰트 cmap 지원을 렌더링 전에 검사하고 미지원이면 원문을 유지한 오류 안내를 제공합니다. 생성 카피의 이모지/미지원 글리프 검증과 호출 통제는 [OPENAI_VALIDATION](OPENAI_VALIDATION.md)을 따릅니다. 기존 Chromium 최종 검사·템플릿·디자인·Candidate schema는 유지합니다.

7단계 저장 카피 → current snapshot 검증 → Jinja2 → Node/Playwright Chromium → 실제 1080×1350 RGB 불투명 PNG 네 장 → 비공개 asset 조회입니다. LLM·CLIP을 다시 실행하지 않습니다. 순위·진단 엔진·편집·다운로드·PDF는 구현하지 않습니다. Mock 카피는 API의 mock_copy와 UI 배너로 표시하며 실제 LLM 검증은 보류입니다.

## 승인된 additive API

모든 경로는 `/api/v1`, `X-Hanjang-Session` 필수, no-store입니다.

| API | 요청 | 응답 |
| --- | --- | --- |
| POST /jobs/{job_id}/rendering | `{expected_asset_id, expected_input:{facts,mood,product_features,use_address_for_copy}, expected_copy_key}` | 202 RenderResponse, Location=status_url |
| GET /jobs/{job_id}/rendering | 없음 | 200 RenderResponse, polling/결과 조회 |
| GET /assets/{asset_id} | 없음 | 기존 인증 binary 조회, PNG preview |

`RenderResponse={job_id,operation:"rendering",status,status_url,source_asset_id,copy_key,revision,is_current,mock_copy,candidates,measurements,warnings,error,expires_at}`입니다. 상태는 pending/processing/completed/failed만 사용합니다. pending/processing/failed는 candidates=[]이며 completed는 정확히 네 전략입니다. 순서는 emotional/price/visual/brand이고 순위를 의미하지 않습니다. error는 null 또는 `{code,message}`입니다. 전체 HTTP/OpenAPI schema는 `/docs`에 제공합니다.

`copy-generation` 응답에 additive `copy_key:string|null`을 추가했습니다. 아직 생성 전이면 null, 생성 시 UUID를 발급하며 재조회·동일 snapshot 캐시에서 유지합니다. 실패 후 명시 재시도는 새 키를 발급합니다. 기존 요청/Facts/카피 필드는 유지합니다. unknown response 필드를 거부하는 외부 strict 소비자는 새 필드를 허용해야 합니다. 서비스 frontend 타입도 함께 갱신했습니다.

POST의 세 expected 필드 중 하나라도 현재 서버 상태와 다르거나 카피가 stale/미완성이면 409 RENDER_SOURCE_CHANGED입니다. 현재 원본/처리본을 고정하며 사진 처리 중은409 PHOTO_PROCESSING_BUSY, 다른 렌더링 작업 중은503 RENDER_BUSY입니다. 미저장 입력409, 인증401, 다른 소유자/미존재404, 만료410, body16KiB 초과413, schema422를 유지합니다. 생성 완료 전 timeout·브라우저 부재·레이아웃 실패 등은 GET의 failed/error로 표시하고 입력·사진·카피는 유지합니다.

## Snapshot과 저장

input 전체 원문·선택 asset ID·완성 카피 결과 및 copy_key·template version을 cache key로 사용합니다. 같은 snapshot의 processing/completed는 재사용합니다. 변경된 요청은 새 revision으로 네 후보를 만듭니다. revision은 렌더링 job 내 단조 증가하며 기존 ranking revision을 구현한 것이 아닙니다.

카피 snapshot 검사는 CopyStore.current_for_render()를 재사용합니다. 시작/완료/GET에서 다시 검사하고, 작업 중 변경된 결과는 보존하되 is_current=false입니다. 오래된 결과는 UI에서 경고하며 최신 광고로 사용하지 않습니다. 저장/사진/카피가 원래 snapshot으로 돌아오면 같은 캐시를 재사용할 수 있습니다. template 수정 시 VERSION을 올려야 합니다.

UUID 파일명·기존 uploads private root·소유권·safe_path 검사를 재사용합니다. 네 장 검증 후 한 번에 asset 인덱스와 결과를 공개하며 부분 실패는 생성 파일을 정리합니다. 원본 bytes와 facts는 수정하지 않습니다. upload 시점의 24시간 TTL을 유지하고 파생 PNG mtime도 원본 시각으로 맞춰 orphan sweep에 포함합니다. 만료 중 완료된 결과는 공개하지 않습니다. metadata는 메모리이며 재시작/배포 시 복구되지 않습니다. 여러 uvicorn worker를 사용하지 않는 단일 서버 MVP입니다.

## 네 geometry와 긴 입력

`templates/ad.html`의 필드 순서와 `tokens.css`의 전략별 geometry를 사용합니다. emotional은 좌측 메시지·우측 비대칭 사진, price는 큰 가격 panel이 먼저, visual은 큰 중앙 사진이 먼저, brand는 큰 가게명 masthead가 먼저입니다. mood는 배경 token만 바꾸며 전략과 독립입니다. 대표색이 없어도 기본 중립 palette로 동작하며 이번 구현은 K-means를 색상에 적용하지 않습니다.

안전 여백54px(5%), 상품은 EXIF 표시 방향 적용 후 contain으로 배치합니다. crop·색 보정·새 상품 생성은 없습니다. body/CTA가 비면 요소 자체를 만들지 않습니다. facts와 생성 카피는 별도 필드이며 주소/Instagram이 있으면 네 광고에 원문 표시합니다. use_address_for_copy는 LLM 전송 옵션일 뿐 렌더링 표시 조건이 아닙니다. product_features는 생성 입력이며 광고에 별도 장문 사실 box로 추가하지 않습니다.

normal→compact→dense 순으로 실제 DOM overflow·bbox·요소 간 overlap을 검사합니다. 폰트 최소32px, Noto의 실제 glyph 높이에 맞춘1.5 line-height를 사용합니다. 과거 DESIGN_SPEC의 주요 글자 크기는 normal에서 적용하고 긴 입력은32px 이상 대체 layout을 사용합니다. 고정 copy의 모든 최대 길이와 개별 facts/연락처 경계값을 실브라우저에서 검사합니다. **모든 필드 최대 길이·많은 넓은 글리프를 동시에 입력하면 유한한 캔버스에 수용되지 않을 수 있으며 RENDER_LAYOUT_OVERFLOW로 실패합니다.** 자동 절단·ellipsis·축약은 없습니다. 새 필드 제한을 임의 도입하지 않습니다.

Facts와 생성 Copy는 기존 제어문자/HTML 정책을 유지합니다. Facts의 HTML 유사 문자열은 Jinja2 escape 후 문자로 표시하며 실제 HTML이 아닙니다. 기존 Facts/Copy의 줄바꿈은422입니다. product_features의 줄바꿈은 저장되지만 광고에 직접 렌더링하지 않습니다. 이 단계가 기존 입력 계약을 완화하지 않습니다.

## 보안·실행 경계

Jinja2 autoescape·trusted CSS만 safe 처리합니다. 사용자는 CSS/JS/URL/경로를 지정할 수 없습니다. 이미지·폰트는 서버가 확인한 bytes의 data URI이며 page의 CSP와 context network route 차단, JS 비활성화·service worker 차단을 적용합니다. 외부 URL/file URL을 사용하지 않습니다. 원본/가중치/세션 token을 worker 로그에 남기지 않습니다. worker stdout은 부모에게만 결과 JSON을 전달합니다.

요청별 Node worker는 네 페이지에서 Chromium 하나를 사용하고 finally에서 page/context/browser를 닫습니다. 전체90초 제한 초과 시 해당 worker tree만 종료합니다. 사용자 브라우저/기존 dev server를 종료하지 않습니다. worker 부재·설정/폰트/이미지 오류는 안전한 실패 코드로 응답합니다.

서비스 .venv에는 Jinja2 3.1.6/MarkupSafe 3.0.4만 추가했습니다. Python Playwright·torch/open_clip은 설치하지 않습니다. Node24와 frontend의 고정 Playwright1.64.0을 서버 worker가 재사용합니다. 따라서 **백엔드 렌더링만 실행해도 npm ci 및 Chromium 설치가 필요합니다.** B .venv-ml과 A .venv-analysis는 유지하고 .venv-rank는 만들지 않습니다.

## Candidate와 계측

Candidate v1.1의 candidate_id/strategy/revision/facts/copy/png/renderer/diagnostics를 그대로 반환합니다. B fixture/schema를 바꾸지 않고 JSON Schema로 호환성을 검사합니다. photo_sha256은 원본, processed_photo_sha256은 실제 선택 asset의 해시입니다(원본 선택이면 둘이 같음). 네 후보의 facts와 revision은 동일합니다.

renderer.text_boxes는 실제 DOM 위치·원문·폰트 크기/weight·색/overflow, product_bbox는 contain된 실제 이미지 rect를 기록합니다. 템플릿 버전은 전략별 ID를 포함합니다. 추가 계측은 `measurements[candidate_id]`에 별도로 두며 layout, 실제 글꼴(CDP), line_count, text rect, photo_frame/product rect, invalid를 제공합니다. text metadata와 bbox는 동일한 screenshot 전 DOM 측정에서 나옵니다. 픽셀/geometry 검증이 완전한 가독성 또는 상품 segmentation 품질 보증은 아닙니다. diagnostics는 unavailable, 수치는null, attention=null이며 가짜 측정값·점수·시선/CTR 예측은 없습니다.

## Windows 새 PC 실행

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend exec -- playwright install chromium
# 루트 .env는 비밀 없는 .env.example을 복사해 각 PC에서 준비
# HANJANG_COPY_PROVIDER=mock / HANJANG_COPY_ALLOW_PAID=false 유지
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
# 다른 터미널
npm.cmd --prefix frontend run dev
```

React http://127.0.0.1:5173 / Swagger http://127.0.0.1:8000/docs. 이번 검증 서버는 기존 서버 보존을 위해5182/8012를 사용합니다. 로컬 설치된 Chrome을 명시하려면 서버 실행 전 HANJANG_RENDER_CHANNEL=chrome으로 설정할 수 있지만 기본/CI는 고정 Playwright Chromium입니다. 폰트는 [라이선스/해시](../templates/fonts/README.md)와 함께 Git에 포함됩니다. 모델·API 키 없이 Mock 카피+렌더링을 사용할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m pytest
$env:RUN_RENDER_TESTS='1'
New-Item -ItemType Directory -Force artifacts/renderer | Out-Null
.\.venv\Scripts\python.exe -m pytest tests/service/test_rendering.py -q --basetemp artifacts/renderer/actual
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test:ci
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e
```

CI backend는 브라우저 없는 Store/API 검사, browser-e2e job은 Chromium 설치 후 경계값/실제 PNG 검사를 실행합니다. 로컬 이미지·metadata·스크린샷·trace는 Git 제외 artifacts/에만 보관합니다.
