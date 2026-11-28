# Original 사진 카드의 원형 맞춤 제외 — 2026-11-28

기준 main `42e291a`. B가 whole-photo의 원형 클리핑을 이미 해제했지만 A worker가 템플릿 ID만으로 원 안에 사진 전체를 넣는 축소를 수행했다.

## 변경

- `scripts/service_render_v3_worker.mjs`: 대상 5종의 circle 조건에 `!frame.classList.contains('whole-photo')`만 추가했다. whole-photo는 기존 rectangle-safe contain 배치를 사용한다. cutout 원형 맞춤·사진 전처리·종횡비·카피·B HTML/CSS는 그대로다.
- `template_v3.template_fingerprint()`에 worker 파일을 추가했다. 이전에는 HTML/CSS만 포함해 worker 변경을 감지하지 못했다. 기존 design snapshot·ranking·다운로드 fencing을 재사용한다. 이전 시안은 stale이고 새 시안이 필요하지만 카피/분석/유료 호출을 다시 만들지는 않는다.
- **VERSION 유지**: 공개 계약이나 B의 템플릿 측정 버전을 바꾸지 않았다. B limits.json의 HTML/CSS source hash 검증은 별도이며 유효하게 유지된다. worker만 바꿔도 fingerprint가 달라지고 이전 순위·다운로드가 거부되는 것을 테스트했다.

## 실제 Chromium 전후 비교

`artifacts/whole-photo-circle-fix/gallery.html` 및 `comparison.json`에 동일 사진·문구·스타일·템플릿의 전후 89쌍, PNG178장을 보존했다. 저장된 실제 카피를 재사용했으며 새 provider 생성은 없다.

|템플릿|짜장면 original 사진 면적 배수|에스프레소 original 사진 면적 배수|
|---|---:|---:|
|price_a|2.151|1.553|
|price_c|1.744|1.829|
|emotional_d|2.151|1.553|
|brand_a|2.151|1.553|
|brand_b|2.151|1.553|

측정은 사진 subject bbox의 width×height 비교이며 상품 자체가 차지하는 면적의 추정값과는 다르다. original은 사진 전체를 보존하므로 배경도 포함한다.

- 실제 로컬 사진 2개 × 16종 × original/cutout = 전후64쌍.
- 가로900×400·세로400×900·정사각600×600 RGB fixture × 대상5종 = 15쌍.
- 빈 본문/CTA 및 긴 문구 × 대상5종 = 10쌍.
- 대상 original35쌍 모두 면적 증가(전체 범위1.175~2.151배), 비율 유지·의도하지 않은 잘림 없음·새 사진/텍스트 bbox 침범0.
- cutout32쌍 및 비대상 original22쌍 **54쌍 픽셀 동일**. 이번 비교에서는 기존 price_c 픽셀 불안정도 재현되지 않았다.
- 모든 텍스트 내용·위치·글꼴·줄바꿈 측정 유지. PNG 변경에 결합되는 대비 증거 hash는 새 이미지로 갱신된다. 모든 출력 RGB1080×1350.
- 갤러리 Chromium178장 decode, console/pageerror0. 원본 사진·비용 원장 SHA 보존.

## 검증

```powershell
$env:RUN_RENDER_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/service/test_whole_photo_circle.py tests/service/test_copy_template_limits.py tests/service/test_designs.py tests/service/test_photo_mode.py -q
```

32 passed, 기존 AnyIO deprecation warning1. 실제 가로/세로/정사각 RGB·RGBA의 대상5종 배치, worker fingerprint 변화, stale ranking·다운로드409, 카피 재사용 및 v2 유지 포함.

별도 포트18195/15195의 `designs-v3.spec.ts`: 1 passed(33.5초), v2→v3·편집·가격 수정·PNG/PDF 다운로드·복원 확인. 카피는 Mock, ranking은 테스트용 응답이며 실제 ML 재추론으로 보고하지 않는다. 변경 없는 ML 모델·CLIP·배경 제거를 재실험하지 않았다. 테스트 전용 서버만 사용하고 운영 서버는 건드리지 않았다. GitHub 전체 회귀는 해당 PR Checks를 따른다.

## 품질 관찰과 한계

- 원본 사진 4종의 B 검증 세트는 로컬에서 확인하지 못해 사용 가능한 짜장면·에스프레소 2종과 비율 fixture로 검증했다. 치킨·케이크·볶음면의 실제 사진 검증을 했다고 주장하지 않는다.
- B 후속: brand_b의 빈 본문에서 큰 고정 여백, 극단적인 세로 사진의 좌우 여백, 원본 배경과 광고 배경의 조화는 템플릿/디자인 판단으로 남긴다. 사진을 키워 임의 크롭하거나 CSS를 수정하지 않았다.
- A 후속: 기존 cutout의 경계·잔여물과 저해상도 원본의 흐림은 이번 수정으로 해결되지 않는다. 이번 비교에서는 cutout 픽셀이 그대로이므로 개선·악화 모두 주장하지 않는다.
- original 모드의 subject_size 경고는 상품 검출이 아니라 사진 전체 bbox 한계가 있으므로 제거하지 않는다. 사람의 최종 디자인 승인은 미완료다.

유료 LLM·이미지 API·모델 다운로드0. 원장65건/$0.53191900(미확정 예약 포함 상한) SHA 보존. 서버 재시작·배포·main 병합 없음. 사진·PNG/PDF·실험 원장·환경 파일은 Git 제외다.
