# 입력 및 이미지 업로드 검증

2026-10-12, feat/service-upload. 범위는 원본 업로드·입력 draft 저장·조회뿐이며 광고 생성·이미지 변환·모델은 구현하지 않았습니다.

## 구현 및 계약

POST /sessions, POST /uploads, GET /assets/{asset_id}, 승인된 PUT /jobs/{job_id}/input과 별도 GET 조회를 추가했습니다. GET JobStatus를 변경하지 않고 동일 draft 응답으로 입력을 읽습니다. 저장 상태는 pending이고 POST /jobs는 없습니다. 입력의 공백·한글·emoji·가격 단위와 원본 byte/hash를 보존합니다.

## 실제 실행 결과

- pytest 37개 통과: 원본 JPEG/PNG byte·hash, 사실 문자열·조회, 세션 소유권, MIME 위장·decode·길이/크기·제어 문자·unknown fields, TTL·orphan·경로·CORS.
- Vitest 11개 통과: health와 입력 필수·길이·파일·서버 실패·정확한 요청·서버 재조회.
- TypeScript·build·pip check 통과.
- Playwright 실제 Chrome 11개 통과: 기존 health 5개와 업로드 6개. PNG/JPEG 원본 다시 받기·입력 저장/조회·탭 새로고침, 필수/형식·작은 이미지 실제 거부, 저장 장애 모의 후 실제 복구, 375px 모바일.
- 시험에는 가짜 상점 텍스트·Pillow로 만든 단색 fixture만 사용했습니다. 이미지 fixture는 실제 상품 광고 생성이 아닙니다. 네트워크 서비스·LLM·B 모델을 호출하지 않았습니다.
- 초기 pytest 오류는 자동 testcase ID가 Windows 임시 경로 길이를 초과한 시험 구성 문제였습니다. 짧은 ID로 수정 후 모두 재검증했습니다. 제품 오류로 숨기거나 성공으로 처리하지 않았습니다.

## 사용자 확인

http://127.0.0.1:5173에서 사진과 가게/상품/가격/분위기를 입력해 저장한 뒤 '저장 정보 다시 조회'로 원래 문자열·원본을 확인합니다. http://127.0.0.1:8000/docs에서 같은 API를 확인할 수 있습니다. [README 체크리스트](../README.md#상품-입력업로드-직접-확인-체크리스트)를 따릅니다. 이번 서버는 loopback에서 유지했습니다.

실제 screenshot과 Console/실패 로그는 Git 제외 artifacts/playwright/에 있습니다. 실패 시 screenshot/trace/video를 보관하도록 구성했으며 이번 최종 실행에는 테스트 실패가 없었습니다. desktop/mobile 업로드 화면을 직접 확인했습니다. CI는 개인정보 없는 단색 fixture 업로드 screenshot만 upload-ui-screenshots artifact로 7일 보관해 PR에서 검토할 수 있게 합니다. 실제 사용자 사진·token·.env는 commit하지 않습니다.

## 한계

메타데이터와 세션은 메모리라 서버 재시작/배포 시 재업로드가 필요할 수 있습니다. 원본은 24시간 보존 후 60초 sweep·시작 정리로 삭제하며 서버 정지 중 삭제는 실행할 수 없습니다. 수정은 TTL을 연장하지 않습니다. 검증은 시간을 앞당긴 저장소/API 시험으로 TTL 동작을 확인했으며 실제 24시간을 기다린 시험은 아닙니다.

기존 AnyIO alias 폐기 예정 경고 1건은 남아 있습니다. 배경 제거·프로필 localStorage·광고 processing/polling·ranking·편집·다운로드·다른 PC 실행은 이번 기능 완료에 포함하지 않습니다. B ml/ 코드는 변경하지 않았습니다. CI의 별도 Linux Chromium 결과는 PR Checks에서 확인합니다.
