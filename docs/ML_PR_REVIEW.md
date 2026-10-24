# 모델 연동 계약 및 기존 PR 검토

2026-10-24 읽기 전용 점검. PR/브랜치를 임의 병합하지 않았으며 B 코드를 수정하지 않았습니다.

## PR 현황

| PR | 상태/CI/개별 병합 | 변경 범위 |
| --- | --- | --- |
| [#11 이미지 전처리](https://github.com/Noah3507/hanjang/pull/11) | OPEN, 네 service check 성공, MERGEABLE/CLEAN | 33파일: backend photo API/schema/processor/worker/storage/config, frontend 비교 UI·API·E2E, Pillow/rembg/CPU 의존성, env/docs/CI synthetic artifact |
| [#13 B 환경](https://github.com/Noah3507/hanjang/pull/13) | OPEN, 기존 service CI 성공, MERGEABLE/CLEAN | 6파일: ml/__init__.py, device.py, README.md, requirements.in/txt, tests/ml/test_ml_smoke.py |
| [#14 저장 정책](https://github.com/Noah3507/hanjang/pull/14) | OPEN, 네 service check 성공, MERGEABLE/CLEAN | 12파일: backend config, env, ranking settings test, README 및 정책/계약 관련 docs |

검토 대상 head: #11=5e4e1e6, #13=edd2d2c, #14=9760fc9. 개별 CI 통과는 세 PR을 함께 적용한 통합 테스트가 아닙니다. 세 PR의 전체 변경 파일 목록은 GitHub Files changed에서 확인합니다.

Git `merge-tree --write-tree --name-only`로 #11과 #14를 시뮬레이션한 결과 아래 5파일에서 실제 content conflict를 확인했습니다. 작업 파일·브랜치에는 merge하지 않았습니다.

- .env.example
- README.md
- backend/app/config.py
- docs/DEVELOPMENT_PLAN.md
- docs/TECH_SPEC.md

#11의 photo 설정과 #14의 RANKING_MODEL_PATH 설정은 역할이 다르므로 둘 다 보존해야 합니다. 공통 변경 docs/API_CONTRACT.md는 이 조합에서 자동 통합됐지만 의미 일관성 리뷰는 필요합니다. B PR은 새 ML 소유 파일만 추가해 직접적인 파일 충돌이 적지만 문서·의존성의 의미 충돌은 남아 있습니다.

## 권장 검토·병합 순서

1. #11의 실제 사진 비교·원본 fallback을 사용자 검토하고 승인 후 수동 병합합니다.
2. #14 담당자가 최신 main을 자신의 브랜치에 정상 merge하고 위 5파일에서 photo/ranking 설정과 문서를 모두 보존합니다. force push/rebase/amend 없이 충돌 해결 commit·CI·재리뷰 후 사용자 승인으로 병합합니다.
3. 이번 계약 PR도 그 시점 main을 정상 merge해 문서 충돌을 해결하고 계약 테스트/CI를 재실행한 뒤 별도 승인으로 병합합니다. #14의 코드나 정책을 이번 PR에 복사하지 않습니다.
4. #13은 B가 아래 수정 사항을 자신의 PR에 반영하고 서비스/ML 환경 경계를 재검토한 뒤 승인·병합합니다. B 작업은 위 과정 동안 병렬로 계속할 수 있으며 순서를 이유로 B의 독립 개발을 막지 않습니다.

병합마다 후속 PR의 충돌/CI를 다시 조회합니다. 기존 CI 결과만 보고 연속 자동 병합하지 않습니다. 이번 PR 생성은 병합 승인을 의미하지 않습니다.

## B에게 전달할 수정 요청

| 발견 사항 | B 수정/확인 요청 |
| --- | --- |
| README open_clip_torch 0.29.1, lock은 3.3.0 | 정확한 라이브러리 버전으로 정정. 0.29.1은 lock의 torchvision 버전 |
| ML Pillow 13.0.0, service 12.3.0 | ML/service venv 분리 유지. rembg의 Pillow<13 조건을 무시해 서비스 버전을 올리지 않음 |
| README ViT-L-14/openai/768과 특정 차원 smoke | 기본 배포 모델로 확정하지 않음. architecture별 smoke와 공통 인터페이스 검증을 구분하고 dimension을 metadata 기반으로 검증하도록 제안 |
| macOS freeze만 검증 | Windows/Ubuntu CPU wheel 가용성·torch/torchvision 호환·설치 크기를 별도 검증 |
| 후보 데이터 이용 조건 | HF card license 표기는 업로더 주장으로 구분하고 원본 동일성/권리 증거를 확인 |
| artifacts 경로 선택 미정 표현 | 사용자 확정 artifacts/models/ 정책과 RANKING_MODEL_PATH 파일 의미 반영 |
| loader/preprocess/batch | 문서 v1.1에 맞춘 manifest·padding·batch/단일 score 일관성·예외 전달안을 공동 리뷰 |

A는 ml/·tests/ml/·학습/평가·scaler·feature 순서·label/split을 변경하지 않습니다. 이 문서는 B에게 보낼 내용이며 외부 메시지를 자동 전송하지 않았습니다.

## OS별 검증을 구분

- Mac: B가 PR에 macOS 26.6.2/Apple Silicon arm64/24GB/Python 3.12.10/MPS에서 ML smoke 5개 통과를 보고했습니다. A의 재실행 실적은 아닙니다.
- Ubuntu: PR #13의 backend/frontend/repository-policy/browser-e2e 성공 확인. pytest.ini가 tests/service만 수집하므로 ML smoke 실행 실적이 아닙니다.
- Windows ML: B lockfile 설치/ML smoke/실제 encoder 추론 미검증. 이번 A 계약 테스트는 Windows 서비스 venv에서 가중치 없이 실행합니다.
- 가중치 추론/CPU 메모리/지연: 어느 service CI 결과로도 검증됐다고 주장하지 않습니다. 모델 config의 768 확인은 실제 embedding 계산이 아닙니다.

## ML CI 제안과 비용·영향

이번 실제 변경은 pytest.ini에 tests/integration을 추가하는 것뿐입니다. 기존 backend CI의 Python/Pydantic/Pillow로 계약 테스트를 실행하고 새 의존성·runner·다운로드는 추가하지 않습니다. tests/ml은 자동 수집하지 않습니다. fixture/scheme 검사 시간은 로컬에서 1초 미만이며 CI 추가 시간은 수초 이내 예상입니다.

별도 `ml-smoke` job은 **제안만 하며 이번 workflow에는 추가하지 않습니다.** B가 Ubuntu CPU 의존성을 검증한 뒤 공동 리뷰합니다.

```yaml
# 설계 예시, 실행되는 workflow가 아님
ml-smoke:
  runs-on: ubuntu-latest
  timeout-minutes: 10
  steps:
    # checkout + Python 3.12 + 검증된 CPU용 ML lock 설치
    # HF_HUB_OFFLINE=1, TORCH_HOME/HF_HOME은 빈 임시 cache
    # python -m pip check
    # python -m pytest tests/ml
```

패키지 설치는 네트워크를 사용하지만 모델 가중치·데이터셋 다운로드는 금지합니다. `pretrained=None` 또는 config/fake feature 검증만 사용하며 실제 encoder 생성도 큰 RAM 할당 가능성이 있어 단순 config 조회와 구분합니다. HF offline 변수만으로 모든 다운로드를 차단한다고 가정하지 않고 테스트에서 network 호출을 실패시키는 방안도 B와 합의합니다.

추가 job은 PR/push별 runner 하나와 PyTorch/open_clip 설치·cache 저장 공간을 사용합니다. CPU wheel이어도 설치 용량이 클 수 있으며 분 단위 초기 실행이 예상되지만 정확한 크기/시간/요금은 아직 측정하지 않았습니다. 10분은 실행 예상치가 아닌 제안 timeout 상한입니다. 현재 private Actions 한도·요금제도 여기서 확정하지 않습니다. 패키지·CPU wheel source·cache key·path filter를 검증한 뒤 실제 CI 변경 범위와 측정치를 보고합니다.

## 6단계 이미지 분석 전 게이트

확인 가능한 main/열린 브랜치에는 CLIP 기반 6단계 이미지 분석 구현이 없습니다. 다른 PC의 미push 코드까지 확인한 것은 아닙니다. 새 단계 시작 전 원격/로컬 상태를 다시 확인하고, 이미지 분석의 open_clip 의존성을 서비스에 넣을지 별도 process로 격리할지 결정해야 합니다. 현재 service/ML Pillow 충돌을 해결하지 않은 상태에서 venv를 합치지 않습니다. 모델 기본 architecture·배포 CPU 메모리·batch4 cold/warm latency는 측정 후 선택합니다.

## 이번 계약 검증 기록

Windows Python 3.12.10 서비스 venv에서 pytest 75개(기존 service 37 + integration 38)가 통과했습니다. 계약 검사만 실행하면 38개가 약 0.3초에 통과했습니다. PyTorch/ML 패키지 설치·모델/데이터 다운로드·B 테스트는 수행하지 않았습니다. PNG 4장 합계 약 120KB와 JSON Schema/semantic 검증만 사용합니다. 기존 AnyIO alias deprecation 경고가 남아 있습니다.

fixture 재생성 후 schema drift 검사도 통과했습니다. 화면·실행 서비스 변경이 없어 로컬 frontend/Playwright를 반복 실행하지 않고 PR의 기존 전체 CI와 구분합니다. 개발 서버와 개인 브라우저는 변경하지 않습니다. 합성 이미지 fixture는 테스트 목적의 승인된 소형 자료이며 사용자 업로드나 generated 서비스 결과물을 Git에 추가한 것이 아닙니다.
