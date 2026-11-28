# 최종 카피 생성 방식 검토 — 2026-11-28

## 운영 결정

**운영 기본값은 v6 / `gpt-5.4-mini-2026-03-17`을 유지한다.** 새 `campaign` 경로는 명시적 opt-in으로만 제공한다. PR #85 이후 최신 main `193428b`(B의 PR #87 limits / #88 Fill·Quality2 포함)을 반영했다. 운영 서버·환경 파일·활성 설정을 변경하거나 재시작하지 않았다.

후보 번호 선별은 재작성보다 검증된 문장을 보존하기 쉽지만, 실제 최종 응답에도 “손이 가볍게 닿는 순간”, “진하게 쉬어가세요”가 남았다. 짜장면 가격형 “오늘 점심, 고민 길어질 땐”은 이전 가격 안내체보다 짧지만 상품 고유성이 약하다. 기존 intensive의 좋은 감성형보다 항상 낫지도 않다. 기술적 성공만으로 운영 승격을 강행하지 않는다. 사람 평가·전환 성과 검증은 수행하지 않았다.

기준 자료: [v8.1](COPY_QUALITY_V8_1.md), [기존 실제 집중 실험](AD_QUALITY_INTENSIVE.md). v6은 이미 알려진 어색함과 중복 문제가 남은 안정성 기준선이며 품질 문제가 해결됐다는 뜻은 아니다.

## 제공하는 선택적 경로

- `campaign` / `gpt-5.4-2026-03-05` / Responses API / low reasoning / `copy-campaign-pool-choose-slots-5-limits1`.
- 첫 호출에서 네 전략 세트 2개를 생성하고 기존 사실·가격·placeholder validator를 통과한 세트만 남긴다. 0개면 안전한 오류, 1개면 선택 호출 생략, 2개면 두 번째 호출에서 전략별 **후보 번호만** 선택한다. 잘못된 번호·실패는 오류이며 세 번째 호출이나 자동 재시도는 없다.
- 후보 번호 선택 뒤 원문 후보를 조립한다. 선택 단계에서 새 문장을 만들지 않는다. 목적과 충돌하는 CTA는 이미 통과한 다른 후보가 있으면 그 후보를 우선한다. 의미 검사는 제한적이며 주문형의 모든 CTA가 충분히 설득력 있다는 보장은 없다.
- 상호·상품·가격 독립 슬롯은 v2 4종과 v3 16종, cutout/original 모두의 `data-field` 교집합으로 확인한다. 보장된 슬롯의 사실만 있는 본문/CTA 또는 분리된 가격 placeholder 토큰만 생략한다. 임의 요약·사실 원문 수정·가격 trim은 하지 않는다. CSS 가시성은 실제 렌더링 검증도 필요하다.
- 한글 상품명 placeholder **밖의 조사**만 받침 규칙으로 보정한다. 영문·숫자 발음은 추측하지 않고 가격·리터럴 사실·원문 공백은 고치지 않는다. 기존 validator는 보정 후에도 실행한다.
- 처리 경고는 최종 선택된 후보에 한해 반환한다. 주관적 품질은 advisory이며 재호출 근거가 아니다.

## B의 limits / 캐시 계약

`templates/v3/limits.json`이 병합돼 실제 스키마 `hanjang-template-limits-1`, 템플릿 버전·집합·HTML/CSS source SHA·전략별 최소값을 확인해 읽는다. 파일 누락·불일치 시 임의 수치를 만들지 않고 제외한다. 치환 후 공백 포함 길이를 사용한다.

|전략|제목 soft/hard|본문 soft/hard|CTA soft/hard|
|---|---|---|---|
|emotional|28/30|72/80|17/19|
|price|26/26|28/64|17/17|
|visual|30/32|44/88|18/20|
|brand|36/36|40/88|19/22|

이는 B의 측정 기반 축소·가독성 지침이다. 기존 JSON 60/160/30 계약을 바꾸거나 긴 상품명을 자르지 않는다. campaign payload에는 숫자 지침을 전달하고 최종 표시 문구의 초과는 경고한다. 다른 프로필 payload는 유지한다. 모든 전략은 기존처럼 카피 하나를 네 템플릿이 공유한다.

provider/model/recipe/payload/facts/photo 캐시는 분리한다. v6 결과·편집·TTL·소유권·revision 계약은 유지한다. 템플릿 VERSION이 같아도 HTML/CSS가 바뀌면 v3 source fingerprint로 이전 시안·순위·다운로드를 stale 처리한다. 이 때문에 카피나 분석을 자동 유료 재생성하지 않는다. v2 snapshot은 변경하지 않는다.

## 실제 검증과 결과물

Git 제외 `artifacts/copy-production-final/`에 원본·실패 기록까지 보존한다. 사용자 사진과 생성 PNG/PDF는 커밋하지 않는다.

- `all-actual-copy.md`: 중단 전 실제 후보·실패·조립 결과. `factory-final-20261128/`에는 재개 후 최종 factory 요청 2개·응답 2개·원문 조립·치환 결과·usage가 별도로 있다. Mock/수작업을 실제 생성으로 표시하지 않는다.
- `comparison-20261128/gallery.html`: 최신 B 템플릿의 실제 저장 카피 5조건×16종 및 이전 우수 사례 8장, 총 **88장**. 원본 정밀도 측정·PNG hash·실제 B 랭킹 **20그룹**은 같은 폴더 `report.json`에 있다. Chromium에서 88장 로드·1080×1350 확인, console/pageerror 0.
- 450개 측정 필드 중 축소 2개, 최저 28px. 글꼴 크기 normal 88장이나 layout caution 5장, subject_size caution 7장, image_crop caution 10장, 대비 unavailable 27장이 남았다. 경고를 숨기지 않았다. 이 수치는 중복 포함 비교 이미지 집합의 결과이며 독립적인 품질 표본 수가 아니다.
- `integration-v3/`: 완료된 짜장면 3목적 API·실제 모델 검증 산출물. 뒤 에스프레소 MIME 실패로 전체 report가 저장되지 않았으므로 존재하지 않는 raw 결과를 만들어내지 않았다.
- `integration-espresso/`: PNG인 에스프레소를 JPEG로 보내던 실행기 MIME 수정 후 실제 rembg/CLIP/Chromium/ML·부분 수정·다운로드 완료.
- `integration-20261128/`: 최종 factory 실제 응답을 **Mock이라고 표시하여 재생**한 API 통합. 최신16종·실제 full u2net·CLIP·bt-logistic-v1·가격/제목 편집·stale·original/cutout 재전환·PNG/PDF·원본/원장 hash 보존 확인. 여기서 추가 유료 호출은 0이다. 실제 생성 검증은 아래 factory 2회와 구분한다.
- 두 에스프레소 편집 PNG는 RGB 1080×1350이며 1페이지 PDF에 동일 RGB 픽셀이 내장된 것을 확인했다. PDF 전체 페이지의 별도 뷰어 시각 평가는 이번 재개 검증 범위가 아니다.

CLIP 검증 실행기의 절대 한글 경로는 Torch JIT에서 errno42를 일으켰다. 기존 모델의 ASCII 상대경로로 동일 파일을 재사용해 성공했다. 모델·가상환경·기존 .env는 바꾸지 않았다.

## 비용·지연·원장 복구

[공식 GPT-5.4 모델 정보](https://developers.openai.com/api/docs/models/gpt-5.4.md)의 입력/캐시/출력 $2.50/$0.25/$15 per 1M과 snapshot 접근을 확인했다. 추가 사진 외부 전송·이미지 API 호출·자동 API 재시도는 모두 0이다.

- 이번 작업 총 실제 SDK **22회**, 새 원장 **23건**(전송 전 실패 예약 1건 포함). 확정 usage 비용 **$0.27141250**, 미확정 보수적 예약 **$0.06072** 보존. 새 입력/출력 토큰 37,411/11,859.
- 기존 **42건/$0.19978650**의 필드는 그대로다. 현재 **65건/$0.53191900**은 기존 미확정 사용량과 이번 예약을 포함한 누적 상한이며 전액 확정 청구액이 아니다. `cost-receipt-20261128.json`에 검증 hash와 PDF 증거가 있다.
- 재개 후 실제 정상 factory 검증은 실험 scope 우회 없이 **2회**, 입력4,163/출력764토큰, **$0.02186750 / 16.27초**였다. 나머지는 중단 전 확보해 재사용했다.
- 이전 대표 결과: 방문22.84초/$0.022240, 주문12.02초/$0.0170775, 에스프레소7.58초/$0.0228675. 과거 mini 단일3.87초/$0.00171075보다 비용·지연이 크다. 조건과 표본이 달라 일반화하지 않는다.

원장 저장 실패는 Windows 공유/access rename 경쟁 가능성에 한해 동일 `.tmp`→원장 교체만 최대5회×50ms 재시도하도록 보완했다. 예약/트랜잭션/API를 반복하지 않는다. 지속 실패는 안전하게 중단하고 보수적 예약·원래 오류를 보존한다. 정확한 당시 OS 원인은 재현하지 못했다. 로컬50회 저장 probe와 이번 실제2회 정산은 성공했지만 모든 Windows 오류 해결을 보장하지 않는다.

## 운영 설정과 실행 준비

일반 기본은 Mock/paid=false, v6/mini, 누적6회/$0.10을 유지한다. legacy 정책 상한10회/$0.10도 유지한다. 이미 원장65건으로 기본 한도가 소진돼 **그대로는 추가 생성이 차단**된다.

관리자만 설정하는 `copy_usage_policy: service`에서 누적 최대128회/$2까지 명시적으로 설정할 수 있다. 프로필과 사용량 정책은 독립적이며 experiment169회/$5 권한을 일반 factory에 주입하지 않는다. 공개 요청으로 한도를 바꿀 수 없다. 아래는 재시작 승인 때 검토할 예시이며 이번에 활성화하지 않았다.

```json
{"copy_prompt_profile":"v6","copy_model":"gpt-5.4-mini-2026-03-17","copy_usage_policy":"service","copy_max_requests":128,"copy_budget_usd":2.0}
```

별도 `artifacts/copy-production-final/presentation-v6-review-20261128.json`을 준비하고 기존 auth/model/runtime/원장 경로를 재사용했다. `service_presentation.ps1 -ConfigFile ... -CheckOnly`에서 v6/mini/128/$2/retries0 확인. 기존 활성 파일·서버는 그대로다. 이전 `presentation-campaign.json`은 중간 산출물로 최신 정책 필드가 없으며 적용용이 아니다.

실제 생성 허용은 provider=openai/paid=true/API키/예산 검증을 모두 요구한다. campaign opt-in은 프로필과 모델을 함께 바꿔야 한다. 실패 시 Mock으로 조용히 대체하지 않고 입력·마지막 성공 자산을 유지한다. 단일 호출 승인용 `service_openai_smoke.py`는 명시적 v6/mini/retries0로 고정해 두 호출 recipe를 잘못 실행하지 않는다.

## 무료 회귀 검증 / 남은 일

- Backend **928 passed / 54 skipped / warning1**. skipped는 opt-in 모델·Chromium 항목으로 통과로 세지 않았다. 필요한 실제 모델·Chromium은 위 별도 실행으로 확인했다.
- Frontend **111 passed**, TypeScript·프로덕션 build 성공. frontend 제품/테스트·CSS·템플릿·ML 파일 수정 없음.
- 원래 Playwright `editor.spec.ts`의 `actual edit twice` 테스트 **1 passed / 25.0초**, 원래120초 제한 유지. PR #85 다운로드 저장 지연은 재현되지 않았고 원인 해결을 단정하지 않는다.
- 로컬 갤러리는 브라우저 파일로 열어 전략별 이전/신규 문구와 PNG를 비교할 수 있다. 사용자 검토는 미완료다. 운영 서버·배포·main 병합은 하지 않는다. GitHub CI는 PR checks에서 별도로 확인한다.

B와 후속 확인: limits의 본문·CTA 생략 시 고정 여백, 일부 작은 상품 배치, layout/크롭 경고, 독립 슬롯의 실제 가시성. A 후속 품질 과제는 어색한 동사와 목적별 CTA이며 새 프롬프트·추가 유료 실험을 이 PR에서 더 반복하지 않는다. 운영 승격은 사람의 실제 카피/PNG 검토 후 결정한다.
