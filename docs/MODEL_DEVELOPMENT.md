# 팀원 B 모델 개발 시작 안내

## 현재 준비 상태

2026-10-12 점검: B(`parkyeonwooo`)에게 write 권한 초대를 보냈지만 아직 수락 대기입니다. GitHub에서 초대를 수락한 뒤 본인 계정으로 인증합니다. A의 인증 토큰이나 API 키를 공유하지 않습니다.

GitHub Flow, PR/Issue 템플릿, 서비스 CI와 [역할 분담](ROLE_SPLIT.md)은 준비되어 있습니다. **`ml/`, `tests/ml/`, 모델 전용 requirements/lock 파일, 학습·추론 코드와 모델 artifact는 아직 없습니다.** Clone만으로 학습할 수 있는 환경이 완성됐다는 뜻은 아닙니다. 이번 점검에서는 B 소유 코드를 생성하거나 변경하지 않았습니다.

## Clone과 작업 브랜치

Git/Python 설치와 서비스 실행은 [README](../README.md), Git 절차는 [CONTRIBUTING](../CONTRIBUTING.md)을 따릅니다. 모델 개발에는 서비스 서버 실행이 필수가 아닙니다.

```powershell
git clone https://github.com/Noah3507/hanjang.git
cd hanjang
git status --short --branch
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c feat/ml-environment
```

이미 같은 작업 브랜치가 있다면 새로 생성하지 않고 `git switch <기존 브랜치>` 후 `git pull --ff-only`합니다. PR #8과 #9는 병합 완료됐으며 최신 main에는 업로드와 협업 안내가 포함됩니다. 필요한 서비스 계약 변경은 A와 먼저 합의합니다.

## B가 첫 PR에서 준비할 영역

| 계획 경로 | B 책임 |
| --- | --- |
| `ml/data/` | 데이터 접근 코드·manifest·split 정의; 원본 데이터 제외 |
| `ml/features/` | feature 순서·전처리·버전 정의 |
| `ml/training/` | 학습 코드와 재현 config |
| `ml/evaluation/` | 평가·baseline·metric·재현 보고서 |
| `ml/inference/` | 합의된 모델 loader/scoring/ranking interface |
| `scripts/ml_*`, `tests/ml/` | 독립 실행·smoke·단위 테스트 |

이 경로들은 소유권 계획입니다. B가 자신의 feature 브랜치에서 생성합니다. A는 읽기·계약 검토만 하며 label/split/scaler/feature 순서/metric을 변경하지 않습니다. A의 `backend/app/ml_adapter/`와 공용 schema는 공동 계약에 맞춰 별도로 통합합니다.

## 모델 환경 격리와 확정할 항목

서비스 CI는 Python 3.12 기반입니다. **모델 Python 버전·PyTorch/CLIP 구현·CUDA·GPU 필요 여부·정확한 의존성 버전은 아직 확정되지 않았습니다.** B가 자신의 CPU/GPU와 라이브러리 호환성을 확인한 뒤 전용 환경과 pin/lock 파일을 첫 PR에 제안합니다. 서비스 `backend/requirements.txt`에 학습 의존성을 섞지 않습니다.

아래는 B가 Python 3.12 호환성을 확인했을 때 사용할 환경 생성 예시이며, 학습 패키지 설치 완료 절차가 아닙니다.

```powershell
py -3.12 -m venv .venv-ml
.\.venv-ml\Scripts\python.exe -m pip --version
# B가 의존성 파일을 추가·검증한 뒤 실행할 예:
# .\.venv-ml\Scripts\python.exe -m pip install -r ml/requirements.txt
# .\.venv-ml\Scripts\python.exe -m pip check
# .\.venv-ml\Scripts\python.exe -m pytest tests/ml
```

현재 위 requirements와 테스트는 없으므로 설치·테스트 성공을 주장하지 않습니다. 가상환경은 각 PC에서 재생성하며 `.venv-*/`는 Git 제외입니다. 데이터 접근 권한·라이선스·다운로드 용량·외부 비용은 합의가 필요합니다. 모델 artifact 기본 root는 artifacts/models/로 사용자 확정됐습니다. `/data/`는 원본 데이터 경로 제안, `artifacts/models/`는 확정 모델 root이며 실제 데이터·가중치·캐시·사용자 사진은 commit하지 않습니다. manifest/checksum/config/model card 등 비밀 없는 재현 정보만 공유합니다.

## 모델 연동 계약: 준비된 초안과 미확정 사항

[API_CONTRACT의 B ranking adapter](API_CONTRACT.md#b-ranking-adapter-계약)가 기준입니다. `load_model`, `extract_features`, `score_ad`, `rank_ads` signature와 tie/exception 규칙은 **B 승인 전 제안**입니다. 이번 문서로 확정하거나 구현하지 않습니다.

- 입력: candidate ID와 서버가 관리하는 최종 광고 PNG의 안전한 로컬 경로. 원격 URL이나 사용자 임의 경로를 받지 않습니다.
- 출력: model/feature version과 네 후보의 ID·유한 scalar score·rank. ID 누락/중복, NaN/Infinity, version 불일치 등을 A adapter가 검증하는 설계입니다.
- preference는 상대 선호이며 구매율·매출·CTR 예측이 아닙니다. 실제 B 모델에 strategy label을 feature로 넘기지 않는 초안입니다.
- 모델+scaler/config, feature 순서·전처리·의존성·checksum·model card·sample smoke 절차를 B가 제공합니다.
- 모델 부재/실패 시 전체 MockRanker fallback과 mock 표시가 서비스 설계에 포함됩니다. **현재 실제 MockRanker·모델 adapter·광고 생성은 구현되지 않았습니다.**

첫 공동 리뷰에서 입력 이미지 조건, 함수 signature, version/exception, timeout, 동점 규칙, artifact 위치와 독립 smoke fixture를 합의한 뒤 계약·소비자를 함께 수정합니다. 사용자 업로드 대신 권한 확인된 fixture로 테스트합니다.

상세 전달 체크리스트와 확정/제안 구분은 [MODEL_HANDOFF](MODEL_HANDOFF.md)를 따릅니다. B는 서비스가 없어도 sample 광고 PNG로 데이터·feature·학습·평가·추론을 진행할 수 있습니다. A는 S5c MockRanker와 S6 서비스 흐름을 개발하고, 실제 모델 연결은 B6 이후 S8 별도 PR로 유지합니다. 현재 전체 광고 흐름은 미구현입니다.

## PR와 완료 기준

Issue 1개→B feature 브랜치→작은 검증 단위의 영어 Conventional Commit→push→main 대상 PR→A/B 리뷰→사용자 명시적 병합 승인 순서입니다. main 직접 push, force push, 자동 merge는 금지합니다. API 변경은 공동 합의합니다.

첫 환경 PR의 완료 기준은 버전/하드웨어/데이터 조건 문서화, pin/lock 파일, 독립 smoke 및 테스트 명령·실행 결과, 비밀/데이터 제외 확인입니다. 모델 다운로드 없이 실행 가능한 가벼운 fixture 테스트와 학습/대용량 평가를 분리합니다. 현재 CI에는 ML 전용 검증이 없으므로 B 환경이 확정된 뒤 공동 리뷰로 추가합니다. 기존 서비스 CI 통과를 모델 평가 통과로 해석하지 않습니다.

최종 재조회에서 protect-main Ruleset의 main PR 필수·삭제/force push 금지가 확인됐습니다. 승인 리뷰 0건이며 필수 CI는 아직 없습니다. 두 사람 모두 PR 리뷰 절차를 지켜야 하며 저장소 권한/보호 변경은 사용자 승인 후 진행합니다.

## 2026-10-24 데이터 및 경로 정책

[MODEL_STORAGE_AND_DATASET](MODEL_STORAGE_AND_DATASET.md)의 확인/미확인 표와 artifacts/models/ 및 RANKING_MODEL_PATH 정책을 적용합니다. 원본 라이선스와 동일성은 미검증입니다. 기존 B 코드와 파일은 변경하지 않으며 loader의 file/directory 경계는 공동 합의 사항입니다.

## 2026-10-24 모델 연동 계약 승인

확정된 출력/추론/예제와 미확정 bundle·배포 항목은 [RANKING_CONTRACT_V1_1](RANKING_CONTRACT_V1_1.md)을 따릅니다. PR 점검과 B 수정 요청·ML CI 계획은 [ML_PR_REVIEW](ML_PR_REVIEW.md)에 정리합니다. 이번은 문서·fixture·경량 검증이며 MockRanker 또는 실제 모델 기능을 구현하지 않습니다.
