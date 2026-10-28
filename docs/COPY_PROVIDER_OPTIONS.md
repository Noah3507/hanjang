# 카피 제공자와 멀티모달 비교 검토 (2026-10-28)

사용자는 **실제 OpenAI 결제/호출을 보류**했습니다. 현재 기본 제공자는 Mock이며 OpenAI adapter 방향을 유지합니다. 다음은 공식 문서 확인과 구현 영향의 비교이지, 제공자 변경·가입·키 발급·다운로드·실제 호출 승인이 아닙니다. 한국어 카피는 어느 제공자도 이번에 실제 생성하지 않았으므로 품질 순위를 매기지 않습니다.

## 무료·저비용 대안

| 후보 | 무료 API/비용 | Structured Outputs | 한국어 광고 품질 검증 | 코드 변경 범위(향후 승인 시) |
| --- | --- | --- | --- | --- |
| 현재 Mock | 무료, 외부 API 아님 | 고정 예시+Pydantic | 생성 품질 평가 대상 아님 | 현재 구현 |
| 승인된 OpenAI GPT-5.4 mini | 일반 무료 티어를 전제로 하지 않음. 입력$0.75/출력$4.50 per1M | Responses JSON Schema 지원 | 미검증. 계정 접근도 미검증 | 현재 adapter 준비, 실제 검증 보류 |
| Gemini Flash-Lite 계열 | 일부 모델 무료 티어 있음, 모델/계정/지역 quota 확인 필요. 예:3.1 Flash-Lite 유료 입력$0.25/출력$1.50 per1M | JSON Schema 지원, 지원 subset·모델별 확인 | 미검증. 동일 한국어3사례로 검토 필요 | 새 provider+SDK/키·schema 매핑·모의/계약 시험, 프론트/공용 카피 계약 재사용 가능 |
| Groq 지원 모델 | Free Plan rate limits 제공, 실제 계정 한도 확인 필요 | GPT-OSS20B/120B 등 지정 모델 strict schema 지원, 모든 모델 지원 아님 | 미검증. 한국어 자연스러움/지시 준수는 모델별 시험 필요 | OpenAI 호환 API라도 전용 provider·인증·응답/사용량/지원 파라미터 매핑 필요. 현재 OpenAI base URL을 바꾸지 않음 |
| 로컬 Ollama+선정 모델 | 외부 API 요금 없음. PC RAM/추론 시간/전력/가중치 용량과 라이선스 별도 | 로컬 format JSON Schema 지원. Ollama Cloud와 구분 | 모델 크기/학습/양자화에 따라 미정, 미검증 | 로컬 HTTP adapter·timeout·모델 설치/버전/성능 측정 필요. B 환경/분석 환경에 섞지 않음 |

문서 기반 무료 API 검토의 첫 후보는 Gemini 무료 티어입니다. 다만 무료 티어의 제품 개선 데이터 이용 표기가 있으므로 실제 고객 정보 대신 합성 데이터로 시작해야 합니다. Groq는 무료 quota와 strict 지원 모델을 함께 확인해야 합니다. 완전 로컬은 외부 전송을 줄이지만 현재 CLIP/rembg와 함께 사용할 메모리·CPU를 따로 측정해야 합니다. 이는 추천 검토 순서이며 한국어 품질 우열을 뜻하지 않습니다.

근거: [OpenAI 모델/가격](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [Gemini 가격/무료 티어·데이터 이용](https://ai.google.dev/gemini-api/docs/pricing), [Gemini Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output), [Groq 무료/유료 rate limits](https://console.groq.com/docs/rate-limits), [Groq schema 지원 모델](https://console.groq.com/docs/structured-outputs), [Ollama 로컬 schema](https://docs.ollama.com/capabilities/structured-outputs). 확인 시점 이후 요금·모델·무료 한도는 바뀔 수 있습니다.

## 공통 비교 시험안 — 아직 실행하지 않음

합성3사례(카페·베이커리·지역 매장)와 동일 Facts/features/mood를 사용합니다. 조건별 네 전략의 구분, 사실 침범 수, 길이/스키마/재시도, 한국어 자연스러움·과장·CTA를 사람이 블라인드로 검토합니다. 입력/출력/추론 토큰·비용·first/cached latency를 측정합니다. 무료여도 외부 전송·계정 연결은 별도 승인 후 진행하고, LLM judge를 추가 호출하지 않습니다. 3사례는 정식 품질 벤치마크나 통계적 우월성 근거가 아닙니다.

## CLIP 단서 전송 vs 원본 사진 직접 전송

| 관점 | 현재 CLIP 단서 방식 | 직접 이미지 방식(미승인·미구현) |
| --- | --- | --- |
| 정보/품질 | 제한 후보로 압축돼 세부 사진 정보가 누락되거나 잡음일 수 있음 | 더 많은 시각 문맥을 볼 가능성. 맛·재료·원산지의 사실 확인을 대신하지 못함 |
| 비용 | 로컬 CLIP CPU/RAM 비용+외부 텍스트 토큰 | 이미지 해상도/detail에 따른 이미지 입력 토큰 추가. 동일 조건 실측 전 총액 단정 불가 |
| 속도 | CLIP 미리 완료 시 텍스트만 전송. cold model 준비는 별도 지연 | 업로드/전처리/원격 이미지 분석 지연. 로컬 cold CLIP을 생략하면 총시간이 줄 가능성도 있어 실제 비교 필요 |
| 개인정보 | 이번 payload는 photos/paths/Instagram 제외, 주소 명시 옵션 | 사진의 얼굴·배경·간판·메타데이터 등 추가 노출 가능. 동의·샘플 출처·제공자 정책 검토 필요 |
| 변경 범위 | 현재 text provider 유지 | 별도 image provider 경로·전송 통제·동의·비용 추정·검증 필요. 이번에는 구현하지 않음 |

향후 사진 전송을 별도 승인하면 동일3사례의 text+CLIP(A)와 text+image(B)를 비교하되 facts/특징 우선 규칙과 출력 schema는 같게 합니다. 현재 실제 호출은0회입니다. 기존 승인된6회/$0.10은 **현재 보류**이며, 재승인 시 A3회+B3회도 이미지 토큰/재시도 포함 총한도 내에서만 가능합니다. A 시험에서 재시도를 소모하면 잔여 호출을 차감하고 B를 축소하거나 추가 승인을 요청합니다. 이미지 요금을 계산하지 않은 채 사진을 보내거나 예산을 새로 초기화하지 않습니다.

이미지 지원과 비용 산정 근거: [OpenAI Images and vision](https://developers.openai.com/api/docs/guides/images-vision). 사진을 직접 보내도 시각 추정은 사용자 사실보다 우선하지 않으며 원본 보존 규칙을 유지해야 합니다.
