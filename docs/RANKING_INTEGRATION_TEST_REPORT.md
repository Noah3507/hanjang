# 12단계 Preference 모델 연동 검증 기록

2026-11-02, Windows/Python3.12, 기준 main `0dd176d`, `feat/service-ranking-integration`. 기존 branch/worktree/transfer/.env/가상환경/모델/ZIP을 보존했다. B 소유 파일과 가중치는 변경하지 않았다.

## 구현 파일과 계약

A adapter `real_ranker.py`/`ranking_worker.py`, RankingStore/main/config, 로컬 실행 스크립트, 순위 표시 UI와 관련 시험/문서를 수정했다. B의 load_model/RankInput/rank_ads를 그대로 호출한다. 서비스 .venv에는 torch/open_clip/safetensors가 없고 Pillow12.3.0이므로, manifest와 일치하는 .venv-rank(Pillow13.0.0/torch2.14.1/open_clip3.3.0/numpy2.5.4/safetensors0.8.0)를 사용한다. backend 의존성을 추가하지 않았다.

기존 POST/GET ranking·Candidate·Ranking v1.1 shape/인증/TTL/revision/snapshot 계약은 유지했다. 서비스 기본은 실제 model, Mock은 명시적인 시험 모드만 허용한다. 실패 시 자동 fallback을 만들지 않는다. 로딩된 버전/원시 score/1~4위가 API와 UI에 표시되고 가독성 영역에는 합산하지 않는다.

## 최종 테스트

| 검사 | 최종 결과·조건 |
| --- | --- |
| 전체 backend pytest | **405 passed, 0 failed, 0 skipped**, 168.15초, AnyIO deprecation 경고1 |
| backend opt-in | RUN_RENDER_TESTS=1, RUN_RANKING_TESTS=1; 실제 Chromium·실제 B 번들 포함 |
| frontend test:ci | **67 passed, 0 failed, 0 skipped**, 15파일 |
| TypeScript / production build | 통과 |
| 전체 Mock-ranking 브라우저 회귀 | **30 passed, 0 failed, 1 skipped**, 실제 모델 전용 testcase만 제외, 2.7분 |
| 실제 모델 브라우저 testcase | **1 passed, 0 failed, 0 skipped**, 최종18.9초 (runner20.2초) |
| B smoke (record 아님) | PASS, 최대 score 오차 **9.46e-06**, 허용0.001 |

실제 모델 backend testcase는3개이다: 정상 bundle의 score/순서/cache, 별도 작은 시험 bundle의 manifest 누락, 손상된 가중치 무결성 거부. 나머지 adapter 오류/timeout/NaN/ID·순서·rank 오류/복구는 가짜 로컬 worker 또는 주입 ranker로 격리했다. 두 경로를 실제 추론 성공으로 합산하지 않는다. CI는 모델/ML 환경을 다운로드하지 않고 opt-in3개와 Windows 전용3개를 명시적으로 skip하며 렌더러 opt-in은 별도 browser job에서 실행한다.

초기 시험에서는 테스트의 Popen 대체가 종료 명령까지 가로채는 문제, 단순 UI fixture의 warnings 누락, 오래된 미구현 안내문/기본 모델 None 기대값이 실패했다. 모의 코드·호환 처리·기대값을 수정하고 최종 전체 검증을 재실행했다. 최초 로그는 Git 제외 artifacts에 보존했다.

## 실제 서비스 증거

실제 에스프레소 상품 사진을 업로드하고 Mock 카피로 실제 광고 PNG4장을 렌더링한 뒤 모델을 실행했다. fixture 점수를 서비스 응답으로 사용하지 않았다. revision1의 실제 결과:

| rank | strategy | raw score |
| --- | --- | --- |
| 1 | price | -1.1389292855296673 |
| 2 | visual | -1.3112551590916335 |
| 3 | emotional | -1.4531641483648474 |
| 4 | brand | -1.6178512881050877 |

source=model, model_version=bt-logistic-v1. candidate ID 집합이 실제 rendering 결과와 같고, ID로 결합한 strategy·rank·score가 UI와 일치함을 브라우저 assertion으로 확인했다. 모델의 작은 점수 차이는 객관적 품질 차이를 의미하지 않는다.

실제 모델 UI에서 진단4개와 score 분리, 편집 후 revision2·이전 순위 숨김, 실제 모델 재평가, PNG/PDF 다운로드, 공백 포함 가격 보존, 모바일 가로 넘침 없음, Console/pageerror 오류 없음까지 검증했다. 전체 회귀에는 업로드/분석/Mock카피/렌더링/편집/다운로드/진단/권한/만료/stale/지연·오류 처리를 포함한다. OpenAI 경로는 기존 fake SDK 시험으로 검증하며 실제 유료 호출은 하지 않았다.

## 로딩·성능

기존 사용자 측정은 load1.211초/첫 추론0.375초/20회 중앙값0.344초/p950.4298초이다. 이번 worker에서 같은 합성 광고4장으로20회 반복한 별도 측정은:

- load **1.085초**, 첫 rank_ads **0.320초**
- warm rank_ads 중앙값 **0.320초**, p95 **0.367초**
- worker 생성/import/파일 snapshot/IPC 포함 cold wall **5.589초**
- 파일 snapshot/IPC 포함 warm wall 중앙값 **0.325초**, model_loads=1

CPU4스레드, 전체 pytest/브라우저 병렬 시험 종료 후 측정했다. B 함수 시간과 서비스 전체 지연을 구분하며 기존 측정의 프로세스·스레드·부하 조건이 완전히 같다고 가정하지 않는다. 순서 변경 후 동일 score와 캐시 재사용도 확인했다. p95는20회 표본의 inclusive quantile이며 보장 SLA가 아니다.

## 명령과 결과물

```powershell
$env:RUN_RENDER_TESTS='1'
$env:RUN_RANKING_TESTS='1'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv-rank\Scripts\python.exe scripts/ml_smoke_inference.py
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test:ci
npm.cmd --prefix frontend run build
# 전체 회귀: 명시적인 mock-ranking 서버
$env:PLAYWRIGHT_FRONTEND_PORT='5183'
$env:PLAYWRIGHT_BACKEND_PORT='8013'
$env:PLAYWRIGHT_RANKING_MODE='mock'
npm.cmd --prefix frontend run test:e2e -- --reporter=list --output=../artifacts/ranking-integration/browser-mock
# 실제 모델: 실제 서버와 .venv-rank/B bundle 필요
$env:PLAYWRIGHT_FRONTEND_PORT='5182'
$env:PLAYWRIGHT_BACKEND_PORT='8012'
$env:PLAYWRIGHT_RANKING_MODE='model'
$env:PLAYWRIGHT_REQUIRE_RANKING_MODEL='1'
npm.cmd --prefix frontend run test:e2e -- e2e/ranking-model.spec.ts --reporter=list --output=../artifacts/ranking-integration/browser-real-final
```

실제 상품 파일은 로컬 PLAYWRIGHT_RANKING_SAMPLE로 지정했다. 필요하면 PLAYWRIGHT_PYTHON으로 기존 서비스 Python을 지정한다. CI/모델 없는 환경에서 RUN_RANKING_TESTS와 실제 모델 flag를 켜지 않는다. source/모드가 다른 서버를 재사용하지 않는다.

로그·벤치마크·시험 JSON/스크린샷/다운로드는 `artifacts/ranking-integration/`에 보존한다. 특히 `browser-real-reviewed/**/ranking-model-result.json`은 실제 후보/asset/revision/점수 연결을 담는다. 모델·로컬 JSON·이미지·키는 Git 제외다. 실행 설정·오류 정책은 [RANKING_SERVICE](RANKING_SERVICE.md)를 따른다.

## 사용자 확인과 남은 범위

실제 모델 화면 http://127.0.0.1:5182 / Swagger http://127.0.0.1:8012/docs, Mock 회귀 화면5183/API8013을 별도 저장 위치에서 실행했다. 기존 포트의 프로세스를 종료하지 않았다. 브라우저에서 사진·필수 정보 저장→Mock카피→PNG4장→순위 계산→모델 버전/score 확인→가독성 진단→편집→순위 재계산→PNG/PDF 다운로드로 확인한다.

실제 유료 OpenAI/학습/평가/모델 다운로드는0회다. 모델 권리·편향·설명 가능성은 B 모델 카드의 한계를 유지한다. 이번은 service 연결 검증이며 학습 성능 개선이나 구매율 예측이 아니다. 메모리 job/24시간 TTL·단일 서버, worker당 모델 메모리, 전원 종료 후 임시 파일 정리, 다중 서버/배포/개인화 등13단계 운영 작업은 남는다. worker는 shutdown 때 닫히며 별도 idle eviction은 없다. 최종 commit/PR/CI 식별자는 완료 보고와 GitHub에서 확인한다. PR은 사용자 검토 전 병합하지 않는다.
