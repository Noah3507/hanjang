# ML 환경 (B: Preference Model & Evaluation)

## 버전
- Python 3.12.10
- torch 2.14.1, open_clip_torch 0.29.1, pytest 9.1.1 — 정확한 버전은 ml/requirements.txt
- CLIP: ViT-L-14, pretrained=openai, embedding 768차원

## 검증한 하드웨어
- MacBook Pro, Apple Silicon(arm64), 메모리 24 GB, macOS 26.6.2, 장치 MPS
- Windows: 미검증
- Ubuntu(CI): 미검증

## 설치
- macOS: python3.12 -m venv .venv-ml → source .venv-ml/bin/activate → pip install -r ml/requirements.txt
- Windows(미검증): py -3.12 -m venv .venv-ml → .\.venv-ml\Scripts\python.exe -m pip install -r ml/requirements.txt
- Linux(미검증): torch가 GPU용 큰 파일로 설치될 수 있다

## 데이터 (Git에 올리지 않음)
- TASTE: https://huggingface.co/datasets/purvanshi/TASTE — MIT, 약 1.6 GB
- CreativeRanking: https://huggingface.co/datasets/Evan12/CreativeRanking — Tianchi 원본의 복사본, Apache-2.0 표시, 원본 약관 미확인. 전체 약 116 GB 중 10–20K 제품 subset만 사용
- 저장 위치: 저장소 안 data/ (.gitignore의 /data/로 제외됨)

## 테스트
- 실행: python -m pytest tests/ml
- 결과 (20261023 날짜, MacBook MPS): 5 passed