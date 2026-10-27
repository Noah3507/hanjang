# S4 상품 사진 분석 (사용자 안내의 6단계)

2026-10-28 승인 범위: 상품 사진 CLIP zero-shot cue·K-means 대표색·비공개 Job 연동·UI. B 광고 preference·학습·LLM·광고 렌더링은 포함하지 않습니다. 새 API와 A 전용 실행 환경·공식 가중치 다운로드는 사용자 승인 사항입니다.

## 데이터 흐름과 보존

React 사진 선택 → POST photo-analysis(expected_asset_id) → 현재 선택 사진 ID 일치 검사 → source asset snapshot → 제한된 RGB K-means → A worker의 CLIP → GET polling → 단서·색상 UI입니다. 기존 API 요청·응답은 변경하지 않습니다. 선택이 없으면 원본을 사용하고, 처리본 선택 시 그 asset을 사용합니다.

원본 bytes·사용자 facts·사진 선택을 분석에서 변경하지 않습니다. 재인코딩/흰색 합성/padding은 모델 입력 메모리에서만 수행합니다. 후속 LLM은 `AnalysisStore.context()`를 통해 현재 사진의 completed 결과만 소비해야 하며, 사용자 facts와 별도 visual_hints로 취급합니다. 해당 LLM 기능 자체는 미구현입니다.

결과는 upload Record에 asset별로 보관하며 동일 사진의 processing/completed 요청은 재사용합니다. 사진을 변경하면 이전 결과를 보존하고 is_current=false로 반환합니다. 같은 사진으로 돌아가면 해당 캐시를 재사용합니다. failed는 재시도 가능하며 completed 부분 결과도 캐시됩니다. 모델 준비 후 이미 캐시된 unavailable 결과를 다시 평가하려면 새 업로드가 필요합니다. 모델은 서버 사용 전에 준비하는 것을 권장합니다.

업로드 생성 기준 24시간 TTL을 늘리지 않습니다. 만료 중 추론이 끝나도 결과를 게시하지 않습니다. 기존 소유권·401/404/410·no-store 정책을 따릅니다. 결과는 메모리이며 서버 재시작/배포 시 유실됩니다. cache는 사진·버전별 영속 저장을 보장하지 않으며 worker를 외부 서버에 공개하지 않습니다.

## CLIP 단서의 의미

- A 전용 OpenCLIP 3.3.0, ViT-B-32/OpenAI, CPU fp32, QuickGELU.
- 공식 OpenAI TorchScript archive를 checksum 검사 후 전용 `load_openai_model(local_path)`로 로딩합니다. 일반 weights_only checkpoint loader를 사용하지 않습니다.
- EXIF 방향 적용 → 투명 영역 흰색 합성 → 비율을 유지하는 정사각 흰 padding → 224 bicubic/모델 mean·std. 상품 자체의 색 보정·저장 이미지 변형은 없습니다.
- 고정 후보 product-cues-v1: category(food/drink/dessert/nonfood), appearance(round/layered/glossy/textured), impression(bright/dark/calm/vivid). 영문 prompt와 한글 표시명은 A의 analysis_prompts.py에서 관리합니다.
- 정규화 image/text embedding의 cosine similarity [-1,1], softmax나 확률 변환 없음. 모든 12개 후보를 반환하며 순서는 고정입니다. 후보 간 절대 신뢰도·그룹 간 보정·정답을 보장하지 않습니다.
- 음식명·재료·맛·원산지·효능·상품명/가격 사실을 추론으로 확정하지 않습니다. 분위기 단서도 사용자 선택 mood를 바꾸지 않습니다.

## K-means

RGB 공간, seed=0, 최대4096 유효 pixel 무작위 표본, k=min(5,고유색 수), 거리 기반 초기화, 최대30회 갱신입니다. alpha<128 pixel은 제외하며 >=128 pixel은 원래 RGB로 동일 가중합니다. 색별 비중은 유효 **표본 픽셀** 수 기준으로 합1입니다. 반투명 경계의 alpha 가중 면적이나 전체 원본의 정확한 면적 측정값이 아닙니다.

중심값을 반올림해 RGB/대문자 HEX로 표시하고 같은 RGB는 병합합니다. 비중 내림차순·RGB 순서로 정렬합니다. 원본 선택 시 배경색이 포함될 수 있고, 유효 pixel이 없으면 빈 palette/CLIP unavailable/failed로 처리합니다. 추출색을 상품에 적용하거나 색을 보정하지 않습니다.

## 실행 환경과 공식 모델 준비 (Windows)

서비스 .venv와 B .venv-ml에는 설치하지 않습니다. A 분석 환경은 backend/requirements-analysis.in과 별도 고정 lock으로 관리하며 B 모듈을 import하지 않습니다. 모델 로딩 전 Python 패키지만 설치되며, 가중치는 아래 별도 opt-in 명령으로 준비합니다.

```powershell
py -3.12 -m venv .venv-analysis
.\.venv-analysis\Scripts\python.exe -m pip install -r backend/requirements-analysis.txt
.\.venv-analysis\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/service_download_analysis_model.py --download
# 기존 README대로 서비스 .venv uvicorn / frontend npm run dev 실행
```

공식 출처: https://openaipublic.azureedge.net/clip/models/40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af/ViT-B-32.pt

2026-10-28 확인 크기353,976,522 bytes(약337.6MiB), SHA256 `40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af`. 저장 위치 artifacts/models/analysis/ViT-B-32.pt, Git 제외. 공개 scikit-image 커피 테스트 사진은 검증용 artifacts에만 저장하며 fixture로 커밋하지 않습니다. 출처는 테스트 보고서에 기록합니다.

런타임 다운로드 금지, HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE=1, 존재·checksum 검증된 로컬 artifact만 로딩합니다. 기존 파일이 다르면 덮어쓰지 않습니다. 인터넷이 없는 새 PC는 승인된 경로로 동일 검증 파일을 별도 배치합니다. A 분석 worker는 모델/text embedding을 한 번 로딩하고 여러 사진에 재사용합니다. 단일 프로세스/서버 worker를 가정하며 uvicorn multi-worker 배포는 이 MVP의 동시성 보장 범위가 아닙니다.

설정(서버 전용): HANJANG_ANALYSIS_PYTHON, HANJANG_ANALYSIS_MODEL_PATH, HANJANG_ANALYSIS_TIMEOUT_SECONDS(기본120/최대300), HANJANG_ANALYSIS_IDLE_SECONDS(기본300). 기본 Python 경로는 현재 repo .venv-analysis입니다. 다른 Python 환경을 지정하면 해당 환경 호환성 검증이 필요합니다.

동시에 한 작업만 실행, 다른 작업은503으로 재시도 안내합니다. worker JSON-lines는 request ID를 검증하고 FastAPI와 subprocess로 격리합니다. timeout/응답 오류는 worker를 종료·재생성합니다. Windows venv launcher의 자식도 taskkill /T로 종료합니다. 유휴300초/서버 정상 종료 시 worker를 정리합니다. 모델은 사용자 사진 TTL과 별도인 재사용 프로그램 자산이며 자동 삭제 대상이 아닙니다. 학습/사용자 사진 embedding을 공용 영속 캐시하지 않습니다.

CLIP 환경/가중치 부재·실패·timeout은 unavailable+warning으로 처리하고 K-means는 계속 사용할 수 있습니다. 양쪽 모두 사용 불가이면 failed+error이며 상품 입력과 사진은 유지됩니다. 단순 health 응답은 CLIP readiness를 보장하지 않습니다.

## 운영 한계와 직접 확인

Windows 실제 커피 사진 첫 요청/반복 요청, PID 재사용·메모리는 [검증 보고서](IMAGE_ANALYSIS_TEST_REPORT.md)를 따릅니다. 피크는 worker 프로세스 사용량이며 서비스·rembg·OS 전체 RAM 요구량이 아닙니다. cold load·동시 요청·다른 PC CPU·배포 지연은 별도 측정해야 합니다. 후보 문구 정확도를 데이터셋으로 평가한 결과가 아닙니다.

1. 상품 사진·사용자 사실을 저장합니다.
2. 원본 또는 배경 제거 처리본을 선택하고 '선택 사진 분석'을 누릅니다.
3. processing→completed, CLIP 시각 단서와 색상·표본 비중을 확인합니다.
4. 사진을 바꾸면 이전 결과 경고와 재분석 필요 안내를 확인합니다.
5. 원래 상품명·가격·사진이 유지되는지 확인합니다. 모델이 없을 때는 CLIP unavailable과 palette만 표시하는 것이 정상입니다.

모델·실제 사진 없이 실행하는 CI는 fake CLIP/프로토콜·offline fallback과 합성 이미지로 검증합니다. 실제 추론과 구분하며 이 작업에서 LLM 카피나 광고 생성은 구현하지 않습니다.
