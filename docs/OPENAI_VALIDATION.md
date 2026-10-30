# OpenAI 카피 보완 통합

## 현재 구현과 검증 범위

PR #39 병합 main `369592e`에서 별도 통합 브랜치를 만들고 보존 커밋 `3f4eea7`을 적용했다. `main.py` 자동 병합 후 CopyStore의 재시도 설정과 RankingStore 초기화·라우터를 모두 확인했다. 기존 Candidate/rendering/Ranking v1.1 계약을 변경하지 않는다. 통합 PR은 사용자 승인 전 병합하지 않는다.

기본은 Mock/paid=false이며 이번 통합에서 실제 OpenAI API·무료 대체 API·이미지 생성 API를 호출하지 않는다. 모델 ID와 SDK 요청 형식은 기존 구현을 유지한다. OpenAI 보완은 문구의 사실성 보장이나 디자인 시스템 구현을 의미하지 않는다.

## 구현

- 요청 예약 상한6회, 예산상한 $0.10, 앱 재시도0~1회 설정. SDK retry0, timeout30초, 출력2048 제한을 유지한다.
- 생성 외 모델 metadata 조회를 제거한다. 생성 시도마다 reserve→dispatched→실측 settle 또는 안전한 실패 코드를 기록한다.
- 기존 ledger 기록을 포함하며 불명 비용을 0으로 환불하지 않는다. 원장에는 키·상품·사진·prompt·응답 원문을 저장하지 않는다.
- usage 누락/잘못된 값/상한 초과, refusal/incomplete, timeout/429/quota/401/404/서버 오류를 구분한다. 실패해도 Mock으로 몰래 전환하지 않는다.
- 폰트 SHA256/cmap을 확인하고 생성 카피의 미지원 문자·이모지·ZWJ 등을 검사한다. 사용자 원문은 삭제·정규화·치환하지 않는다.
- prompt_version/glyph 정책을 캐시 키에 넣어 오래된 카피·PNG·순위를 최신으로 사용하지 않는다.

## 통합 시 최소 회귀 보완

동봉 폰트 누락/손상은 cmap 검사 전에 `RENDER_FONT_UNAVAILABLE`로 분류한다. 미지원 원문은 `RENDER_UNSUPPORTED_GLYPH`로 안내한다.

원장 JSON/구조 손상은 `COPY_BUDGET_INVALID`, 파일 읽기/저장 오류는 `COPY_BUDGET_UNAVAILABLE`로 차단한다. 예약 저장 실패는 요청을 보내지 않는다. 실패 상태 기록마저 실패하면 원래 안전한 공급자 오류와 기존 보수 예약을 유지하며 원장 원본을 삭제하거나 재생성하지 않는다. 원자적 파일 교체는 외부 청구와 분산 트랜잭션이 아니므로 디스크 장애 후 완전한 과금 감사까지 보장하지 않는다.

프롬프트 확대 후에도6000 byte 기반 입력 검사를 유지한다. 이는 실측 토큰수가 아니며 긴 입력을 몰래 자르지 않는다. 상한 초과는422, 일반 입력과 재생성은 회귀 테스트한다. 예산 단가는 기존 앱 추정값이며 공급자 청구 차단 기능을 대신하지 않는다.

공식 [오류 문서](https://developers.openai.com/api/docs/guides/error-codes)와 [Python SDK 문서](https://developers.openai.com/api/reference/python)의 오류 종류·SDK 재시도를 대조했다. 이 PR은 기존 제한 재시도 정책을 유지하며 일반 목적 재시도 엔진을 추가하지 않는다. 실제 호출 권한·현재 과금·공급자 응답은 이번 무료 시험으로 검증하지 않는다.

## 설정

`HANJANG_COPY_PROVIDER=mock`, `HANJANG_COPY_ALLOW_PAID=false` 기본. `HANJANG_COPY_MAX_REQUESTS=0..6`, `HANJANG_COPY_BUDGET_USD=0..0.10`, `HANJANG_COPY_MAX_RETRIES=0..1`. 원장 경로는 `HANJANG_COPY_BUDGET_PATH`, 키는 서버 전용 `OPENAI_API_KEY`이다. 기존 원장 삭제나 경로 변경으로 한도를 우회하지 않는다. 로컬 모델 실행 스크립트는 Mock을 강제하고 실제 .env를 변경하지 않는다.

## 시점별 과거 기록

1. 데스크탑 사전 보완: fake SDK/소켓 격리로 검증했으며 당시 실제 호출0회. 당시 기록의 pytest207+별도 opt-in/실제 렌더러 시험과 E2E23은 과거 환경 결과이다.
2. 이후 사용자 승인 실제 시험: 기록상 합성 상품3사례 카피 생성5회(재시도2회 포함), 입력2931/출력1195토큰, 추정 $0.00757575, PNG12장을 검증했다. 별도 이미지 편집1회는 상품 동일성 미통과로 서비스 채택하지 않았다. 상세 원장/결과는 Git 제외 백업 자료이며 이번 통합에서 재실행하지 않았다.
3. 노트북 9단계: PR #39와 별도 모델 복구를 검증했다. 당시 임시 프로세스 설정을 이번 반복 실행 스크립트로 안정화한다.
4. 현재 통합 결과·실행 명령·제약은 [HARDENING_TEST_REPORT](HARDENING_TEST_REPORT.md)를 따른다. 과거 수치를 현재 통합 통과 수로 합산하지 않는다.

Figma 고품질 템플릿·Typography System·새 아트 디렉션 운영 통합·실제 B 모델 순위는 이번 범위 밖이다. 로컬 모델 재사용·junction·서버 재실행은 [LAPTOP_SETUP](../LAPTOP_SETUP.md)을 따른다.
