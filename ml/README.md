# ML 환경 (B: Preference Model & Evaluation)

## 버전
- Python 3.12.10
- torch 2.14.1, torchvision 0.29.1, open_clip_torch 3.3.0, pillow 13.0.0, pytest 9.1.1 — 전체 고정 버전은 ml/requirements.txt
- CLIP 라이브러리: open_clip_torch (import 이름 open_clip)
- CLIP encoder: 미확정. 후보 ViT-B-32, ViT-B-16, ViT-L-14 (pretrained=openai)의 CPU 메모리·추론 시간을 비교한 뒤 A와 결정
- 후보 목록은 ml/clip_config.py. embedding 차원과 입력 크기는 open_clip 모델 설정에서 읽는다(코드에 고정값 없음)

## 가상환경 분리
- ML은 .venv-ml, 서비스는 .venv를 따로 쓴다.
- 이유: ML의 pillow 13.0.0과 서비스의 pillow 12.3.0(rembg가 Pillow<13 요구)이 충돌한다.
- ml/requirements.txt를 서비스 .venv에 설치하지 않는다.

## 검증한 환경
- macOS 26.6.2, Apple Silicon(arm64), 메모리 24 GB, Python 3.12.10, 장치 MPS: tests/ml 통과
- Windows: 미검증 (CPU wheel 설치, torch/torchvision 호환, 설치 크기 확인 필요)
- Ubuntu: 미검증. 현재 CI는 tests/ml을 실행하지 않는다
- CLIP 가중치를 받아 실제로 추론한 적은 없다 (CPU 메모리·지연 미측정)

## 설치
- macOS: python3.12 -m venv .venv-ml → source .venv-ml/bin/activate → pip install -r ml/requirements.txt
- Windows(미검증): py -3.12 -m venv .venv-ml → .\.venv-ml\Scripts\python.exe -m pip install -r ml/requirements.txt
- Linux(미검증): torch가 GPU용 큰 파일로 설치될 수 있다

## 데이터 (Git에 올리지 않음)
- 원본 데이터와 캐시는 저장소 안 data/ 또는 datasets/ (Git 제외). ml/data/는 코드 전용이다.
- TASTE: https://huggingface.co/datasets/purvanshi/TASTE — Hugging Face card 표기 MIT, 약 1.6 GB. 이용 조건 근거는 다운로드 전에 기록한다.
- CreativeRanking(후보): https://huggingface.co/datasets/Evan12/CreativeRanking — card의 apache-2.0은 업로더의 metadata 표기다. Tianchi 원본과 동일한 데이터인지, 원본 라이선스와 재배포 권리는 모두 미확인이다. 확인 전까지 승인된 학습 데이터가 아니다. 사용하게 되면 전체 약 116 GB 중 10–20K 제품 subset만 쓸 예정이다.

## 모델 산출물 (Git에 올리지 않음)
- 기본 위치: artifacts/models/ranking/<version>/ (manifest, 모델, scaler/config)
- 서비스 설정 RANKING_MODEL_PATH는 모델 파일 경로다. 파일 형식과 manifest는 A와 합의 예정 (docs/RANKING_CONTRACT_V1_1.md)

## 테스트
- 실행: python -m pytest tests/ml (모델 가중치·데이터 다운로드 없음)
- 결과 (2026-10-25, macOS MPS): 8 passed
## CLIP 후보 측정 (2026-10-26, Mac CPU)

`scripts/ml_benchmark_clip.py`로 측정. MacBook Pro arm64, CPU 8스레드, Python 3.12.10, torch 2.14.1, open_clip 3.3.0. 광고 4장(1080×1350)을 `pad-square-v1`(흰색)으로 padding한 뒤 224로 줄여 한 번에 처리. openai 가중치에 맞춰 QuickGELU 사용(`ml.clip_config.uses_quick_gelu`).

| 모델 | embedding | 가중치 | 불러오기 | 4장 처리 (warm 중앙값) | 최대 메모리 |
| --- | --- | --- | --- | --- | --- |
| ViT-B-32 | 512 | 605 MB | 1.5초 | 0.042초 | 1.52 GB |
| ViT-B-16 | 512 | 599 MB | 1.6초 | 0.123초 | 1.49 GB |
| ViT-L-14 | 768 | 1.71 GB | 3.4초 | 0.442초 | 3.59 GB |

- 제안: 기본 ViT-B-32. B-16은 평가에서 확실히 나을 때만 검토, L-14는 제외. 배포 서버 사양이 정해지면 A와 최종 결정.
- 전처리 제안: padding 흰색, 입력 224, open_clip 기본 보간·정규화, QuickGELU, `pad-square-v1`.
- 배포 서버 CPU에서는 측정하지 않았다. 측정 JSON은 `artifacts/benchmarks/`(Git 제외)에 있다.
- 테스트: `python -m pytest tests/ml -q` → 17 passed (2026-10-26).
