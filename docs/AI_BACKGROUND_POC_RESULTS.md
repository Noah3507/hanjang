# AI 배경 하이브리드 실제 광고 비교

2026-11-27 · 실험 기준 main `aca9626` (PR #83) · PR 준비 시 `85a09eb` (PR #84, B 비교 도구만 추가) 반영 · **운영 채택 보류**.

## 실제 결과와 판단

text-only 배경 4장을 생성하고, 저장된 실제 카피·사진·스타일을 재사용해 Chromium 광고 **32장**을 비교했다. 각 상품의 밝은/어두운 배경에 visual_a/emotional_a 또는 visual_d/emotional_d를 적용했다. 같은 템플릿의 네 조건은 카피와 스타일이 같다.

|조건|배경|상품 사진|
|---|---|---|
|A|기존 단색|기존 u2netp|
|B|기존 단색|PR #83 full u2net|
|C|생성 배경|B와 동일한 full u2net 자산|
|D|생성 배경|기존 original RGB 경로|

다음은 Codex의 원본 PNG 시각 검토이며, 매장 운영자·디자이너의 평가나 객관적 품질 점수가 아니다.

|배경|유망한 부분|실패·제약|
|---|---|---|
|짜장면 / 밝은 에디토리얼|중립적인 질감이 단색의 평면감을 줄인다.|잔여 천·나무 받침의 불완전한 경계가 그대로 남는다. 질감만으로 전문 광고 수준의 차이는 작다.|
|짜장면 / 어두운 목재|visual_d의 큰 접시에 식탁 맥락을 더한다.|목재 무늬가 문구 뒤까지 이어진다. emotional_d의 작은 상품과 과도한 여백은 개선되지 않는다.|
|에스프레소 / 자연광 석재|emotional_a가 가장 유망하다. 따뜻한 컵 색상과 밝은 표면이 어울린다.|원본 사진의 조명·기존 합성 그림자와 배경 광원이 완전히 맞지는 않는다. 실제 사진보다 더 정교한 접지감을 보장하지 못한다.|
|에스프레소 / 어두운 스튜디오|중앙 조명으로 단색보다 깊이감이 생긴다.|접시 아래 직선에 가까운 그림자 경계가 여전히 보인다. emotional_d의 작은 상품·큰 여백도 그대로다.|
|D / original 공통|원본 상품 구성·소품을 보존한다.|사진 속 테이블과 생성 배경이 별개 카드로 중첩된다. 특히 밝은 원본과 어두운 배경이 충돌하고 상품도 더 작아 보인다.|

이번 표본에서 C가 모든 B보다 명확히 우수하지 않았다. **4회에서 탐색을 종료**하고 자동/운영 배경 생성을 연결하지 않는다. 우선순위는 B와의 상품 배치·텍스트 안전 영역·그림자 계약 합의다. 배경을 바꾸면 마스크 잔여물이나 사진 해상도, 기존 카피의 약점이 해결된다는 주장은 하지 않는다. 생성 배경 4장에는 시각 검토상 중복 상품·문자·로고가 보이지 않았지만, 이를 보장하는 자동 탐지기는 구현하지 않았다.

## 로컬 결과물

모든 이미지와 사용자 카피는 Git 제외 `artifacts/ai-background-poc/`에만 보존한다.

- `gallery.html`: A/B/C/D를 동일 템플릿끼리 비교. 이미지를 클릭/새 탭으로 열어 1080×1350 원본을 확인한다.
- `blind-gallery.html`, `blind-key-local.json`: 조건 이름을 숨긴 32장과 로컬 대응표. 사람 평가는 미실시.
- `ads/{상품}/{배경}/{A|B|C|D}/{template_id}.png`: 실제 Chromium 결과.
- `{배경}/request.json`, `response.json`, `background.png`, `result.json`: 실제 요청·응답·배경·시간. 비밀키/인증 헤더/사용자 사진 전송 없음.
- `render-results.json`: 사진/배경/PNG SHA, 실제 표시 카피, 글꼴·줄 수·진단, 렌더링 시간.
- `verification.json`, `browser-check.json`: 무료 무결성·동일 조건 검사와 갤러리 브라우저 검사.
- `render_compare.py`: 격리된 비교 실행 기록. 기존 결과를 덮어쓰지 않도록 파일 존재 시 중단한다.

배경만 1024×1536에서 1080×1350으로 중앙 fit했으며 상품의 RGB를 생성형 AI로 변경하지 않았다. 원본 모드는 기존 방향/RGB/비율 보존 경로를 사용했다. 실험 HTML에만 배경을 주입해 기존 worker로 캡처했다. **이 미리보기는 운영 snapshot이 아니며 저장된 서비스 후보로 재사용하면 안 된다.**

## 구현 범위와 안전장치

- `background_provider.py`: 고정된 서버 소유 테마만 허용하는 text-only Images provider. 사진·가게명·가격·주소·연락처 입력 인터페이스가 없다.
- `service_background_poc.py`: 명시적 `--approved-paid-call`만 허용하는 실험 실행기. 일반 광고 생성/API/UI에는 연결하지 않았다.
- 별도 이미지 원장: 호출 전에 $0.25 예약, 16시도/$5 이중 제한, 동일 요청 키 중복 거부, SDK 재시도 0. 실패·불명확 비용은 예약액을 남기고, 알려진 usage는 실제 비용으로 정산한다. 예약 초과 시 후속 시도를 차단한다. 단일 로컬 프로세스/원장 lock 기반이며 다중 서버 과금 시스템은 아니다.
- 일반 LLM 한도/원장, 운영 기본값, 인증, 기존 모델/사용자 자료, B 소유 파일을 변경하지 않았다. 신규 LLM 호출 0회, 이미지 edit/사진 외부 전송 0회.
- 배경 자산 Job/API/TTL/캐시·편집 연동·ranking/diagnostics 무효화 기능은 **미구현**이다. 품질 채택 조건이 충족되지 않아 범위를 확대하지 않았다. 기존 서비스의 이 기능들은 그대로 유지된다.

새 유료 호출은 다음 명령으로 발생하므로 단순 재현 검증에 실행하지 않는다. 이번 작업은 이미 완료됐으며 추가 호출할 필요가 없다.

```powershell
# 실제 비용 발생: 승인된 실험에만 사용. 사용한 id는 재사용 불가.
.\.venv\Scripts\python.exe scripts/service_background_poc.py --theme coffee-natural --id UNIQUE-ID --approved-paid-call
```

이 실행기는 이번 승인 당시의 LLM 원장 SHA를 고정 검증한다. 향후 원장이 변하면 호출 전에 중단하는 것이 의도된 동작이다. 승인·공식 가격·모델 접근성 재검토 없이 실행기를 수정해 우회하지 않는다.

## 비용과 측정

공식 모델 `gpt-image-2.6-flare` 접근성을 무료 조회 후 확인했다. [공식 가격](https://developers.openai.com/api/docs/models/gpt-image-2.6-flare.md)은 text input $5/M, image input $8/M, image output $30/M이다. 요청은 medium/1024×1536/complexity low/PNG/n=1이다. 공식 계산기의 같은 크기 최대 품질 출력 5488토큰과 입력 3000토큰을 합산한 $0.17964보다 높은 **$0.25/회**를 예약했다. 16회 총 예약 $4로 승인 $5 이내다. 모델/가격은 이후 달라질 수 있다.

|생성 배경|실제 비용 USD|시간 초|
|---|---:|---:|
|noodle-editorial-1|0.035240|8.86|
|noodle-dark-1|0.035245|7.19|
|coffee-natural-1|0.035270|8.30|
|coffee-dark-1|0.035260|9.15|
|합계|**0.141015**|중앙값 8.58|

실제 4회 성공/실패 0/재시도 0. text input 1035, image input 0, image output 4528토큰. 기존 LLM 원장 **42건/$0.19978650 및 SHA 그대로**. 이미지 비용을 기존 LLM 원장에 합치지 않았다. 비용은 API usage와 확인한 단가로 계산했으며 청구서 대조는 미실시다.

광고 32장 모두 RGB1080×1350·해시 검증, 텍스트 152항목, 글꼴 30~44px, 자동 축소/넘침/텍스트 충돌 각각 0. B/C는 사진 SHA 및 텍스트/크기/줄 수/좌표가 같다. C/D 16장의 대비는 unavailable, A/B 16장은 normal이다. subject_size는 A/B/C 각 1건 caution, D 8건 unavailable로 유지했다. 렌더링 중앙값 5.68초/장(개별 worker 실행, 배치 최적화 수치 아님). 자동 검사는 접지감·미적 완성도를 판정하지 않는다.

무료 회귀 검사: backend 전체 875 passed/45 skipped(모델·Chromium opt-in), 신규 provider 9 passed, frontend 111 passed·타입/빌드 성공. 별도 실제 Chromium 편집·두 번째 편집·PNG/A4 PDF lossless 픽셀/원본 보존 테스트 1 passed. 비교 갤러리 두 페이지 각각 32장 디코딩 성공·브라우저 오류 0. 전체 backend의 skip을 실행 성공으로 계산하지 않는다. Starlette/AnyIO의 기존 deprecation 경고 1건은 남아 있다.

## B에게 전달할 다음 계약

실제 근거: `coffee-natural-1/C/emotional_a.png`는 유망, `coffee-dark-1/C/visual_d.png`는 접시 밑 경계, `noodle-dark-1/C/emotional_d.png`는 작은 상품/여백, 동일 D는 카드 중첩 사례다. 모두 위 `ads/` 아래에 있다.

1. 배경 opt-in 템플릿별로 상품 bbox·텍스트 quiet zone·허용 명도·그림자 소유권을 합의한다. 감성형 원형과 큰 visual형에 동일 배경 계약을 가정하지 않는다. 무늬 위 텍스트에는 B가 별도 안전 패널을 검토한다.
2. 별도 `background_asset_id/sha256/model/prompt_version/review_state` 내부 자산을 제안한다. 공개 API는 아직 추가하지 않았다. photo_mode는 cutout/original 그대로다.
3. 명시적 생성/선택만 허용하고 원본·마지막 성공 광고를 보존한다. 캐시에는 모델/프롬프트/팔레트/목적/예약 영역/소유권을 포함하고 가격·카피는 제외한다. 텍스트 편집은 같은 배경을 재사용한다.
4. 운영 연동 시 최종 snapshot에 배경 SHA와 합성 버전을 반드시 추가한다. 배경 교체 시 PNG revision과 ranking/diagnostics를 무효화하고 지연 완료 결과를 게시하지 않는다. 소유권/TTL·실패 후 기존 배경 선택·PNG/PDF도 함께 검증해야 한다.

추가 구현·운영 적용은 실제 사용자/B의 이 비교 자료 검토 후 결정한다. 배포·서버 재시작·main 병합은 하지 않는다.
