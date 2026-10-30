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

- 결정 (A 동의, 2026-10-27): 기본 ViT-B-32. B-16은 같은 split·평가 지표에서 의미 있는 개선이 있을 때만 검토. L-14는 배포 후보에서 제외(연구 비교용으로만 남김).
- 전처리 결정: padding 흰색, 입력 224, open_clip 기본 보간·정규화, QuickGELU, `pad-square-v1`. 학습과 추론에 똑같이 쓰고 모델 manifest에 기록한다.
- 측정 스크립트는 macOS·Linux·Windows에서 실행된다(Windows는 추가 패키지 없이 Windows API로 메모리 측정). 입력은 정확히 4장, 1080×1350 RGB여야 한다.
- 1.52 GB는 Mac 측정 프로세스의 최대 메모리이며 배포 서버 전체 RAM 요구량이 아니다(FastAPI·이미지 처리 등은 별도).
- 배포 서버 CPU에서는 측정하지 않았다. 측정 JSON은 `artifacts/benchmarks/`(Git 제외)에 있다.
- 테스트: `python -m pytest tests/ml -q` → 28 passed (2026-10-27).

## feature cache (7단계, 2026-10-29)

`python scripts/ml_extract_features.py`가 split 결과(`data/processed/splits/split-v1/`)의 모든 이미지를 한 번 계산해 `data/features/<feature_version>/`(Git 제외)에 저장한다. 학습·평가는 이 파일만 읽는다.

- 이미지 받기: `python scripts/ml_fetch_images.py`. TASTE `images/`와 CreativeRanking `images.zip`에서 필요한 이미지(56,663장, 약 5.1 GB)만 range 요청으로 받는다. revision 고정, CRC32 검사, 이어 받기 지원. 107.7 GB zip 전체는 받지 않는다.
- CLIP: ViT-B-32 / openai, QuickGELU, CPU(서비스 순위 worker와 같은 장치), 입력 224, open_clip 기본 정규화, `pad-square-v1`(흰색) 후 L2 정규화한 float32.
- 이미지 통계(`stats-v1`): brightness, contrast, saturation, n_colors(16단계×3채널 색 중 나타난 비율). 패딩 전 원본 이미지 기준, 모두 0~1.
- 투명 이미지: 투명 부분을 패딩 색(흰색)으로 채운 뒤 계산한다. 개수는 manifest의 `alpha_flattened`.
- center crop: 평가(10단계)의 패딩 vs crop 비교용으로 val·test 이미지만 따로 계산한다. 학습·서비스 기본은 패딩이다.
- 파일: `<dataset>_index.parquet`(row, image, split, had_alpha)의 row 순서가 `<dataset>_clip.npy`, `<dataset>_stats.npy`의 행 순서와 같다. `manifest.json`에 모델·버전·열 순서·개수·코드 커밋·입력 SHA-256을 기록한다. pickle은 쓰지 않는다.
- 모든 이미지가 성공하고 값이 모두 유한할 때만 폴더가 한 번에 바뀐다.
- 속도 확인: `--time-only 200`은 200장만 계산해 속도와 전체 예상 시간을 출력하고 아무것도 쓰지 않는다.
