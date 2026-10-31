# 11단계: 규칙 기반 가독성 진단

진단은 광고 선호도 ranking과 독립된 참고 도구입니다. 가독성 점수·구매율·매출·CTR·실제 시선·OCR을 측정하지 않으며 PNG와 사용자 원문을 자동 수정하지 않습니다. Candidate/B v1.1의 기존 `diagnostics` placeholder는 그대로 유지하고, 별도 응답과 렌더링 `measurements` envelope만 확장합니다. 프로필·실제 ML 연동은 범위 밖입니다.

## API와 상태

세션 헤더 `X-Hanjang-Session`, 소유권·24시간 TTL·`Cache-Control: no-store`는 기존 API와 같습니다.

`POST /api/v1/jobs/{job_id}/diagnostics`는 **동기 200**입니다. 백그라운드 생성 202나 Job 상태 변경이 아닙니다. 요청 예:

```json
{
  "expected_render_revision": 2,
  "expected_candidates": [
    {"candidate_id": "emotional-id", "asset_id": "11111111111111111111111111111111"},
    {"candidate_id": "price-id", "asset_id": "22222222222222222222222222222222"},
    {"candidate_id": "visual-id", "asset_id": "33333333333333333333333333333333"},
    {"candidate_id": "brand-id", "asset_id": "44444444444444444444444444444444"}
  ]
}
```

실제 ID는 현재 rendering 응답에서 가져옵니다. 네 후보 ID·asset ID는 각각 고유해야 합니다. 요청 한도는 기존 16KiB입니다.

`GET /api/v1/jobs/{job_id}/diagnostics`는 최근 결과를 재조회하며 분석을 새로 실행하지 않습니다. 응답은 `job_id`, `operation:"diagnostics"`, `status`, `revision`, `is_current`, `rules_version`, `results`, `warnings`, `error`, `expires_at`입니다. `pending`은 아직 결과 없음, `processing`은 다른 동기 요청이 현재 계산 중임을 관찰한 상태, `completed`는 계산 완료, `failed`는 전체 계산 실패입니다. 기존 draft Job의 상태는 바뀌지 않습니다. POST 계산 실패도 200/failed이며 `error.code=DIAGNOSTICS_FAILED`를 제공합니다. 개별 규칙 실패는 다른 정상 측정값을 유지하며 해당 규칙만 unavailable로 반환합니다.

후보별 결과: `candidate_id`, `strategy`, `asset_id`, `coverage`, `rules`. 규칙별 결과: `rule_id`(contrast/font_size/layout/density), `status`(normal/caution/problem/unavailable), `coverage`(complete/partial/unavailable), `measured_value`(객체 또는 null), `unit`, `criterion`, `explanation`, `action`. 측정 누락은 null이며 0점·정상으로 바꾸지 않습니다. 일부 측정 불가 시 유효한 수치와 coverage를 함께 표시합니다. NaN/Infinity는 반환하지 않습니다.

오류: 인증 누락·잘못된 세션 401, 다른 소유자·없는/만료된 작업은 기존 upload 정책, 잘못된 본문 422, 초과 본문 413. 현재 성공 광고 없음은 409 `DIAGNOSTICS_RENDER_NOT_READY`, 기대 revision/ID 불일치 또는 계산 중 snapshot 변경은 409 `DIAGNOSTICS_SOURCE_CHANGED`, PNG 소유·형식·해시 불일치는 409 `DIAGNOSTICS_ASSET_INVALID`(파일 자체 누락은 기존 asset 오류), 동일 작업의 동시 실행은 503 `DIAGNOSTICS_BUSY`입니다. 내부 파일 경로를 오류에 포함하지 않습니다.

## 최신성·동시성·보존

시작·완료·재조회 시 현재 사진/저장 입력/카피/template snapshot, revision, 네 후보·asset ID, 원문 facts, 실제 PNG SHA-256 및 등록 해시를 검증합니다. 계산은 복제된 snapshot에서 실행하고, 완료 시 다르면 결과를 게시하지 않습니다. 이전 결과는 보존하되 조회 시 `is_current=false`로 반환하고 현재 광고의 진단으로 표시하지 않습니다. 새 snapshot의 성공 결과가 최신 슬롯을 대체합니다. 같은 snapshot과 규칙 상수의 완료 결과는 재사용합니다. 후보 순서는 API 내부 ID 비교로 확인하며 B 계약을 변경하지 않습니다.

진단 전용 per-job busy는 동기 함수의 finally에서 해제하며 렌더링·편집 worker active와 분리합니다. PNG·편집·PDF·ranking 상태를 잠그거나 변경하지 않습니다. 성공한 편집은 이전 진단을 stale로, 실패한 편집은 기존 진단을 유지합니다. 메타데이터는 인메모리이며 서버 재시작 시 유실되고 작업 만료 시 제거됩니다.

## 규칙과 근거

| 규칙 | 계산·판정 | 한계 |
| --- | --- | --- |
| 글자 크기 | 실제 Chromium font-size, 현재 CSS px=PNG px(배율1). `SMALL_FONT_PX=36.0` 미만 **주의**, 같으면 정상 | 조정 가능한 초기 서비스 휴리스틱. 보편 기준·모바일/인쇄 보장이 아님 |
| 텍스트 밀도 | 캔버스 내 text block bbox **합집합** / (1080×1350), `DENSITY_LIMIT=.40` 초과 **주의**. 중복 제외, 누락 시 하한값·partial | 글자 잉크 면적이나 이해도 점수가 아님 |
| 경계·겹침 | 캔버스 이탈은 문제. 1px 초과 bbox 교차 및 DOM overflow는 주의 | bbox만으로 실제 글자 가림·의도적 배치·투명 이미지 영역을 확정하지 않음 |
| 명도 대비 | 검증된 전경 RGB와 실제 배경 픽셀만 sRGB 상대휘도 `(Lmax+.05)/(Lmin+.05)`. 일반4.5:1, 큰 글자3:1 미만 문제 | 측정할 수 없는 항목은 null/unavailable. 접근성 인증이 아님 |

36px/40%는 `backend/app/services/diagnostics_engine.py` 상수이며 변경하면 캐시 fingerprint도 달라집니다. 대비 큰 글자는 24 CSS px 이상 또는 14pt(18.666…px) 이상·weight700 이상이며 판정 전 반올림하지 않습니다. [W3C 대비 참고 기준](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum)을 사용합니다.

## 실제 렌더링 대비 계측

원래 PNG를 먼저 저장한 뒤, 같은 Chromium 페이지에서 글자 fill만 숨긴 **별도 배경 캡처**를 생성합니다. bbox 불변을 확인하고 글자 줄 rect 전체의 불투명·균일 배경 픽셀을 검사합니다. 전경은 실제 computed color와 대응 Candidate text metadata가 일치해야 하며 증거에 최종 PNG 해시를 결합합니다. CSS 배경색만으로 배경을 단정하거나 안티앨리어싱된 글자 픽셀로 전경색을 추측하지 않습니다.

이미지와 교차, 조상 gradient/background-image, opacity/filter/blend/transform, pseudo paint, text shadow/stroke, fill 불일치는 보수적으로 제외합니다. 비균일/투명 배경·캡처 실패·이전 renderer metadata는 unavailable입니다. 전체 paint engine을 재현하지 않으므로 미리보기 검토가 필요합니다. 배경 캡처는 내부 일회성 데이터이며 공개 응답에 PNG base64를 남기지 않습니다. 캡처 실패는 원래 PNG 렌더링을 실패시키지 않습니다. template version은 `four-layouts-v2-evidence`; 디자인·배치는 변경하지 않습니다.

## 화면·실행

최신 성공 광고 아래 별도 진단 영역에서 **가독성 진단 실행**을 누릅니다. 네 후보의 네 규칙, 측정값·coverage와 펼침 가능한 근거/조치를 확인합니다. 문구 편집→재렌더링 후 이전 진단은 숨겨지고 새 revision으로 재진단합니다. 순위는 독립적으로 유지됩니다. 새로고침은 세션과 Job이 살아 있으면 GET으로 복원하며 늦은 이전 응답은 무시합니다.

추가 패키지·모델·유료 API는 필요하지 않습니다. 기존 Python/Pillow·Chromium·Noto Sans KR을 사용합니다. 검증 명령과 실제 결과는 [DIAGNOSTICS_TEST_REPORT](DIAGNOSTICS_TEST_REPORT.md)를 따릅니다.
