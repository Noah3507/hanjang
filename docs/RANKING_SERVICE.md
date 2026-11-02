# 12단계 실제 Preference 모델 서비스 연동

## 경계와 호환성

`ml.inference.load_model`과 `RankInput`/`rank_ads`를 소비하는 A 전용 worker를 추가한다. B의 모델·학습·특징·전처리·가중치·문서는 수정하지 않는다. 입력은 상품 사진이나 텍스트가 아닌 **현재 revision의 최종 RGB1080×1350 광고 PNG 네 장**이다. strategy/facts는 서비스 매핑에만 사용하고 B feature로 보내지 않는다.

POST/GET `/api/v1/jobs/{job_id}/ranking`, 세션 인증, revision/ID 요청, Ranking v1.1 응답 형태를 유지한다. `source=model`, 실제 model_version/feature_version/score/rank/pairwise는 B 반환값에서 가져온다. HTTP items만 rank 순 복사 정렬하고 B 입출력 순서를 바꾸지 않는다. 새 계약 필드는 추가하지 않는다. warnings의 `RANKING_MODEL_MODE`는 실제 모델 모드이고, 명시적 Mock에는 기존 시연 경고를 사용한다.

## 실행 환경과 설정

서비스 `.venv`는 torch/open_clip/safetensors를 import하지 않는다. 기존 별도 `.venv-rank`와 B의 `ml/inference/requirements.txt`를 사용한다. 런타임 설치·모델 자동 다운로드·번들 업로드 API는 없다. 모델이 없는 clone/CI에서도 나머지 서비스는 실행된다.

| 서버 설정 | 기본값/의미 |
| --- | --- |
| HANJANG_RANKING_MODE | model. mock은 명시적인 개발/테스트 시연용 |
| RANKING_MODEL_PATH | artifacts/models/ranking/bt-logistic-v1/model.safetensors, **파일** 의미 유지 |
| HANJANG_RANKING_PYTHON | 현재 프로젝트의 .venv-rank/Scripts/python.exe (Unix는 bin/python) |
| HANJANG_RANKING_TIMEOUT_SECONDS | 30, worker 초기 import/로딩/추론 포함, 0초 초과~120초 |
| HANJANG_RANKING_TEMP_ROOT | artifacts/ranking-runtime, 비공개 일회용 PNG snapshot |

명시적으로 빈 RANKING_MODEL_PATH를 제공하면 모델 미설정으로 취급한다. 모델을 사용하려면 파일 경로를 지정하거나 빈 설정을 제거해 기본값을 사용한다. 폴더를 파일 설정에 넣지 않는다. 모델 버전을 바꾸면 승인된 bundle 전체와 맞는 inference 환경이 필요하다. 기존 모델/ZIP/환경 파일을 Git에 포함하지 않는다.

Windows는 [LAPTOP_SETUP](../LAPTOP_SETUP.md)의 실행 스크립트를 사용한다. Git 제외 `artifacts/local-dev.json`의 resource_root를 기존 리소스 프로젝트로 지정한다. 선택적인 ranking_python, ranking_model_path, ranking_mode, upload_root를 지정할 수 있다. 기본 실제 모델, 기본 카피 Mock/paid=false이다. 기존 JSON/.env를 덮어쓰지 않는다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/service_local.ps1 -Port 8012 -FrontendPort 5182
# 별도 frontend 터미널
$env:DEV_BACKEND_URL='http://127.0.0.1:8012'
npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 5182
```

최초 준비 또는 B와 합의한 재검증은 `.venv-rank`의 `python scripts/ml_smoke_inference.py`이다. `--record`는 B 전용이며 서비스 작업에서 실행하지 않는다.

## 데이터 흐름과 캐싱

1. RankingStore가 현재 네 후보·소유권·TTL·facts·revision·PNG 형식/내용을 확인한다.
2. 실제 검사한 바이트와 hash key를 다시 대조하고 index 기반 안전한 파일명으로 비공개 임시 snapshot을 만든다. candidate ID를 파일명으로 사용하지 않는다.
3. 전용 Python worker에 해당 ID/경로만 보낸다. worker는 허용된 임시 root 밖 경로를 거부한다.
4. B loader가 manifest·파일 해시/크기·패키지·전처리를 검증하고 모델을 worker당 한 번 로딩한다. 동일 worker가 요청을 직렬 처리하며 CPU4스레드로 재사용한다.
5. B rank_ads 결과의 순서·ID·finite score·rank·버전을 서비스 schema로 검증하고 ID로 연결한다.
6. 완료 직전 현재 snapshot을 다시 검사한다. 편집/카피/사진/입력/revision 또는 번들이 바뀌면 이전 결과는 is_current=false이다.

동일 completed snapshot은 API에서 재사용한다. 번들 manifest 내용과 파일 stat fingerprint를 캐시 키에 포함한다. 번들 파일이 바뀌면 worker가 B loader로 재검증하고 모델을 교체한다. A가 scaler/특징 순서/가중치를 고치지 않는다. 로딩 시 해시 검증 후 캐시된 모델은 같은 프로세스에서 읽기 전용으로 사용한다.

worker 초기 import 시간도 timeout에 포함된다. timeout/깨진 출력/모델 오류는 A가 생성한 worker와 그 Windows venv 자식만 종료한다. 다음 POST에서 새 worker로 재시도한다. 앱 종료 시 worker를 닫는다. 사용자의 다른 Python 프로세스나 B 작업 환경을 종료하지 않는다. 임시 snapshot은 성공/실패/timeout 후 제거하지만 업로드·최종 PNG는 삭제하지 않는다. 비정상 전원 종료로 남은 임시 파일은 별도 운영 정리 대상이다.

## 점수와 UI

score는 원시 상대 선호 실수이며 높은 순서부터1~4위다. 음수도 정상이다. 동점은 candidate ID 사전순이고 근접 점수는 반올림으로 뒤집거나 합산하지 않는다. B 계약의0.2 미만 인접 차이는 가까운 후보 안내로만 표시하며 객관적 우열을 주장하지 않는다. 버전과 실제 모델 실행 여부를 표시하고 실수 score를 그대로 노출한다. Mock은 점수/확률을 숨기고 기존 시연 안내를 표시한다.

pairwise는 기존 API 계약에 포함하되 UI에서 확률·백분율로 바꾸어 보여주지 않는다. 모델 점수는 CTR/매출/전환율/객관적 디자인 품질이 아니며 서로 다른 상품/모델 버전 간 직접 비교하지 않는다. OCR로 문구 의미를 이해하는 모델이 아니다. 가독성 진단은 별도 영역·규칙·측정값이며 모델 score와 합산하지 않는다.

## 오류와 재시도

기본 경로에는 자동 Mock fallback이 없다. 실패는 기존 failed/error·ranking=null을 반환하며 source=model 점수를 조작하지 않는다. 이미 생성한 광고·편집·PNG/PDF 다운로드·진단을 유지한다. 복구 후 동일 snapshot의 실패 작업을 POST로 재시도할 수 있다. 명시적 mock 설정만 MockRanker를 사용한다. 스키마는 기존 fallback_mock도 읽을 수 있지만 이번 구현은 자동 fallback_mock을 생성하지 않는다.

| 안전한 오류 코드 | 원인 |
| --- | --- |
| RANKING_MODEL_UNAVAILABLE | 모델 파일/manifest/구성 파일 없음 |
| RANKING_ENV_UNAVAILABLE | 지정한 worker Python 없음 |
| RANKING_ARTIFACT_INVALID | B loader의 해시·버전·설정 무결성 불일치 |
| RANKING_IMAGE_INVALID | B가 광고 PNG를 거부 |
| RANKING_INFERENCE_FAILED | B 추론·환경 import 오류 |
| RANKING_OUTPUT_INVALID | worker JSON·ID·순서·score·rank·version 오류 |
| RANKING_TIMEOUT | 설정된 실행 제한 초과 |

사용자 응답에 내부 경로·stack·원래 예외 문구를 전달하지 않는다. 잘못된 PNG/현재 광고/세션/만료는 기존409/404/401/410 검증을 먼저 적용하며 Mock으로 감추지 않는다.

## 검사와 한계

기본 pytest는 worker 모의·explicit Mock·오류·snapshot·편집·다운로드·진단을 검증한다. `RUN_RANKING_TESTS=1`은 기존 실제 B bundle/.venv-rank가 있을 때만 opt-in한다. CI는 다운로드하지 않고 실제 가중치 검사를 명시적으로 skip한다. 실제 UI 검증은 PLAYWRIGHT_REQUIRE_RANKING_MODEL=1, PLAYWRIGHT_RANKING_MODE=model과 실제 모델 서버로 실행한다. 기존 회귀 전체는 명시적 Mock 서버로 별도 실행한다.

실행 결과·명령·시간·검증 한계는 [RANKING_INTEGRATION_TEST_REPORT](RANKING_INTEGRATION_TEST_REPORT.md)에 기록한다. 이번 단계는 배포/다중 서버·작업 큐·개인화·디자인 개선을 구현하지 않는다. 모델 데이터 권리/편향·성능 한계는 B 모델 카드에 따른다. 유료 OpenAI는 호출하지 않는다.
