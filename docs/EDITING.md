# 10단계 문구 편집·재렌더링·PNG/A4 PDF

2026-10-31 사용자 승인. 이번 단계는 headline(1–60자), body(0–160자), cta(0–30자)만 후보별 편집한다. 사실 정보는 기존 상품 입력에서만 변경한다. 자유 디자인·상품 변형·LLM 재호출·실제 ML 연결은 포함하지 않는다. A4는 기존 로드맵에서는 OPTIONAL이지만 사용자 승인으로 **이번 10단계에서는 PNG와 함께 필수 완료 조건**이다.

## 데이터와 revision

CopyStore의 최초 카피·copy_key를 변경하지 않는다. 동일 사진/입력/카피/template snapshot에 별도 편집 ID와 네 후보 성공본을 연결한다. 같은 계보의 candidate_id/strategy/facts/원본·선택 사진 해시는 보존한다. 수정된 후보는 기존 Chromium으로 렌더링하고 다른 세 후보는 asset ID와 bytes를 재사용한다. 네 Candidate와 png reference의 revision은 모두 새 revision이다. Candidate/B JSON schema는 변경하지 않는다.

완료 후 네 후보를 한 번에 공개한다. 편집 상태와 마지막 성공 render는 별도로 조회하며 실패 중에도 기존 성공본을 유지한다. revision은 job 내 단조 증가하고 실패한 target을 재사용하지 않아 번호에 빈 구간이 있을 수 있다. 최신 성공본을 다시 편집할 수 있다. 새 입력·사진·카피 계보의 ID는 기존 생성 정책대로 새로 발급한다.

같은 원본 생성 snapshot의 rendering POST는 편집 최신 성공본을 반환하며 원래 카피로 되돌리지 않는다. 입력·사진·카피가 바뀌면 이전본은 stale이다. 원래 snapshot으로 돌아오면 기존 캐시를 재사용하는 기존 정책을 유지한다. 저장 metadata는 메모리이며 서버 재시작 후 복구하지 않는다.

## API — 모두 /api/v1 및 X-Hanjang-Session

### PATCH /jobs/{job_id}/candidates/{candidate_id}

```json
{
  "expected_revision": 1,
  "expected_candidate_ids": ["실제ID1", "실제ID2", "실제ID3", "실제ID4"],
  "expected_asset_id": "현재선택사진의32자리ID",
  "expected_copy_key": "현재원본카피의32자리키",
  "expected_input": {
    "facts": {"store_name":"가게", "product_name":"상품", "price_text":" 3,000 원 ", "address":null, "instagram_handle":null},
    "mood":"warm", "product_features":null, "use_address_for_copy":false
  },
  "copy": {"headline":"한 잔의 여유", "body":"", "cta":""}
}
```

예제의 ID 설명은 실제 GET 응답의 값으로 바꾼다. copy는 전체 교체이며 facts/strategy/CSS/경로 추가는 거부한다. 202 및 Location=/api/v1/jobs/{job_id}/editing. 한 job에서 동시 편집은 하나만 실행한다. 기존 렌더러의 단일 실행 제한도 공유한다.

### GET /jobs/{job_id}/editing

`{job_id, operation:"editing", status, status_url, edit_id, candidate_id, base_revision, target_revision, is_current, error, expires_at}`

- 상태 pending/processing/completed/failed. 미요청이면 ID와 revision은 null.
- is_current는 현재 성공본과 편집의 source/revision 대응 여부이며 성공을 뜻하지 않는다. 실패는 error와 status로 확인한다.
- 완료 후 GET rendering에서 네 최신 Candidate를 조회한다. 새로고침 시 진행 중 editing을 polling하고 성공 revision을 다시 읽는다.
- 같은 요청의 processing/completed는 source와 현재 revision이 대응할 때 재사용한다. 실패는 명시 재시도한다. 무변경은 새 revision/렌더링 없이 completed를 반환한다.
- 서로 다른 동시 수정·오래된 revision·현재 입력/사진/원본 카피 불일치는409. 완료 시 snapshot·TTL·선택 사진과 PNG 해시를 재검증한다.

### GET /jobs/{job_id}/candidates/{candidate_id}/download

필수 query: `format=png|pdf&expected_revision=N`.

- 최신 completed/is_current render만 허용하고 해당 Candidate, revision, job 소유 asset, 실제 RGB 불투명1080×1350 PNG와 등록된 SHA256을 검사한다.
- PNG는 미리보기와 동일 bytes이다. PDF는 같은 PNG를 담은 세로 A4 한 페이지다.
- 200 binary, image/png 또는 application/pdf. no-store/nosniff/attachment, 안전한 ASCII fallback 및 UTF-8 filename*를 사용한다. 세션 토큰·내부 경로를 URL/파일명에 넣지 않는다.
- 브라우저는 인증 fetch → Blob 다운로드를 사용한다. 기존 인증 asset 미리보기는 유지한다.
- PDF는 기존 Chromium 사용, 210×297mm, 최소10mm 여백·중앙 배치다. Chromium print의 비대칭 반올림을 피하려고 이미지716×895 CSS px(약189.44×236.80mm, 좌우약10.28mm·위아래약30.10mm)를 사용해 실제 PDF draw matrix의4:5 비율도 검증한다. 한글은 PNG 픽셀에 포함되어 폰트 대체가 없으며 검색 가능한 텍스트/300dpi 원본은 아니다.
- PDF 생성은 PNG와 독립이며 revision+candidate+PNG해시별 메모리 캐시다. 생성 후에도 source/TTL/PNG를 다시 검사한다. 동시 PDF 생성은 하나로 제한하고90초 timeout은 소유 worker tree만 종료한다.

## 오류

기존401 인증/404 소유권·리소스/410 만료, PATCH16KiB 초과413, schema422 유지. PATCH CORS를 추가한다.

| code | HTTP/작업 상태 |
| --- | --- |
| EDIT_SOURCE_CHANGED | 409 또는 완료 검증 실패의 failed |
| EDIT_BUSY / PHOTO_PROCESSING_BUSY | 409 |
| EDIT_UNSUPPORTED_GLYPH | 422, 원래 광고 유지 |
| EDIT_ASSET_INVALID | 409 또는 failed |
| RENDER_LAYOUT_OVERFLOW/RENDER_FONT_UNAVAILABLE/RENDER_UNSUPPORTED_GLYPH/RENDER_TIMEOUT/EDIT_FAILED | editing failed, 마지막 성공본 보존 |
| DOWNLOAD_SOURCE_CHANGED / DOWNLOAD_ASSET_INVALID | 409 |
| PDF_BUSY / PDF_FAILED | 503, PNG 보존 |

빈 선택 문구는 숨긴다. 일반 사용자 카피는 Copy 스키마·실제 폰트 지원 정책으로 검증하며 자동 교정·요약·삭제하지 않는다. 사용자 편집은 사용자 작성 문구이며 의미적 사실 검증을 완전히 자동 보장하지 않는다. facts는 별도 읽기 전용으로 표시한다.

## ranking과 UI

성공 편집 후 이전 ranking은 전체 후보 snapshot/revision 불일치로 stale이다. 사용자가 명시적으로 새 임시 순위를 요청한다. Mock 안내는 유지하며 성공본이 바뀌기 전에는 이전 성공본 기준 상태를 보여준다.

편집 화면은 현재 성공본과 수정중 값을 분리한다. 무변경 적용 금지·취소 후 초점 복원·처리중 중복 버튼 비활성화·입력/사진 변경 후 늦은 응답 무시·모바일 줄바꿈을 적용한다. 다운로드 중에는 스냅샷 변경 시 응답을 저장하지 않는다. 새로고침 시 메모리에 존재하는 job만 복원 가능하다.

## 실행·검증

새 런타임 의존성/폰트/모델은 없다. 기존 Node24/Python3.12/Playwright Chromium 환경을 재사용한다. 서비스는 Mock/paid=false, 기존 실행 스크립트와 로컬 설정을 사용한다. 이번 확인 포트는 React5186/FastAPI8013이다. 기존 포트 사용 프로세스를 임의 종료하지 않는다.

```powershell
$env:RUN_RENDER_TESTS='1'
$env:HANJANG_RENDER_CHANNEL='chrome' # 설치 Chrome 사용 시만
.\.venv\Scripts\python.exe -m pytest
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test:ci
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e
```

PDF 테스트는 Chromium 출력의 단일 페이지/MediaBox/손실 없는 RGB 이미지 stream/배치 matrix를 검사한다. 별도 PDF parser를 런타임에 추가하지 않는다. Chrome PDF viewer로 실제 페이지를 열어 시각 검수한다. 최종 수치·제약은 EDITING_TEST_REPORT.md를 따른다.
