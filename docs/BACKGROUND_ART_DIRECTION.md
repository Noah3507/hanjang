# 로컬 AI 배경 아트 디렉션 — 2026-11-28

기준 main `e0aa299`(PR #91). **검토된 기존 배경을 이용하는 내부 opt-in만 구현했으며 기본 단색 광고·공개 API·frontend는 유지했다.** 새 이미지/LLM API 호출, 모델 다운로드, 사진 외부 전송, 운영 서버 재시작·배포는 없다.

## 실제 결과와 판단

기존 배경4장과 광고32장의 무결성을 확인하고 대표 원본·배경을 시각 검토했다. 최신 템플릿/Full U2Net/실제 저장 카피를 고정해 단색 A, 기존 중앙 cover B, 개선 C2를 비교했다. 최종 비교는30개 고유 RGB1080×1350 PNG이며 실패·비권장 사례도 포함한다. Codex의 정성 평가이며 사람 평가·경쟁 서비스 대비 우수성 검증은 아니다.

|조건|관찰·결정|
|---|---|
|A 단색|문구가 명확하지만 평면감과 떠 있는 합성 인상이 남는다. 기존 출력4장은 이전 검증 PNG와 픽셀 동일함을 확인했다.|
|B 기존 PoC|석재/목재 분위기가 생기지만 글자 뒤 무늬와 광원·그림자 부조화가 남는다. 단색보다 항상 좋지 않다.|
|첫 C 단색 안전 띠|템플릿 배경색으로 텍스트 뒤를 덮으니 사진과 다른 색의 띠처럼 보였다. 실패 사례로 보존하고 채택하지 않았다.|
|C2 질감 보존|실측 상품 중심에 배경의 조용한 영역을 맞추고 글자 뒤 배경 질감만 완화한다. 에스프레소/밝은 석재/emotional_a, 짜장면/어두운 목재/visual_d가 상대적으로 유망하다. 초기 C의 색 띠가 없어졌지만 접지감이 완성되지는 않았다.|
|어두운 배경+emotional_a|기존 어두운 글자색과 충돌한다. 색을 임의 변경하지 않고 검토 manifest에서 이 조합을 제외했다.|
|original+생성 배경|촬영 테이블과 생성 표면이 카드 두 겹처럼 보인다. 실험 PNG는 보존하되 서비스에서는 original에 새 배경 선택을 거부하고 기존 사진 카드를 유지한다. cutout 선택은 기억해 재사용한다.|

초기 원근·조명 정보가 없는 평면 plate를 상품 뒤에 놓는 것만으로 실제 공간 합성이 되지는 않는다. bbox 하단은 실제 접지점이 아니라 기하학적 추정이며 추가 그림자를 만들지 않았다. B의 기존 그림자는 그대로여서 이중 구현도 없다. 컵600×400의 확대 흐림·짜장면 천 잔여물·원형 슬롯 크기는 배경으로 해결한 문제가 아니다.

## 구현과 내부 계약

- `background_art_direction.py`: server-injected 검토 manifest만 허용한다. 상대 경로·root 범위·PNG/RGB·크기·SHA256·템플릿 호환성을 검사한다. asset ID, source, 모델/프롬프트 버전과 immutable 원본 plate bytes를 함께 보존한다. 자동 검색/생성/다운로드는 없다.
- `BackgroundContext`는 owner/job/기존 expires_at에 결합한다. 새 선택 시 파일을 검증하고, 성공한 context의 bytes는 원본 배경 파일이 없어져도 job TTL 안에서 재사용한다. 공유 검토 plate 파일은 읽기 전용 자원이며 사용자 job 정리로 삭제하지 않는다.
- A renderer/worker의 opt-in 배경 레이어만 추가했다. 지원 초기 템플릿은 visual_a/d·emotional_a다. 검토 manifest는 밝은 plate→visual_a/emotional_a, 어두운 plate→visual_d로 좁혔다. 전경 decoration이 상품을 덮으면 합성을 거부한다. B HTML/CSS·폰트·상품 배치·RGB/alpha를 변경하지 않는다.
- 실측 bbox/텍스트로 cover offset과 quiet bands를 계산한다. 질감 완화는 배경에만 적용하고 상품 보호 사각형은 제외한다. 글자색/크기나 진단 기준을 바꾸지 않는다. 호환성 확인이 대비 보장을 대신하지 않으며 실제 diagnostics가 계속 필요하다.
- `DesignStore.background_library`는 기본 None이다. 서버가 명시적으로 주입한 뒤에만 **내부** `apply_background(owner,job,strategy,DesignSnapshot,selections)`를 쓸 수 있다. 공개 route·입력 필드는 추가하지 않았다. 기존 POST의 임의 backgrounds 필드는422다.
- 배경 선택은 새 v3 세대/revision으로 게시한다. 배경 SHA·합성 버전·foreground hash·scope가 snapshot에 반영된다. 다른 전략도 보수적으로 stale 처리될 수 있다. v2·카피·분석은 재생성하지 않는다.
- 후보별 가격/문구 편집을 배경 변경·해제 시에도 보존한다. 서로 다른 편집값이면 각각 맞는 입력으로 렌더링한다. 가격/문구 편집은 같은 배경 context를 재사용하며 이미지 생성0회다.
- 손상/미검토/비호환 배경은 상태 변경 전에 거부한다. 렌더링 실패는 이전 성공 context/시안을 복구하고 호출자에게 오류를 반환한다. 추론 중 사용자 입력이 바뀌면 이전 결과는 최신으로 게시되지 않는다. 소유권·만료·기존 다운로드409 guard를 유지한다.
- VERSION은 유지한다. 기존 worker source fingerprint가 이번 JS 변경을 반영한다. 합성 정책은 `background-texture-safe-v1`, 후속 생성 계획은 `empty-layout-backdrop-v1`로 분리한다. 기본 광고 변경으로 유료 카피를 자동 호출하지 않는다.

## 검증과 결과물

`artifacts/background-art-direction/`:

- `gallery.html`, `blind-gallery.html`: A/B/C2 및 실패 관찰. 블라인드는 파일명도 조건을 숨기고 `blind-key-v2-local.json`에 대응표를 분리했다. 사람 평가 미완료.
- `final-comparison.json`, `verification.json`: 동일 카피·사진 SHA·위치·글꼴·비율, 기존 단색 픽셀 일치, source/context snapshot 검증. 표본의 불투명 내부 픽셀 총24,063개에서 변경0. 이는 전체 상품의 의미적 보존율이 아니며 반투명 경계는 새 배경과 정상적으로 혼합된다. 동일 cutout을 사용하는 A/B/C2의 foreground RGBA bytes는 동일하다. original 카드는 별도 대조 조건이다.
- `*-regions.png`, `future-requests.json`: 실측 상품/글자 보호 영역과 생성 크기1024×1536→최종1080×1350 crop을 반영한 text-only 요청 계획. 상호·가격·주소·연락처·자유 문구·사진은 포함하지 않는다. CLIP category 힌트는 확정 사실로 승격하지 않는다.
- `api/report.json`, `api/edited.png`, `api/edited.pdf`: 격리 TestClient에서 기존 카피를 Mock 표시로 재생하고, 검증된 Full 사진/CLIP cache를 재사용했다. 새 사진/CLIP 추론으로 보고하지 않는다. 실제 Chromium·bt-logistic-v1·기존 편집/다운로드 API로 선택→편집→해제→실패 보존을 검증했다. 1페이지 PDF에 동일 PNG RGB가 내장됐다. 모델은 새 배경 분포에서 검증되지 않았으므로 점수를 미적 품질 증명에 쓰지 않는다.
- 일반/블라인드30장씩 Chromium decode, console/pageerror0. 내부 선택 UI는 없으며 갤러리 브라우저 검증과 기존 서비스 CI E2E를 구분한다.

전체 backend945 passed/58 skipped를 수행한 뒤 original 선택 제한을 마무리했다. 재개 후 관련 회귀 및 최종 전체 CI 수치는 PR Checks/로그를 따른다. opt-in skip을 실제 모델/Chromium 성공으로 세지 않는다. 초기 비교 실행기의 Pydantic 복사 오류는 수정 후 완료된 PNG를 재생성하지 않고 이어갔다. 기존 실패 C와 이전 로그도 남겼다.

## B 협업 / 공개 계약 제안만

현재 빈 본문 조건 실측 예: 에스프레소 emotional_a 상품(x212.6,y257.6,w654.9,h604.8), quiet y27~153 및937~1328. 짜장면 visual_d 상품(x145.2,y204.6,w789.6,h790.9), quiet y27~153 및1012~1328. 문구/Fill에 따라 달라지므로 고정 좌표를 템플릿 정책으로 확정하지 않는다.

B와 합의할 metadata: background compatibility, camera/pose, 보호 영역, 실제 contact region, foreground overlay, shadow 책임(template/compositor 중 하나). 전경 fade가 있는 visual_c/emotional_b는 현재 opt-in 대상이 아니다. 가격/브랜드 전략은 기존 단색을 유지한다.

후속 additive API/UI 안은 별도 승인 대상이다: 기존 owner/TTL dependency로 보호한 background-selection POST에 expected_revision/snapshot과 검토 asset ID만 받는다. 응답에는 raw bytes/path 대신 선택/적용 상태·asset SHA/출처·합성 버전을 제안한다. original에서는 비활성/기억된 선택을 구분하고, 유료 생성 버튼과 무료 로컬 선택을 분리한다. 이번 PR은 이를 공개하지 않는다.

## 신규 생성 필요성과 비용 계획 — 실행 안 함

지금은 더 많은 무작위 배경보다 B의 조명·접지·영역 계약 합의가 먼저다. 이후 필요하면 coffee/emotional_a와 noodles/visual_d를 각1회, **최대2회/재시도0**로만 제안한다. `future-requests.json`은 실행기가 아니다. 기존 provider/원장 검증을 거치지 않고 raw SDK로 호출하면 안 된다.

[공식 Flare 모델 정보](https://developers.openai.com/api/docs/models/gpt-image-2.6-flare.md)를 확인했다: text input $5/M, image output $30/M. 기존1132 output tokens/image와 준비한 최대1618 UTF-8 bytes를 기준으로 약$0.08~0.10/2장 추정, 기존 정책 예약$0.25씩 총$0.50 안이다. 출력 토큰 변동이 있으므로 예약은 강제 청구 상한이나 확정 가격이 아니다. 실행 직전 계정 접근·출력 상한·가격을 재확인하고 새 승인을 받아야 한다. 사진/image input은0이다.

기존 [GPT Image1.5 문서](https://developers.openai.com/api/docs/models/gpt-image-1.5.md)는 현재 deprecated이므로 신규 권고에서 제외했다. 기존 이미지 원장4건/$0.141015 및 LLM 원장65건/$0.53191900(미확정 예약 포함 상한)의 SHA가 그대로다. 신규 유료 호출0. 기존 PoC 실행기의 과거 LLM baseline guard도 우회하지 않았으며, 후속 승인 시 현재 원장을 검증하도록 별도 검토해야 한다.

운영 기본값·서버·터널·환경·모델·사용자 파일·기존 결과물·transfer 보존. 생성 이미지/PDF·모델·원장·비밀은 Git 제외. main 병합·배포 없음. 시각적 이득은 제한된 두 상품의 정성 판단이며 전문 광고 완성도나 일반적인 우수성을 확정하지 않는다.
