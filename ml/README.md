# ML 환경 (B: Preference Model & Evaluation)

## 버전
- Python 3.12.10
- torch 2.14.1, open_clip_torch 0.29.1, pytest 9.1.1 — 정확한 버전은 ml/requirements.txt
- CLIP: open_clip_torch 사용. 모델 크기는 미확정 (ViT-B/32, ViT-B/16, ViT-L/14 중 CPU 메모리·추론 시간을 재서 결정)

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
- - CreativeRanking: https://huggingface.co/datasets/Evan12/CreativeRanking — Tianchi 원본의 복사본으로 보이나 원본과 동일한 데이터인지 미확인. 라이선스는 복사본에 Apache-2.0으로 표시되어 있으나 원본 약관 미확인. 확인 전까지 사용 가능 여부는 확정하지 않음. 전체 약 116 GB 중 10–20K 제품 subset만 사용 예정
- 저장 위치: 저장소 안 data/ (.gitignore의 /data/로 제외됨)

## 테스트
- 실행: python -m pytest tests/ml
- 결과 (20261023 날짜, MacBook MPS): 5 passed