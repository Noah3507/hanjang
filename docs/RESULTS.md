# 9단계 결과 비교 및 Mock 임시 순위

## 범위와 보존

최신 main `e114d7d` 기반 `feat/service-results`에서 결과 확대·MockRanker·Ranking API를 추가한다. 기존 rendering API, Candidate 및 B v1.1 계약을 유지한다. 실제 ML·편집·다운로드·가독성 진단·배포·Figma/타이포그래피 기능은 포함하지 않는다.

기존 `feat/service-openai-validation`의 `3f4eea7`은 main 미반영 상태로 별도 보존했다. OpenAI 예산/오류/글리프 보완과 노트북 복원 기록을 자동 이식하거나 merge/rebase하지 않았다. 이 브랜치가 해당 보완을 포함한다고 주장하지 않는다. 실제 API 호출 없이 Mock/paid=false로 검증한다.

## 사용자 흐름

사진·원문 입력 저장 → 4전략 카피 생성 → 광고4장 렌더링 → 카드 확대 비교 → 임시 순위 확인. 저장 정보 다시 조회 후 광고와 기존 순위를 읽을 수 있다. 입력창을 바꾸면 기존 snapshot의 결과 영역이 숨겨지고, 저장 후 서버 stale 판정을 따른다.

확대는 인증된 PNG Blob을 재사용한다. 공개 URL·인증 우회·파일 다운로드 기능은 없다. Enter/Space로 열고 닫기/ESC로 닫으며 초점은 원래 버튼으로 돌아온다. Tab/Shift+Tab은 확대창 안에서 유지한다. 이미지 권한/디코딩 오류는 카드별로 안내·재조회한다.

필수 UI 안내: **시연용 임시 순위이며 실제 광고 품질 평가 결과가 아닙니다**

순서는 visual → emotional → price → brand다. API score는 기존 fixture와 같은 .8/.6/.4/.2 고정 시험값이며 품질·확률·CTR·매출을 측정하지 않는다. UI는 점수·확률을 표시하지 않는다. `source=mock`, `model_version=mock-v1`, `feature_version=null`, `pairwise=null`이다.

## 승인된 추가 API

Phase A에서 제안하고 Phase B 승인으로 추가했다. 소비자는 A FastAPI/React/서비스 테스트다. B 함수·출력 및 Candidate·rendering 계약은 변경하지 않는다.

공통: `/api/v1`, `X-Hanjang-Session`, no-store, 서버 경로 비노출. upload 생성 기준24시간 TTL이며 조회·재시도로 연장하지 않는다. 메모리 metadata는 재시작 복구를 보장하지 않는다.

### POST /jobs/{job_id}/ranking

```json
{
  "expected_render_revision": 1,
  "expected_candidate_ids": ["candidate-1", "candidate-2", "candidate-3", "candidate-4"]
}
```

실제 rendering 응답의 네 고유 ID를 그대로 보낸다. 요청 순서는 순위가 아니다. 사용자 점수·strategy·파일 경로를 받지 않는다. 응답202/Location, background task 완료는 GET으로 확인한다. 동일 snapshot의 processing/completed는 재사용하며 failed만 POST 재시도한다.

### GET /jobs/{job_id}/ranking

읽기 전용. 미생성은 pending/ranking=null, 실행 실패는 failed/error다.

```text
RankingResponse = {
 job_id, operation:"ranking", status, status_url,
 revision:int|null, is_current:bool, ranking:Ranking|null,
 warnings:string[], error:{code,message}|null, expires_at
}
```

Ranking은 [기존 v1.1](RANKING_CONTRACT_V1_1.md) shape다. 네 ID·finite score·rank1..4·score 내림차순·동점 ID 사전순을 검사한다. HTTP items는 rank 순이며 strategy는 Candidate ID로 연결한다. B의 입력 순서 유지 계약과 다르므로 향후 adapter가 변환한다.

### snapshot 및 오류

- 현재 completed 렌더링·카피·사진·입력으로만 시작한다.
- identity: revision/source asset/copy_key/전체 Candidate snapshot. 콘텐츠 key: identity + 네 PNG SHA256.
- 소유 job의 파생 asset·실제 RGB1080×1350 PNG인지 검사한다. 완료 시·GET에서 재검사한다.
- 이전 결과는 보존하되 is_current=false이며 UI에서 최신 순위로 표시하지 않는다.
- 같은 identity의 PNG 내용 변경 시 current 사용과 새 POST를 거부한다. 재렌더링을 안내한다.
- 만료/cleanup 후 게시하지 않는다. ranker 실패는 ranking만 failed로 만들고 광고를 보존한다.
- frontend도 revision/ID/asset/사진·카피 snapshot 및 요청 ticket으로 늦은 응답을 버린다.

| 오류 | 의미 |
| --- | --- |
| 401 / 404 / 410 | 기존 세션·소유권/리소스·만료 정책 |
| 422 / 413 | 요청 형식·후보 수/중복·revision 오류 / body16KiB 초과 |
| 409 RANKING_RENDER_NOT_READY | 최신 광고 미완료/stale |
| 409 RANKING_SOURCE_CHANGED | 기대 revision/ID 불일치 |
| 409 RANKING_CANDIDATES_INVALID | 서버 후보 수/ID/strategy/revision/facts 불일치 |
| 409 RANKING_ASSET_INVALID / CHANGED | 최종 PNG 규격 또는 내용 snapshot 불일치 |
| failed + RANKING_FAILED | 실행/출력 검증 실패. 내부 예외 비노출 |

## 실행과 검증

새 dependencies·모델·폰트가 없다. 기존 `.env`를 수정·복사하지 않는다. worktree에서 기존 서비스 Python을 명시적으로 재사용할 수 있다.

```powershell
# 터미널1: 작업 트리 루트, 서비스 환경 Python 사용
$env:HANJANG_COPY_PROVIDER='mock'
$env:HANJANG_COPY_ALLOW_PAID='false'
$env:HANJANG_UPLOAD_ROOT=Join-Path $PWD 'artifacts/results/uploads'
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8002

# 터미널2
$env:DEV_BACKEND_URL='http://127.0.0.1:8002'
npm.cmd --prefix frontend run dev -- --port 5175
```

화면 http://127.0.0.1:5175, Swagger http://127.0.0.1:8002/docs. 포트의 기존 프로세스를 임의 종료하지 않는다. 재부팅 후 재실행하고 새 작업을 업로드한다.

검증: pytest, frontend typecheck/test:ci/build/test:e2e. 실제 renderer opt-in은 RUN_RENDER_TESTS=1. 다른 Python 경로는 PLAYWRIGHT_PYTHON으로 지정한다. CI 구성 변경 없이 기존 backend/frontend/browser-e2e/repository-policy에 포함된다. 결과는 [RESULTS_TEST_REPORT](RESULTS_TEST_REPORT.md)를 참조한다.

## 12단계 교체 지점과 한계

`ml_adapter/mock_ranker.py`는 A 소유이며 B 코드·가중치를 import하지 않는다. 서비스 ranker 주입 지점에서 향후 합의된 B 응답을 v1.1 Ranking으로 검증·변환한다. B 함수 signature·bundle·예외를 확정하는 구현은 아니다.

네 후보 누락·잘못된 PNG를 Mock 성공으로 숨기지 않는다. 이번 E2E의 모델 없는 rembg/CLIP fallback은 실제 모델 검증이 아니다. 편집·다운로드·진단·디자인 시스템 및 실제 model/fallback worker는 범위 밖이다.
