# 상품 사진 운영 품질 판단 — 2026-11-28

기준 main `79fc4ba`(PR #90 포함). **검증된 두 불투명 음식/도자기 컵에는 Full U2Net + cleanup을 권고한다. 일반 기본 u2netp는 유지한다.** 투명 용기·복잡한 음식·비식품 실사진이 부족해 모든 상품에 대한 기본 전환은 확정하지 않는다. 실행 중인 서버/.env/활성 설정은 변경하지 않았다. 아래 시각 평가는 Codex의 정성 관찰이며 사람 평가가 아니다.

## 실제 결과와 선택

기존 [모델 실험](PHOTO_QUALITY_INTENSIVE.md), [matte 검증](PHOTO_MATTE_RESULTS.md), [original 카드 수정](WHOLE_PHOTO_CIRCLE_FIX.md), [배경 PoC](AI_BACKGROUND_POC_RESULTS.md)의 원본·마스크·실제 카피·분석·가중치를 재사용했다. 새 모델 벤치마크나 유료 생성을 반복하지 않았다.

|비교|실제 관찰|결정|
|---|---|---|
|A u2netp → B Full U2Net|짜장면 visual_a에서 독립적으로 뜬 젓가락 조각과 왼쪽의 부서진 배경 경계가 줄어듦. 하단 천·받침 일부는 남음. 에스프레소 접시·손잡이·숟가락 유지, 개선 폭은 작음|기존 Full 모델을 실제로 선택할 수 있는 운영 실행 경로 보완|
|C 한 픽셀 인접 faint alpha 복원|불투명 영역/RGB 보존. 바뀐 alpha는 짜장면438px·커피811px. 밝고 어두운 배경·최종 광고에서 뚜렷한 이득 미확인. 흰 경계 번짐 위험도 있음|가설만 보존, 운영 후처리에 추가 안 함|
|기존 BiRefNet Lite 결과|접시 밑은 깔끔하지만 받침 하단을 잃고 양옆만 남음. 기존 높은 CPU/메모리 부담도 있음|재추론/운영 확대 안 함|
|D original|소품과 촬영 맥락을 온전히 보존. PR #90의 카드 확대 유지. 배경과 광고 색상의 충돌은 상품별 판단 필요|모델 불확실·구성품 보존이 중요할 때 권장 경로 유지|
|그림자 없음 / 작은 단일 shadow|일부 halo는 약해지지만 촬영 광원·접지면을 모르면 자연스러움이 일관되지 않음|B CSS와 중복되는 A 그림자 계층은 도입 안 함|

숟가락·젓가락·받침이 항상 제거 대상이라고 가정하지 않는다. Full U2Net도 실제 상품으로 판단해야 할 부분을 잃을 수 있으며 잘린 RGB를 후처리로 복원했다고 주장하지 않는다. 전체 소품 보존이 필요하면 original을 선택한다.

## 원인 분리

- 잔여물·불연속 외곽: 모델 alpha의 전경 판단. cleanup은 모든 alpha>=128을 유지하므로 불투명하게 예측된 잔여물도 남는다. 작은 연결 성분을 삭제하거나 최대 성분만 남기는 정책은 적용하지 않았다.
- bbox: 약한 alpha를 포함한 전체 지지 영역이 크기를 좌우한다. 잔여물과 실제 분리 소품을 구별할 정답이 없어 배치용 bbox를 임의로 축소하지 않았다. PR #90의 original/원형 cutout 배치는 그대로다.
- 흐림: 실제 원본은 짜장면800×800·에스프레소600×400이다. B Full visual_a의 준비 이미지→배치 scale은 각각1.397배·2.306배다. 큰 광고에서 보이는 해상도 한계를 sharpening·RGB 보정으로 숨기지 않았다. 이 두 입력은1600px 이하라 처리 단계 resize도 발생하지 않았다.
- 반투명처럼 보임: `visual_c`, `emotional_b`의 **전경 gradient가 실제 PNG에서 상품 하단을 덮는다**. 같은 alpha에서 gradient만 끈 격리 비교4장으로 분리했다. B의 빈 본문 조건 실측은 visual_c y860/h170, emotional_b y850/h130. 템플릿/입력별 실제 값은 `overlay-results.json` 참조.
- 이번 갤러리의 이미지 opacity=1/filter=none을 Chromium에서 확인했다. 조사한 기존 photo-quality/최종 비교 갤러리에도 선택에 따른 fading CSS는 없다. 다른 모든 과거 UI까지 검사했다고 주장하지 않는다.
- 합성 그림자: B의 두 단계 drop-shadow가 상품 전체 외곽에 적용된다. 접지면/광원 정보 없이 또 다른 A 그림자를 더하면 중복된다. 실험 효과는 별도 preview이며 서비스 snapshot으로 재사용하지 않는다.

## 구현: 선택한 모델이 실제로 실행되도록

기존 presentation 실행기는 이름을 전달하지 않았고 local 실행기는 u2netp hash만 허용했다. offline model probe도 이름 없이 LocalRembg를 생성했다. Full 모델 경로만 바꾸면 잘못된 session/검증을 사용하거나 거부되는 원인이었다.

- 두 실행기에 `photo_model_name`, `photo_model`, `photo_matte_mode`를 일관되게 연결하고 process 환경을 finally에서 복원한다. 기존 설정 생략 시 u2netp/cleanup 유지.
- local preflight·readiness는 registry의 이름·크기·SHA256을 검증한다. 원래 파일 존재만 확인하던 ready 판정을 강화했다. 모델 로드·다운로드·추론은 하지 않는다. 최대8개 file identity/metadata 기반 digest 캐시이며 inference의 독립적인 checksum 검증도 유지한다.
- `service_model_check.py`가 선택한 모델 이름을 전달한다. 출력에는 API 키나 모델의 내부 경로를 추가하지 않는다.
- 마스크·RGB·prepare_product·템플릿·CSS·frontend·ML은 운영 변경하지 않았다. MATTE_VERSION과 기존 processing_version 유지. u2net은 이미 `u2net-8d10d2f3bb75-matte-cleanup-v1-preserve-solid`로 구분된다. 기존 자산을 자동 재처리하지 않는다. 실제 선택 asset/hash 변경 시 기존 snapshot/stale 처리를 사용한다.

검토용 `artifacts/photo-production-quality/review-full-u2net.json`은 기존 root/runtime/model/원장 구성을 복사해 **별도로** 준비했다. 카피는 Mock/paid=false이며 활성 설정이 아니다. `service_presentation.ps1 -ConfigFile ... -CheckOnly`에서 u2net/cleanup/verified=True 확인. 서버는 시작하지 않았다.

```json
{"photo_model_name":"u2net","photo_model":"<절대 프로젝트 경로>/artifacts/models/rembg/u2net.onnx","photo_matte_mode":"cleanup"}
```

실행 전 CheckOnly, 별도 승인 후에만 서버 재시작. 새 환경에서 모델이 없거나 손상/이름 불일치면 모델 필수 readiness는 실패한다. 자동 다운로드나 모델 대체는 없다. 일반 개발의 모델 선택적 설정에서는 기존 원본 사용 경로를 유지한다.

## 측정·실제 서비스 검증

기존 동일 CPU/각 사진3회 벤치마크 재사용: u2netp 추론 중앙값0.483~0.595초/peak0.666GiB, Full1.215~1.315초/peak0.987GiB(로딩0.508초), Lite12.450~13.836초/peak11.759GiB. 격리 Python worker 전체 working set이며 GPU/동시 부하 수치가 아니다. 이번에 같은 대규모 벤치마크를 반복하지 않았다. 과거 서비스 subprocess 총 시간은 Full4.20~4.40초로 추론 시간과 구분한다.

- 최신 실제 광고50장(A/B/C/D48+기존 Lite2), 격리 shadow8장·gradient4장 = **62장**. 실패한 초기 shadow wrapper 직렬화4건은 원래 로그에 남기고 해당 가설만 고쳐8장 성공시켰다. 미해결 렌더링 실패0. 생성 이미지/PDF는 Git 제외.
- 모든 마스크 조건의 동일 격자 RGB 보존·동일 카피·사진 SHA·원장 SHA·RGB1080×1350 확인. haze/진단 개수로 우열을 정하지 않았다.
- 두 상품의 격리 TestClient 실제 worker u2net 처리·CLIP·v2 Chromium·v3 가격/비주얼16시안·실제 bt-logistic-v1 4그룹·가격/제목 수정·stale 다운로드409·original 전환 확인. 카피는 저장된 실제 응답을 **Mock 표시로 재생**, 신규 실제 provider 호출0. 왕복/캐시·이전 자산 호환은 관련 회귀와 기존 실제 검증을 재사용했다.
- 두 편집 PNG와 1페이지 PDF 내장 RGB 픽셀 일치. 실제 missing-model worker의 실패 코드/원본 조회·ready false 확인.
- 관련 pytest49 passed(기존 AnyIO warning1). 새 검사는 파일 교체·같은 길이 손상·잘못된 이름·누락·CLI·환경 복원 목록·offline probe 이름 전달 포함. 실제 Chromium 일반/블라인드 갤러리 각각62장 decode·console/pageerror0. 전체 회귀 CI는 PR Checks 참조.

## 결과물·후속

`artifacts/photo-production-quality/gallery.html`, `blind-gallery.html`, `render-results.json`, `geometry.json`, `verification.json`, `api/report.json`, `overlay-results.json`에 보존했다. 원본 해상도 PNG는 `ads/{상품}/{조건}/{템플릿}.png`다. 모델·시간·메모리 기존 원시 자료는 `artifacts/photo-quality-intensive/` 참조.

추가 원본 조사는 uploads/originals의12개 고유 이미지를 확인했지만 기존 광고/단색 fixture여서 실상품으로 사용하지 않았다. 비교 시트 썸네일도 원본 검증에 쓰지 않았다. 투명 유리컵/얼음, 치킨, 케이크, 복잡한 소품의 볶음면, 비식품의 출처가 확인된 고해상도 원본이 추가로 필요하다.

B 요청: visual_c/emotional_b의 gradient가 사진 몸체를 덮는 범위와 감쇠를 검토하고, 큰 상품의 double-shadow를 광원·배경 밝기별로 확인한다. brand_a/price_c의 시선 집중과 여백은 사진 bbox만 고쳐 해결할 문제가 아니다. 코드·메시지는 자동 전송하지 않았다.

다음 AI 배경 작업은 마스크 잔여물 제거와 고해상도 입력을 먼저 확보하고 상품 접지면·조명 방향·텍스트 안전 영역을 B와 합의해야 한다. 생성 배경만으로 원본 사진의 광원·해상도·alpha 손실을 고칠 수 없다. 기존 배경 PoC를 재사용하며 새 이미지 API 호출은 하지 않았다.

유료 API/사진 외부 전송/새 모델 다운로드0. 원장65건/$0.53191900(미확정 예약 포함 상한) SHA 보존. 사용자 파일·모델·환경·transfer·기존 결과물·운영 서버/터널 보존. 사람 평가는 미완료이며 main 병합·배포는 하지 않는다.
