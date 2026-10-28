# Hanjang 디자인 설계 초안

근거: P10·11·14·16, R3·9. 원본은 mobile-first, 전략별 템플릿, 사진·사실 보존을 요구합니다. 정확한 비율·좌표·폰트·반응형 breakpoint는 자료에 없으므로 아래는 **검토용 설계 제안**입니다. 발표 예시의 음식 일러스트를 서비스의 생성 이미지 사용 허가로 해석하지 않습니다.

자료 충돌은 최종 발표본 기준입니다. 사용자 승인으로 상품 색상·채도·명도 보정은 보류하며 배경 제거·비율 유지 리사이즈만 허용합니다. 처리 실패·품질 저하 시 보존 원본을 선택할 수 있습니다. 필수 우선순위는 업로드→네 광고→선호 순위→문구 수정→PNG, A4는 그 이후 OPTIONAL입니다.

## 공통 광고 캔버스

초기 Instagram PNG는 1080×1350(4:5), 안전 여백 5%를 제안합니다(D11). 정사각·story·복수 비율은 미확정입니다. 모든 후보는 동일 실제 사진에서 얻은 원본 또는 cutout, 동일 가게명·상품명·가격을 사용합니다. 상품 전체 silhouette를 유지하고 왜곡·생성형 확대·상품 가림·내용 변경을 금지합니다. 사진 배경이 유지될 때는 상품 포함 전체 frame을 contain으로 배치합니다.

입력 사실은 전용 text box에 그대로 표시하며 generated copy와 섞어서 대체하지 않습니다. 가격 단위·쉼표는 입력값 그대로입니다. 긴 이름은 줄바꿈→허용 최소 크기 내 축소→대체 layout 순서로 대응합니다. 그래도 넘치면 명확한 오류이며 ellipsis·문자 삭제·자동 별칭 금지입니다.

## 전략별 실제 레이아웃 차이

비율은 canvas 면적의 대략적 목표이며 crop이나 픽셀 동일성 검증을 대신하지 않습니다. 단순 색상 교체로 네 전략을 구현하지 않습니다.

| 전략 | geometry·시각 계층 제안 | 텍스트·사진 배치 | 금지·실패 기준 |
| --- | --- | --- | --- |
| emotional | 상단 좌측 20% headline, 하단/우측 40–50% 상품, 별도 하단 정보 strip. 비대칭·넓은 여백 | 감성 headline→상품→상품명→가격→가게명. warm palette 기본이지만 mood 적용 가능 | 실제 사실인 듯 성분·행사·날씨·원산지 창작 금지. 감성 문구가 사실 box를 대체하면 실패 |
| price | 상단 25–30% 가격 panel, 중간 35–45% 상품, 하단 메뉴·가게 정보. 큰 입력 가격이 최상위 요소 | 가격→상품명→사진→가게명. 가격 panel이 다른 후보에 없는 큰 영역 | 할인율·할인 전 가격·최저가·기간·혜택 생성 금지. 가격을 숫자로 재포맷하면 실패 |
| visual | 중앙 55–65% 상품, generated copy 최소화, 하단 compact facts stack. 사진 중심 대칭 | 사진→상품명→가격→가게명. 상품 위 text overlay 없이 실제 사진 최대 활용 | AI로 음식 다시 그리기·부분 확대 재생성·비율 왜곡 금지. 가격·가게명을 숨겨도 실패 |
| brand | 상단 20–25% 가게명 masthead, 중앙 35–45% 상품, 하단 메뉴·가격·선택 연락처. 정돈된 grid | 가게명→사진→상품명→가격. 입력 가게명 자체를 typographic anchor로 사용 | 미입력 로고·슬로건의 사실 주장·수상 이력 생성 금지. 가게명보다 generated headline이 크면 실패 |

각 template version별 bbox·font 계층을 고정하여 visual QA에서 상단 anchor, 상품 크기, alignment, 정보 영역이 실제로 다른지 확인합니다. rank가 visual 1위로 항상 나오는 것은 MockRanker fixture일 뿐 디자인 정책이 아닙니다.

## 분위기와 팔레트

P14는 따뜻한 감성·깔끔한 미니멀·활기찬 강렬함·고급스러움 예시를 제시합니다. enum warm/minimal/vivid/premium 매핑은 제안입니다. 분위기는 strategy를 선택·제거하지 않습니다. warm+price도 price geometry를 유지합니다.

K-means dominant color는 템플릿 배경·accent 후보만 제공합니다. 상품 색 자체를 palette에 맞춰 변경하지 않습니다. contrast 부족 시 중립 surface를 선택하고 실패값을 기록합니다. mood와 전략을 독립 적용하며 과도한 조합 폭발은 별도 template가 아닌 token으로 관리하는 안입니다.

## Typography와 진단 기준 제안

한글 지원·라이선스 확인된 폰트를 서버에 고정합니다. PNG 1080px 폭 기준 본문/사실 최소 32px, 주요 상품명 56–80px, price 전략 가격 88–120px를 검토값으로 둡니다. 작은 화면 preview 가독성과 출력물 QA 후 조정합니다.

UI 대비 목표는 일반 text 4.5:1, 큰 text 3:1을 제안합니다. 광고 raster는 실제 배경에서 계산 가능한 영역만 측정합니다. 사진 배경에서 계산이 불확실하면 unavailable이지 양호가 아닙니다. 상품 mask와 text bbox overlap은 배치 진단이며 사용자 attention 측정이 아닙니다.

규칙으로 읽기 순서를 추정하면 '레이아웃 기준 예상 순서'라고 표시합니다. UMSI가 없는데 '상품에 시선이 먼저 가요'라고 출력하지 않습니다. 실제 UMSI도 모델 추정임을 표시합니다.

## UI 화면과 상태

| 화면 | 구성·동작 |
| --- | --- |
| 입력 | 사진 upload/preview, 보존 원본/배경 제거본 비교·원본 사용 선택, 가게명·상품명·완성 가격 문자열, optional 주소·Instagram, mood 선택, 프로필 저장 toggle/초기화, 생성 CTA |
| 생성 | pending/processing/completed/failed 상태와 실제 stage, 실패 시 입력으로 돌아가기/재시도. MVP 작업 취소 기능 없음. 임의 시간·62% 같은 가짜 수치 금지 |
| 결과 | rank/전략 badge, 전체 광고 preview, thumbnail 네 개, 별도 ranking 설명·진단, 개별/전체 저장, 문구 편집 |
| 편집 | headline/body/CTA, 입력 사실 read-only 확인, 취소/저장, 재렌더링·재순위 상태. 이전 완성본 보존 |
| 오류/만료 | 단계·해결 방법, 재생성·입력 유지. 비밀·서버 path·타 사용자 정보 숨김 |

결과 UI는 '상대 선호 순위'와 설명을 우선하고 원시 score는 상세 영역에 둡니다. 퍼센트·막대의 구매 가능성 해석을 피합니다. mock/fallback은 계속 보이는 '데모 순위 — 실제 선호 모델 미사용' 배너를 둡니다. 데이터가 없는데 '선호 높음/보통' 임계값을 만들지 않습니다. 높은 model score가 가독성 양호를 뜻하지 않습니다.

## 반응형 제안

| viewport | UI 배치 |
| --- | --- |
| 320–767px | 한 열 입력, 결과는 선택 카드+thumbnail 또는 swipe, index와 버튼으로 접근 가능. 긴 가격 입력도 잘리지 않음 |
| 768–1199px | 입력/preview 두 열, 결과 2×2 또는 상세+목록 |
| 1200px 이상 | 최대 content 폭 1280px 제안, 네 preview 비교와 선택 상세 panel |

광고 PNG geometry는 viewport에 따라 바뀌지 않습니다. UI에서 비율 유지 축소만 합니다. UI breakpoint를 export layout로 사용하지 않습니다. 320·375·768·1280px에서 페이지 가로 overflow·버튼 가림·키보드 focus·입력 label·error 연결을 검증합니다. touch target 최소 44px, 색만으로 상태 표현하지 않기, alt text는 사실 기반으로 작성하는 제안입니다.

## A4와 디자인 완료 기준

A4는 PNG MVP 이후 OPTIONAL이며 최종 필수 완료 조건에서 제외합니다. 선택 구현 시 210×297mm 별도 print layout, 10mm 여백 제안, 한 페이지·한글 font·사실 동일성·사진 비율·PDF 출력 확인을 추가합니다. 정확한 인쇄 DPI·bleed는 원본에 없으므로 합의합니다.

완료 기준: 같은 입력의 네 후보에서 geometry 차이를 사람이 확인, 원본 상품 형태·내용과 factual 문자열 동일, 긴 이름·사진 배경·투명 PNG·한국어 검사, metadata와 실제 screenshot 일치. 사용자 승인 전 이 표를 완성된 디자인 시스템으로 취급하지 않습니다.
## 2026-10-28 구현된 S5b 기준

1080×1350·54px 여백·네 전략 geometry·로컬 Noto Sans KR2.004를 적용합니다. normal의 주요 정보 계층을 유지하되 긴 입력은 compact/dense 대체 layout과32px 최소 글꼴을 사용합니다. 실제 폰트 glyph 높이 때문에 line-height1.5를 적용했으며 그래도 넘치면 RENDER_LAYOUT_OVERFLOW입니다. 주소/Instagram은 값이 있으면 원문 표시하고 없으면 요소를 숨깁니다. 실제 규격/측정은 [RENDERING](RENDERING.md)을 따르며 아래 미구현 UI(ranking/edit/export)는 후속 제안입니다.
