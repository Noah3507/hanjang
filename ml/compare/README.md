# 일반 AI 비교 실험

교수님 피드백("우리 서비스를 쓰는 게 일반 AI한테 시키는 것보다 나아야 한다")에 답하기 위한 실험이에요.
사람이 점수를 매기지 않고, **같은 규칙으로 누구나 다시 잴 수 있는 것만** 비교해요.

## 무엇을 비교하나

| 항목 | 재는 방법 | 왜 중요한가 |
|---|---|---|
| 가격·가게명·상품명 정확도 | 광고 이미지에서 글자를 읽어(OCR) 입력값과 비교. 입력과 다른 가격이 적혀 있으면 "틀린 가격" | 가게 광고에서 가격이 틀리면 바로 손해 |
| 근거 없는 표현 | 우리 문구 검사기(`copy_validation.py`의 `CLAIMS`) 목록 + `30%`, `1위`, `1+1` 같은 숫자 표현 중 입력에 없는 것 | 할인·원산지·순위를 지어내면 허위 광고 위험 |
| 상품 사진 유지 | 올린 사진과 광고의 SIFT 특징점이 몇 개 맞는지 (50개 이상이면 "같은 사진") | 일반 AI는 상품을 새로 그려서 실제와 달라질 수 있음 |
| 가격만 고치기 | "가격만 바꿔 줘" 전후로 가격 영역 밖에서 바뀐 픽셀 비율과 SSIM, 새 가격이 있고 예전 가격이 없는지 | 가게는 가격이 자주 바뀜. 다시 만들 때마다 광고 전체가 바뀌면 곤란 |
| 시간·비용 | 기록표의 값 | 실제로 쓸 만한지 |

특징점 기준 50개는 보정한 값이에요. 같은 사진을 가로 200px로 작게 넣어도 73개가 맞았고, 흐리게 하거나 뭉갠 사진은 17~39개였어요.

**한계도 같이 적어요.** OCR은 꾸민 글씨를 잘못 읽을 수 있어요(예: 굵은 "원"을 "2!"로). 두 시스템에 똑같이 적용되고, 읽은 글자 원문은 `measurements.json`에 남아서 사례마다 확인할 수 있어요. 맞는 가격을 확인할 때는 "25000원"을 "2500074"처럼 읽는 경우도 맞는 가격으로 봐요(틀린 가격을 찾을 때는 이렇게 봐주지 않아요). 광고가 예쁜지, 사고 싶은지는 재지 않아요.

## 공정하게 하기 위한 규칙

- 두 시스템에 **같은 사진, 같은 가게명·상품명·가격·분위기·광고 목적**을 넣어요.
- 일반 AI에도 우리 서비스가 지키는 규칙(상품 그대로, 정보 정확히, 지어내지 않기)을 프롬프트로 알려 줘요. 문장은 `prompt.md`에 고정돼 있어요.
- **첫 결과만** 써요. 마음에 안 든다고 다시 만들지 않아요. 거절당하거나 오류가 나서 다시 했으면 `attempts`와 `notes`에 적어요.
- 사례마다 **새 채팅**을 열어요. 가격 수정은 같은 채팅에서 이어서 해요.
- 우리 쪽은 사이트가 처음 보여 주는 결과와 같게, 고른 전략의 **추천 1위 시안 한 장**만 써요.
- 사진은 팀이 직접 찍었거나 써도 된다고 허락받은 것만 써요. 사진과 광고 이미지는 `artifacts/compare/`(git에 안 올라감)에만 둬요.

## 준비 (한 번만)

Tesseract(글자 읽기 프로그램)를 설치해요.

```
brew install tesseract tesseract-lang
```

나머지(OpenCV, scikit-image, Pillow, httpx)는 서비스용 `.venv`에 이미 있어요.

## 순서

### 1. 사례 정하기

`cases.example.csv`를 `artifacts/compare/cases.csv`로 복사하고 사례를 채워요. 사진은 `artifacts/compare/photos/`에 넣어요.

| 열 | 내용 |
|---|---|
| case_id | c01, c02 … |
| photo | 사진 경로 (cases.csv 기준 상대 경로) |
| store_name, product_name, price_text | 입력 정보 |
| new_price_text | 가격만 고칠 때 바꿀 가격 |
| mood | warm, minimal, vivid, premium |
| ad_goal | menu_promotion, store_visit, order |
| product_features | 상품 특징 (없으면 비움) |
| strategy | 우리 쪽에서 쓸 전략: emotional, price, visual, brand (비우면 price) |

### 2. 일반 AI 광고 만들기 (사람이 직접)

`prompt.md`의 문장으로 ChatGPT 등에서 광고를 만들고, 같은 채팅에서 가격만 바꿔요.
이미지는 `artifacts/compare/general/`에 저장하고, `results-general.example.csv` 양식대로 `artifacts/compare/results-general.csv`를 채워요.

- `make_seconds`, `edit_seconds`: 보내기를 누른 순간부터 이미지가 다 보일 때까지 걸린 초
- `cost_usd`: 앱 구독으로 만들었으면 비워 두고 `notes`에 요금제를 적어요
- 이미지 경로는 `results-general.csv` 기준 상대 경로예요

### 3. 우리 광고 만들기 (자동)

로컬 서버를 연습용 문구 설정으로 켜고(최상위 README의 "개발 서버 실행" 참고) 실행해요. 사례마다 사이트의 한 번에 만들기와 같은 순서로 시안을 만들고, 추천 1위 시안을 저장한 뒤 가격만 고친 시안과 걸린 시간까지 저장해요.

```
.venv/bin/python scripts/ml_compare_general_ai.py make-hanjang --cases artifacts/compare/cases.csv --out artifacts/compare/hanjang
```

서버가 유료 OpenAI 문구를 쓰도록 켜져 있으면 스크립트가 멈춰요. 실제 문구로 비교하기로 팀이 정했을 때만 `--allow-paid`를 붙여요.

### 4. 재기

```
.venv/bin/python scripts/ml_compare_general_ai.py measure --cases artifacts/compare/cases.csv --results artifacts/compare/hanjang/results-hanjang.csv --results artifacts/compare/results-general.csv --out artifacts/compare/report
```

결과물은 다음과 같아요.

- `summary.md`: 시스템별 비교표 (발표에 바로 쓸 수 있는 형태)
- `measurements.json`: 사례별 세부 값과 OCR이 읽은 글자 원문
- `sheet-c01.png` …: 사례별로 원본 사진, 각 시스템 광고, 가격 수정본을 나란히 놓은 이미지

## 테스트

```
.venv/bin/python -m pytest tests/ml/test_compare_general_ai.py
```

합성 이미지만 써요. Tesseract 한국어 데이터가 없으면 OCR 테스트 하나는 건너뛰어요.
