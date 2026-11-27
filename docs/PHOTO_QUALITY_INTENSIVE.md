# 실제 사진·광고 시각 품질 비교 — 2026-11-27

PR #82 MERGED/main `2d2982c`를 확인하고 `feat/photo-quality-intensive`에서 수행했다.
**권고: full u2net을 명시적 선택 후보로 제공하되 기본 u2netp는 유지한다.**
짜장면의 실제 광고는 개선됐지만 천 잔여물과 구성품 경계 문제가 남고, 투명 용기·다른 카테고리 실사진 검증이 부족하다.
자동 점수나 haze 감소로 품질을 확정하지 않았다. 아래 시각 평가는 Codex의 AI 정성 관찰이며 사람 평가는 미실행이다.

## 원인과 실제 비교

요청된 기존 PNG8장을 원본 크기로 확인했다.

- u2netp는 짜장면의 젓가락 일부·천·받침을 불완전하게 분리했다.
  기존 matte는 모든 alpha>=128을 보존하므로 모델이 불투명하게 예측한 잔여물을 제거하지 않는다.
  이를 면적/거리만으로 삭제하면 분리된 실제 음식·소품도 잃을 수 있어 변경하지 않았다.
- 접시/받침의 불규칙한 경계는 모델의 전경 판단 문제다. alpha를 더 깎아 복원할 수 없다.
- `brand_a`/`price_c`의 작은 사진과 고정 여백, `emotional_b`의 상단 장식 가림은 템플릿과 구분했다.
- 기존 `prepare_product()`는 alpha>=16의 **모든** 지지 영역과2% pad를 사용한다.
  작은 잔여물이 포함되면 bbox와 원형 containment가 커져 실제 중심 상품이 작아질 수 있다.
  dominant connected component를 실제 상품으로 단정하거나 나머지를 삭제하지 않았다.

실제 원본과 입력이 함께 확인된 사진은 짜장면800×800과 에스프레소600×400이다.
11종 비교 이미지가 있다고 해서 그 상품 원본을 확보했다고 보고하지 않는다.
투명 유리컵·얼음·액체·비식품의 실제 모델 품질은 미검증이다.

## 모델 조사와 선별

rembg 패키지의 MIT와 각 가중치의 이용 조건을 구분했다.
[공식 rembg 모델 목록](https://github.com/danielgatis/rembg#models),
[U-2-Net 라이선스](https://github.com/xuebinqin/U-2-Net/blob/master/LICENSE),
[IS-Net 사용 조건](https://github.com/xuebinqin/DIS#7-term-of-use),
[BiRefNet Lite 모델 카드](https://huggingface.co/ZhengPeng7/BiRefNet_lite)를 확인했다.

|후보|공식 rembg ONNX 크기|이용 조건 근거|이번 결정|
|---|---:|---|---|
|u2netp|4,574,861 bytes|U-2-Net 저장소 Apache2.0|기존 파일 재사용, baseline|
|u2net|175,997,641 bytes|같은 U-2-Net 저장소 Apache2.0|공식 export를 실제 비교, opt-in 구현|
|IS-Net general|178,648,008 bytes|공식 README는 코드/평가 metric Apache2.0, 데이터는 별도 조건. 가중치 상업 이용 범위를 단독으로 확정하지 않음|미설치·미측정. 상업 배포 전 가중치 조건 명확화 필요|
|BiRefNet Lite|224,005,088 bytes|저자 HF 모델 카드 MIT. 배포 시 해당 저작권·라이선스 고지 보존|공식 export 실제 비교, opt-in 제공하되 기본 권고 안 함|
|BiRefNet general|972,666,916 bytes|저자 [모델 카드 MIT](https://huggingface.co/ZhengPeng7/BiRefNet)|Lite의 비용/구성 손실을 확인해 추가 대용량 설치 안 함|

코드 저장소의 라이선스가 모든 데이터 권리까지 보장한다고 표현하지 않는다.
모델을 타인에게 재배포할 경우 코드/가중치 고지와 출처를 함께 검토해야 한다. 가중치는 이번 Git에 포함하지 않았다.
두 신규 파일은 공식 rembg 릴리스 크기·공식 session의 MD5를 확인하고 로컬 SHA256을 기록했다.
**upstream MD5와 로컬 SHA256을 구분**하며 로컬 SHA를 공식 발표 checksum이라고 부르지 않는다.
런타임은 registry에 고정한 SHA256을 확인한다.

## 측정 — 같은 CPU/각 사진3회

Windows, 물리 RAM 약31.5GiB, Intel Arc130V 환경에서 ONNX CPUExecutionProvider/intra-op1로 측정했다.
GPU 가속·전용 VRAM·동시 서비스 부하는 벤치마크하지 않았다. 기존 환경을 업그레이드하지 않았다.

|모델|세션 로딩|짜장면 추론 중앙값|에스프레소 추론 중앙값|worker peak working set|
|---|---:|---:|---:|---:|
|u2netp|0.087초|0.595초|0.483초|0.666GiB|
|u2net|0.508초|1.315초|1.215초|0.987GiB|
|BiRefNet Lite|4.602초|13.836초|12.450초|11.759GiB|

세션 로딩1회와 같은 세션의 반복 추론3회다. 서비스 전체 지연이나 p95로 해석하지 않는다.
메모리는 Windows가 기록한 격리 Python worker의 peak working set이며 Python·ONNX·라이브러리와 두 사진6회 처리를 포함한다.
추가 psutil 설치 없이 OS API로 측정했다. 원시 시간과 메모리는 로컬 `resources.json`, 모델별 `benchmark.json`에 있다.
추론 worker는 socket 접속을 차단했으며 모델 자동 다운로드가 없었다.
모든 모델·사진의 반복 마스크 SHA가 일치했다. 마스크 적용 전후 동일 격자의 RGB도 일치했다.

## 사진·실제 광고 결과

같은 저장 실제 LLM 카피/템플릿/style snapshot으로 A기존/Bfull u2net/Coriginal을 비교했다.
추가로 BiRefNet Lite 및 raw model-alpha를 비교해 **46장**을 실제 Chromium으로 생성했다. 렌더링 실패0.
원본 사진/카피/템플릿/CSS/색상 스타일은 수정하지 않았다.
`summary.json`에서12개 A/B/C 그룹의 카피·style 동일성을 확인한다.

|사례|개선/남은 문제|
|---|---|
|짜장면 visual_a/c/d|full u2net은 떠 있는 젓가락 조각을 제거하고 접시·받침 외곽을 더 연속적으로 보존. 어두운 배경에서도 깨진 왼쪽 잔여물이 감소. 하단 천과 받침 왼쪽의 잘린 형상은 남음|
|짜장면 BiRefNet 대안|접시 하단은 깔끔하지만 나무 받침 하단이 사라지고 양옆만 남음. 전체 구성을 유지하려는 요구에는 명확한 손실 위험. 가장 낮은 haze가 최선이 아님|
|짜장면 brand_a|잔여 조각 감소로 기존 containment 안에서 중심 상품이 커 보이는 사례. 그래도 슬롯·고정 여백은 바뀌지 않아 큰 상품 광고가 되지는 않음|
|에스프레소|full u2net의 접시 외곽은 비교적 연속적이고 숟가락·손잡이 유지. 컵 상단의 얇은 밝은 테두리는 남음. 모델 교체의 개선 폭은 짜장면보다 작음|
|에스프레소 emotional_b|모든 cutout 모델에서 상단 장식과 사진의 겹침이 남음. 배경 제거 원인으로 오인하지 말고 B 템플릿 검토|
|original|전체 젓가락·받침·천과 촬영 배경을 온전히 보존하여 합성 잔여물이 없음. 다만 작은 사진 슬롯이나 상단 가림은 원본 모드만으로 해결 안 됨|
|그림자|템플릿의 동일 그림자를 유지한 통제 비교. 경계 개선으로 덜 인위적인 부분은 있으나 사진이 평면 배경에 떠 있는 인상은 완전히 해결하지 못함|

소품을 무조건 삭제한 것이 성공 기준이 아니다. 젓가락을 온전히 포함해야 하는 광고라면 original이 더 적절할 수 있다.
마스크의 정답 annotation이 없으므로 상품 보존율/IoU/미적 객관 점수를 만들지 않았다.
`geometry.json`에는 전체 support bbox와 최대 연결 성분 bbox/면적을 함께 기록하되 의미적 상품 판정으로 사용하지 않았다.
렌더러의 보수적인 trim/contour 정책은 그대로이며, 이미 잘린 부분을 새 픽셀로 복원하지 않는다.

새 광고46장의 PNG와 측정값을 검증했고 gallery에서46개 모두1080×1350 decode/브라우저 오류0을 확인했다.
진단은 font_size normal46, layout caution5, image_crop caution14, subject_size caution11,
subject_size unavailable12, contrast unavailable6이다. original의 상품 bbox unavailable을 임의로 정상 판정하지 않았다.
경고 수를 낮추려고 템플릿·진단 기준을 바꾸지 않았다. Codex의 시각 검토는 지정8장과 대표 비교 이미지 중심이며 사람 평가가 아니다.

## A 코드 구현과 안전한 사용

- `photo_models.py`: 검증한3개 모델만 명시적 registry. 외부 서비스·미확인 임의 모델·자동 다운로드 없음.
- `LocalRembg`: 파일/크기/stream SHA 확인 후 해당 rembg session을 CPU로 로드. `download_models()`는 지정된 로컬 경로만 반환.
- `photo_model_name=u2netp`, `photo_matte_mode=cleanup`을 기본으로 유지했다.
  새 후보는 `u2net`/`birefnet-general-lite`를 명시하고 **이름과 일치하는 photo_model_path도 함께 설정**해야 한다.
  잘못된 모델을 넣으면 기존 PHOTO_PROCESSING_FAILED 계약으로 실패하며 다른 모델로 조용히 대체하지 않는다.
- `model-alpha`는 추가 hard threshold를 적용하지 않는 **명시적 실험 옵션**이다.
  기존 원본 alpha와 min으로 결합하고 RGB/프레임/비율/EXIF/최대1600 리사이즈 정책은 그대로다.
  실제 투명 용기의 우수성을 확인한 옵션이 아니며 기본으로 권하지 않는다. 합성 semi-transparent 입력으로 알파 보존만 검사했다.
  기존 마스크 유효성 검사(alpha>127 전경 유무)는 유지하므로 전부 낮은 알파인 결과는 실패·원본 사용 경로로 남는다.
- 기존 `u2netp-matte-cleanup-v1-preserve-solid` 버전은 그대로다.
  새 모델은 `모델명-SHA앞12자리-정책버전`, raw 정책은 `model-alpha-v1`로 구분한다.
- 완료된 기존 photo/asset은 모델 설정 변경만으로 재처리/교체하지 않는다. 새 업로드/아직 처리 안 된 사진부터 새 설정이 적용된다.
  기존/새 처리 자산을 함께 보존하며 선택된 실제 PNG/asset hash가 바뀔 때만 render/design/ranking snapshot이 무효화된다.
  original 모드와 카피·분석 재사용/부분 수정·다운로드 경로는 변경하지 않았다.

모델 준비 명령(이번에는 이미 준비되어 재다운로드하지 않음):

```powershell
.\.venv\Scripts\python.exe scripts/service_download_photo_model.py --download --model u2net
```

추후 승인된 **별도 로컬 프로세스**에서만 `HANJANG_PHOTO_MODEL_NAME=u2net`,
`HANJANG_PHOTO_MODEL_PATH=<프로젝트>/artifacts/models/rembg/u2net.onnx`,
`HANJANG_PHOTO_MATTE_MODE=cleanup`을 함께 전달한다. 이번에는 .env를 쓰거나 운영 서버를 재시작하지 않았다.
파일이 없으면 명시적 다운로드 명령을 먼저 수행해야 하며 `/ready`의 파일 존재 여부만으로 checksum/품질을 판단하지 않는다.

정확한 로컬 모델 경로(프로젝트 루트 기준):

- `artifacts/models/rembg/u2netp.onnx` — 기존 파일 보존.
- `artifacts/models/rembg/u2net.onnx` — SHA `8d10d2f3bb75ae3b6d527c77944fc5e7dcd94b29809d47a739a7a728a912b491`.
- `artifacts/models/rembg/birefnet-general-lite.onnx` — SHA `5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333`.

## 로컬 결과물과 B 요청

`artifacts/photo-quality-intensive/`의 `gallery.html`은 같은 템플릿 A/B/C를 나란히 표시한다.
`blind-gallery.html`은 처리 조건을 숨기고 상품/템플릿을 표시한다. 해제키는 `blind-key-local.json`이며 엄격한 이중맹검은 아니다.
`jjajang-visual_a-comparison.png`, `jjajang-brand_a-comparison.png`, `espresso-emotional_b-comparison.png`부터 비교할 수 있다.
모델별 raw/후처리 mask, 밝은/어두운 배경 합성, 서비스 worker 결과, geometry/diagnostics도 모두 보존했다.

B에게 전달할 요청(코드는 수정하지 않음):

1. `brand_a`, `price_c`: 사진 처리 개선 뒤에도 작은 슬롯과 과도한 빈 공간이 유지된다. 상품 중심 전략의 최소 크기/슬롯 재검토.
2. `emotional_b`: 에스프레소 컵 상단에 띠처럼 남는 부분은 장식/텍스트 배경과 사진의 겹침이다. cutout/original 모두 실제 PNG 비교 후 가림 정책 검토.
3. `visual_c`: 큰 사진과 어두운 배경에서는 잔여 천/외곽과 그림자 부조화가 더 드러난다. 사진 크기에 따른 그림자 강도/방향·접지감 조정 논의.
4. original의 온전한 구성이 더 적합한 사진에 대해, 기존 카드 모드의 상품 크기와 텍스트 여백도 함께 검토.
5. AI 배경/레이어/예약 영역은 [별도 사전 설계](AI_BACKGROUND_HYBRID_PROPOSAL.md)를 바탕으로 합의 후 PoC. 이번에는 이미지 API 호출/템플릿 변경0.

## 검증 및 보존

관련 사진·모드52 passed, 전체 backend866 passed/45 skipped를 실행했다. skip은 별도 Chromium/실제 모델 opt-in이다.
실제 새 모델 worker4조건, 실제 Chromium46장, 실제 B 모델 adapter15 passed를 별도로 확인했다.
추가 독립 TestClient 앱에서는 실제 u2net 처리 → v2/v3 Chromium8시안 → 실제 bt-logistic-v1 순위 →
부분 수정/PNG·PDF 다운로드 → original/cutout 왕복을 확인했다. `api-replay/`에 편집 PNG/PDF와 응답을 보존했다.
카피만 저장 실제 `l-jj` 응답을 Mock provider 표시로 재생했으며 새 LLM 생성으로 보고하지 않는다.
실제 RGB 보존·마스크 결정성·원본 SHA·기존 오류·부분 수정/다운로드·stale 검증과 Mock 여부는 실행 기록을 구분한다.
새 실제 LLM 생성0, 이미지 API0, 외부 배경 제거 서비스 전송0.
LLM 원장42건/$0.19978650, SHA `43d7e939de8cea8d82357188ce528ae97f1e087726248605518e3ce538834084` 유지.
사용자 사진·모델·환경·transfer·기존 결과물을 보존했다. 운영 서버/터널/배포/main 병합은 변경하지 않았다.
