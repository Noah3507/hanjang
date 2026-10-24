# API와 Ranking 계약 초안

계약 version: v1.1-contract (문서·fixture 승인 기준; 현재 서비스 HTTP 구현 범위는 유지). R5의 접점은 candidate ID·image path/url·score/rank/model version입니다. 자료 충돌 시 최종 발표본을 우선합니다. 사용자 승인에 따라 입력·업로드 API 및 아래 draft 계약을 구현했습니다. 나머지 광고 API는 설계 단계입니다. P/R 표기는 [결정 목록](REQUIREMENTS_REVIEW.md)을 따릅니다.

## 공통 규약

현재 구현: health, POST /sessions, POST /uploads, PUT·GET /jobs/{job_id}/input, GET /assets/{asset_id}. GET /health는 기존 별칭을 유지합니다. POST /jobs, GET /jobs/{job_id}, 결과·ranking·편집 API는 미구현입니다. health는 광고 기능의 준비 상태를 보장하지 않습니다.

- Base /api/v1, JSON UTF-8. 이미지 upload만 multipart.
- Strategy = emotional | price | visual | brand. Mood = warm | minimal | vivid | premium은 제안.
- ID는 opaque string. client filesystem path 금지, asset URL은 동일 origin의 인증 endpoint.
- facts는 수락 문자열 그대로. 가격 float·자동 단위·trim·번역 금지.
- datetime은 UTC ISO 8601, score는 finite float이며 0–1 제한 없음, rank는 유일한 1–4.
- unknown field 거부. optional 입력은 생략 가능, 응답에서는 null. breaking change는 version 갱신과 공동 승인.

## 승인된 입력 draft 계약

POST /jobs는 광고 처리 시작이므로 이번 입력 저장 기능에서 구현하거나 재사용하지 않았습니다. 사용자가 PUT /jobs/{job_id}/input 추가와 기존 제안 검증값 적용을 승인했습니다. 기존 GET /jobs/{job_id}의 JobStatus에는 facts/mood가 없어서 조회는 **GET /jobs/{job_id}/input**으로 별도 추가했습니다. 이는 기존 작업 상태 응답이나 B ranking 계약을 변경하지 않는 additive 계약입니다.

PUT 요청은 InputDraft = {facts: Facts, mood: Mood}. GET/PUT 응답은 DraftResponse = {job_id:string, status:"pending", facts:Facts, mood:Mood, expires_at:UTC datetime}. 저장은 광고 처리를 시작하지 않고 TTL을 연장하지 않습니다. 미저장 draft 조회는 409 INPUT_NOT_SAVED입니다. 입력 갱신은 전체 대체·last-write-wins이며 revision/자동 광고 재생성은 이번 범위에 없습니다.

```json
{"facts":{"store_name":"  테스트 가게  ","product_name":"한글 메뉴","price_text":" 10,500 원 ","address":null,"instagram_handle":null},"mood":"warm"}
```

공백·쉼표·통화 단위·한글·emoji는 입력 그대로 보존합니다. 공백만인 값·제어 문자·숫자형 가격·길이 초과·unknown field는 422이며 자동 교정/trim/절단하지 않습니다. 선택 문자열은 생략/null 가능, 빈 문자열은 화면에서 null로 전송합니다. mood는 warm/minimal/vivid/premium입니다.

사진은 JPEG/PNG 실제 형식·decode·10 MiB·24MP·가로/세로 각각 256px 이상을 확인합니다. Multipart에는 photo 1개만 허용하며 사용자 파일명·경로는 저장에 사용하지 않습니다. 파싱 전 전체 요청은 10 MiB+64KiB, draft JSON은 16KiB로 제한합니다. 원본 byte·해시를 보존하며 Pillow는 검증만 담당합니다.

세션 token은 POST /sessions에서 발급하며 X-Hanjang-Session header로만 전송합니다. UI는 tab sessionStorage에 token과 업로드 ID/metadata만 보관하고 사실 정보는 서버 GET으로 읽습니다. 다른 세션의 asset/draft는 404, 누락/만료 세션은 401입니다. 원본 GET은 인증된 bytes 응답이며 공개 정적 디렉터리가 없습니다. 실제 token·사진·개인 입력을 로그에 출력하지 않습니다.

원본·draft는 업로드 created_at부터 24시간입니다. 시작 시와 60초 간격 sweep에서 만료 원본·metadata를 삭제하고 만료 접근은 즉시 거부합니다. 삭제 전 자기 만료 작업은 410, 삭제/재시작 후 미존재는 404일 수 있습니다. 세션 자체도 발급 후 24시간으로 만료합니다. 서버 중단 중 삭제는 실행할 수 없고 재시작 시 파일 mtime으로 24시간 지난 orphan을 정리합니다. 메타데이터는 메모리이므로 재시작/배포 후 유실될 수 있으며 새 업로드가 필요합니다. 이번에는 중간/광고 결과 파일을 생성하지 않습니다.

## 타입 정의

| 타입 | field와 제약 |
| --- | --- |
| Facts | store_name:string(1..80), product_name:string(1..80), price_text:string(1..40), address:string 또는 null(<=200), instagram_handle:string 또는 null(<=80). 공백만·제어 문자 거부, 자동 수정 금지 |
| Copy | headline:string(1..60), body:string(0..160), cta:string(0..30). 길이는 제안, plain text, 사실 추가 금지 |
| Upload | job_id/asset_id:string, width/height:양의 int, mime_type:image/jpeg 또는 image/png, sha256:64 hex string, created_at/expires_at:datetime. 원본은 pending job에 귀속 |
| Asset | asset_id/url/mime_type:string, width/height:int 또는 null, revision:int>=1. PNG는 크기 필수, PDF는 null 가능 |
| Warning | code/message:string. 안전한 설명만 |
| RankingItem | candidate_id:string, score:finite float, rank:int 1..4 |
| Ranking | source:mock 또는 model 또는 fallback_mock, model_version:string, feature_version:string 또는 null, revision:int, items:RankingItem[4] |
| TextBox | field/text:string, x/y/width/height:number, font_size_px:number, font_weight:int, foreground:#RRGGBB, background:#RRGGBB 또는 null, overflow:bool |
| RendererMetadata | template_version:string, canvas_width/height:int, text_boxes:TextBox[], product_bbox:{x,y,width,height}, photo_sha256/processed_photo_sha256:string |
| Diagnostics | status:available 또는 partial 또는 unavailable, rules_version:string, min_font_size_px/min_contrast_ratio/text_overlap_ratio/product_overlap_ratio:number 또는 null, layout_order:string[] 또는 null, attention:Attention 또는 null, warnings:Warning[] |
| Attention | 선택 기능만: source:umsi, model_version:string, heatmap_asset:Asset, product_saliency_share:number 또는 null. 모델 추정이며 실제 시선 측정 아님 |
| Candidate | candidate_id:string, strategy:Strategy, revision:int, facts:Facts, copy:Copy, png:Asset, renderer:RendererMetadata, diagnostics:Diagnostics |

길이·upload 제한과 구체적인 진단 임계값은 원본 확정값이 아닙니다. 응답의 generated copy와 facts를 분리해 입력값 변경을 막습니다.

## HTTP 요청·응답

X-Hanjang-Session을 health/session 생성 외 endpoint에 요구하는 제안입니다. token은 profile localStorage·URL·log에 저장하지 않고 session scope로 유지합니다. 다운로드도 인증 fetch→Blob 방식입니다.

| Method/path | request | 성공 response |
| --- | --- | --- |
| GET /health | 없음 | 200 {status:"ok",api_version:"v1-draft"} |
| POST /sessions | 빈 JSON | 201 {session_token,expires_at}, Cache-Control:no-store |
| POST /uploads | multipart photo | 201 Upload와 고유 pending job 생성. 승인된 JPG/PNG·10MiB·24MP·가로/세로 최소256px 검증 |
| PUT /jobs/{job_id}/input | {facts,mood} | 200 DraftResponse, 입력만 저장·pending 유지 |
| GET /jobs/{job_id}/input | 없음 | 200 DraftResponse, 미저장 409 |
| POST /jobs | {job_id,photo_asset_id,facts,mood} | 202 JobStatus. 자기 pending upload job을 처리 시작, strategy 선택 없음, 반드시 네 종류 |
| GET /jobs/{job_id} | 없음 | 200 JobStatus |
| GET /jobs/{job_id}/result | 없음 | 200 GenerationResult, 미완성/실패 409 |
| PATCH /jobs/{job_id}/candidates/{candidate_id} | {expected_revision,copy} | 202 JobStatus, copy 전체 교체, facts/strategy 변경 금지 |
| PATCH /jobs/{job_id}/photo-source | {expected_revision,photo_source:original 또는 processed} | 202 JobStatus, 같은 보존 원본/처리본 선택 후 네 후보 재렌더링·재정렬. 상세 endpoint는 제안 |
| GET /assets/{asset_id} | 없음 | 200 binary 원본 JPG/PNG 또는 결과 PNG. PDF는 PNG MVP 이후 OPTIONAL, 안전한 filename·no-store, session 소유권 필수 |

expected_revision은 job 전체 revision입니다. 다른 후보 동시 편집도 409로 처리하는 안입니다. 실패 후 재시도·timeout 중복 요청의 idempotency 계약은 S2에서 확정하며 무제한 자동 재송신을 금지합니다. 취소 endpoint·취소 상태는 MVP에 포함하지 않습니다. 업로드부터 동일 job_id와 만료 시각을 사용하여 orphan과 처리 파일을 함께 정리합니다. 신규 재업로드는 새 job_id를 생성합니다.

생성 요청 예:

```json
{"job_id":"job_demo_01","photo_asset_id":"photo_01","facts":{"store_name":"쿠지라 식당","product_name":"아부라소바","price_text":"10,500원","address":null,"instagram_handle":null},"mood":"warm"}
```

JobStatus 전체 field 예:

```json
{
  "job_id":"job_demo_01","status":"processing","operation":"generate","stage":"rendering",
  "revision":1,"target_revision":1,
  "created_at":"2026-10-12T00:00:00Z","updated_at":"2026-10-12T00:00:01Z","expires_at":"2026-10-13T00:00:00Z",
  "warnings":[],"error":null
}
```

status는 `pending`, `processing`, `completed`, `failed`만 허용합니다. operation=generate/edit/photo_change는 제안, stage=null 또는 photo_processing/photo_analysis/copy_generation/rendering/ranking/diagnostics입니다. 최초 revision/target_revision은 publish 전에도 1입니다. edit/photo_change 중 revision은 현재 완료본, target_revision은 다음 번호입니다. error는 ErrorBody 또는 null. 수정 실패 시 기존 result를 유지하고 해당 JobStatus는 failed로 표시합니다. 원본 선택은 같은 사진을 사용하며 LLM을 다시 호출하지 않습니다.

job.created_at부터 24시간으로 expires_at을 고정하는 세부 정책을 제안합니다. 조회·수정으로 연장하지 않습니다. 만료 시 원본·중간 파일·결과물을 자동 정리하고 접근을 차단합니다. 원본도 인증 asset 조회로만 제공하며 파일 경로는 응답에 넣지 않습니다. 재시작·배포 시 job 및 파일 유실 가능, 복구 보장 없음, 미존재/만료이면 재업로드를 안내합니다. 비공개 저장·형식/크기 검증·서버 파일명·root 내부 경로 검증은 필수입니다.

GenerationResult 전체 구조:

```text
{api_version:string, job_id:string, revision:int, mood:Mood, facts:Facts,
 candidates:Candidate[4], ranking:Ranking, warnings:Warning[]}
```

candidates는 rank 순서, ID 집합은 ranking.items와 완전 일치, strategy 집합은 네 종류, facts는 모두 동일합니다. 모든 후보 snapshot·PNG reference·ranking은 최신 job revision에 맞춥니다. 수정 안 된 PNG는 내용 bytes를 재사용할 수 있지만 새 revision snapshot으로 참조합니다.

## 4개 광고 후보와 LLM 스키마

LLM은 facts 없이 {variants:[{strategy,copy},...]}만 반환합니다. schema 검증 후 서버가 동일 facts·사진을 각각 연결합니다. 아래는 한국어 artificial fixture이며 실제 생성 결과·품질 증거가 아닙니다.

```json
{
  "variants":[
    {"strategy":"emotional","copy":{"headline":"한 끼의 여유","body":"오늘의 식사를 즐겨보세요.","cta":"매장에서 만나보세요"}},
    {"strategy":"price","copy":{"headline":"오늘의 한 그릇","body":"가격을 확인해 보세요.","cta":"메뉴를 살펴보세요"}},
    {"strategy":"visual","copy":{"headline":"사진으로 만나보세요","body":"","cta":""}},
    {"strategy":"brand","copy":{"headline":"우리 가게의 한 그릇","body":"","cta":"방문해 보세요"}}
  ]
}
```

최종 Candidate 4개는 동일 schema를 사용합니다. candidate ID는 strategy 자체가 아니라 job 내부의 유일 ID입니다.

| candidate_id | strategy | template_version | png.asset_id | mock score | rank |
| --- | --- | --- | --- | --- | --- |
| c_visual | visual | visual-v1 | png_visual_r1 | 0.8 | 1 |
| c_emotional | emotional | emotional-v1 | png_emotional_r1 | 0.6 | 2 |
| c_price | price | price-v1 | png_price_r1 | 0.4 | 3 |
| c_brand | brand | brand-v1 | png_brand_r1 | 0.2 | 4 |

Candidate 전체 field 예입니다. geometry·측정값은 fixture용 인공 값이며 실제 측정 결과가 아닙니다. 실제 renderer는 모든 표시 text box를 기록해야 합니다.

```json
{
  "candidate_id":"c_visual","strategy":"visual","revision":1,
  "facts":{"store_name":"쿠지라 식당","product_name":"아부라소바","price_text":"10,500원","address":null,"instagram_handle":null},
  "copy":{"headline":"사진으로 만나보세요","body":"","cta":""},
  "png":{"asset_id":"png_visual_r1","url":"/api/v1/assets/png_visual_r1","mime_type":"image/png","width":1080,"height":1350,"revision":1},
  "renderer":{
    "template_version":"visual-v1","canvas_width":1080,"canvas_height":1350,
    "photo_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "processed_photo_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "text_boxes":[
      {"field":"product_name","text":"아부라소바","x":54,"y":1000,"width":972,"height":90,"font_size_px":64,"font_weight":700,"foreground":"#FFFFFF","background":"#181818","overflow":false},
      {"field":"price_text","text":"10,500원","x":54,"y":1100,"width":972,"height":60,"font_size_px":40,"font_weight":700,"foreground":"#FFFFFF","background":"#181818","overflow":false},
      {"field":"store_name","text":"쿠지라 식당","x":54,"y":1180,"width":972,"height":60,"font_size_px":36,"font_weight":400,"foreground":"#FFFFFF","background":"#181818","overflow":false},
      {"field":"headline","text":"사진으로 만나보세요","x":54,"y":70,"width":972,"height":60,"font_size_px":36,"font_weight":400,"foreground":"#FFFFFF","background":"#181818","overflow":false}
    ],
    "product_bbox":{"x":140,"y":160,"width":800,"height":800}
  },
  "diagnostics":{"status":"available","rules_version":"readability-v1","min_font_size_px":36,"min_contrast_ratio":17.76,"text_overlap_ratio":0,"product_overlap_ratio":0,"layout_order":["headline","product_name","price_text","store_name"],"attention":null,"warnings":[]}
}
```

모든 후보의 store_name/product_name/price_text box text가 원 입력 문자열과 동일해야 합니다. body/CTA가 비어 있으면 해당 box는 만들지 않습니다. 최종 JSON 예시 fixture 4개·Pydantic/OpenAPI·frontend 타입은 S1에서 공동 승인 후 생성하며 이번에는 코드 파일을 만들지 않습니다.

## B ranking adapter 계약

현재 추론·MockRanker 구현은 없으며 아래 함수 signature는 B 승인 전 초안입니다. 전처리·artifact 전달·오류·공동 합의 항목과 병렬 개발 게이트는 [MODEL_HANDOFF](MODEL_HANDOFF.md)에 정리합니다. 이번 점검은 HTTP/API schema를 변경하지 않습니다.

R4 공개 surface는 load_model(), extract_features(), score_ad(), rank_ads()입니다. 아래 signature는 B 승인 전 제안입니다. A는 rank_ads() 경계를 사용하고 B feature extraction을 복제하지 않습니다.

```python
# Interface specification only; not implementation.
load_model(artifact_dir: Path) -> ModelHandle
extract_features(image_path: Path, model: ModelHandle) -> FeatureVector
score_ad(image_path: Path, model: ModelHandle) -> float
rank_ads(items: list[RankInput], model: ModelHandle) -> RankOutput
# RankInput = {candidate_id: str, rendered_image_path: Path}
# RankOutput = {model_version: str, feature_version: str, items: list[RankingItem]}
```

서비스 metadata의 strategy는 B feature로 전달하지 않습니다. B 입력은 candidate ID와 **최종 PNG 경로**입니다. 서버 관리 하위의 절대 경로만 허용하며 B가 remote URL을 가져오지 않습니다. R5의 path/url 중 로컬 package+path를 채택하는 제안입니다. B는 서비스 없이 sample 이미지 폴더로 테스트할 수 있습니다.

```json
{
  "model_version":"bt-logistic-v1","feature_version":"clip-vit-l14-stats-v1",
  "items":[
    {"candidate_id":"c_visual","score":1.84,"rank":1},
    {"candidate_id":"c_emotional","score":1.10,"rank":2},
    {"candidate_id":"c_price","score":0.32,"rank":3},
    {"candidate_id":"c_brand","score":-0.40,"rank":4}
  ]
}
```

인공 응답 예입니다. scalar score는 상대 선호 값이며 구매 확률이 아닙니다. sigmoid(sA-sB)는 모델 내부 pairwise 비교이며 개별 매출·CTR 예측이 아닙니다. 다른 모델 version·다른 입력 set의 점수를 UI에서 직접 비교하지 않습니다.

계약 조건:

1. 네 후보를 같은 loaded model·feature version으로 평가하고 candidate ID로 결합합니다. 배열 위치로 결합하지 않습니다.
2. ID 누락·중복·추가, NaN/Infinity, version 불일치, rank 불일치는 A adapter가 거부합니다.
3. score 내림차순, 동점은 candidate_id 사전순으로 유일 rank 1–4를 부여하는 제안입니다. 동점 처리에 선호 차이가 있다고 설명하지 않습니다.
4. B는 model+scaler/config, feature 순서·전처리·의존성 spec, checksum, model card, sample smoke 절차를 제공합니다. A는 label/split/metric을 변경하지 않습니다.
5. B 예외 제안: ModelNotAvailable, ArtifactMismatch, InvalidImage, InferenceFailure. A는 안전한 code로 변환하고 stack/path를 client에 노출하지 않습니다.
6. 실패·timeout 시 **전체 mock**: source=fallback_mock, model_version=mock-v1, feature_version=null, warning=RANKER_FALLBACK. 정상 mock은 source=mock, 정상 B는 source=model.

MockRanker만 strategy별 고정값을 사용합니다. RealRanker는 strategy label을 feature로 사용하지 않습니다. 편집 후 네 후보 모두 재평가하고 새 이미지에 이전 score를 붙이지 않습니다.

## 오류 형식

```json
{"error":{"code":"INVALID_INPUT","message":"가격 입력을 확인해 주세요.","field_errors":[{"field":"facts.price_text","message":"가격이 필요합니다."}],"retryable":false,"request_id":"req_demo_01"}}
```

ErrorBody는 code/message/field_errors/retryable/request_id입니다. field_errors는 없으면 빈 배열. HTTP 오류는 {error:ErrorBody}, JobStatus.error는 ErrorBody 자체입니다. Pydantic 422도 공통 형식으로 변환합니다.

| HTTP | code 예 | 의미 |
| --- | --- | --- |
| 401 | SESSION_REQUIRED | token 없음/무효 |
| 404 | RESOURCE_NOT_FOUND | 미존재 또는 다른 session, 존재 여부 노출 금지 |
| 409 | REVISION_CONFLICT/JOB_NOT_READY/JOB_FAILED | 편집 충돌·미완성·실패 |
| 410 | RESOURCE_EXPIRED | 자기 session의 이미 알려진 만료 asset |
| 413/415/422 | FILE_TOO_LARGE/UNSUPPORTED_MEDIA/INVALID_INPUT/INVALID_IMAGE | upload·field 오류 |
| 429 | RATE_LIMITED | 한도 승인 후, Retry-After |
| 503 | SERVICE_UNAVAILABLE | job 시작 불가. LLM/renderer 작업 실패는 JobStatus.error |

job 오류: COPY_SCHEMA_INVALID, COPY_PROVIDER_TIMEOUT, RENDER_FAILED, FACTS_MISMATCH. ranker/분석 fallback은 warnings이며 완료를 막지 않습니다. 후보 일부만 생성된 경우 completed를 반환하지 않습니다.

## 계약 테스트와 고정 시점

공동 fixture로 네 strategy·ID 완전 일치, 사실 문자열 동일, finite score·동점·wrong version·path, mock/real 동일 schema, edit revision을 검증합니다. 원본 일정은 Week 5 input, Week 6 output, Week 7 artifact/failure 고정입니다. OpenAPI→frontend 타입 생성은 S1 제안이며 이 문서는 구현된 schema가 아닙니다.

## v1.1 확정 모델 접점

2026-10-24 승인된 최종 RGB PNG, open_clip_torch, 비율 유지 padding, 네 후보 batch, version/ID 유지와 선택적 pairwise는 [RANKING_CONTRACT_V1_1](RANKING_CONTRACT_V1_1.md)이 기준입니다. 기존 Ranking에 nullable pairwise를 추가하며 mock은 확률을 생성하지 않습니다. B RankOutput의 입력 순서와 서비스 Ranking의 rank 순서를 구분합니다. 현재 실서비스 ranking endpoint는 구현하지 않습니다.
