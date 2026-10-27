# S4 상품 사진 분석 검증 (2026-10-28, Windows)

기준 main c607167에서 feat/service-image-analysis 작업. B ml/·scripts/ml_*·tests/ml 및 서비스/B 환경은 수정하지 않습니다. 기능 범위와 실행은 [IMAGE_ANALYSIS](IMAGE_ANALYSIS.md), 새 계약은 [API_CONTRACT](API_CONTRACT.md)를 따릅니다.

## 자동 검증

| 범위 | 실행 결과 |
| --- | --- |
| 서비스/계약 전체 pytest | 112 passed, AnyIO deprecation1건 |
| 이 중 분석 신규 테스트 | 17개: facts/hash 보존·만료·인증·캐시/409/503·stale context·색상/투명/깨진 이미지·NaN·worker 장애/timeout/ID오류/재사용/종료·실제 checksum 거부 |
| frontend Vitest | 18 passed (분석 신규4개 포함) |
| TypeScript·Vite build | 통과 |
| Chrome Playwright | 17 passed (27.7초), 기존14개+분석3개 |
| A 분석·서비스 pip check | 통과 |

Python3.12.10, Windows AMD64, torch2.14.1 CPU/OpenCLIP3.3.0/Pillow13.0.0은 A 전용 .venv-analysis에 설치했습니다. 서비스는 Pillow12.3.0/rembg를 유지하며 B .venv-ml도 변경하지 않습니다. 실행 전후 두 환경의 pip freeze를 로컬 artifacts/image-analysis/에서 비교합니다.

명령:

```powershell
.\.venv\Scripts\python.exe -m pytest
npm.cmd --prefix frontend run test:ci
npm.cmd --prefix frontend run build
# 실제 모델이 준비된 로컬 환경만:
$env:PLAYWRIGHT_CHANNEL='chrome'
$env:PLAYWRIGHT_FRONTEND_PORT='5179'
$env:PLAYWRIGHT_BACKEND_PORT='8008'
$env:PLAYWRIGHT_REQUIRE_ANALYSIS_MODEL='1'
$env:PLAYWRIGHT_REQUIRE_PHOTO_MODEL='1'
$env:PLAYWRIGHT_ANALYSIS_SAMPLE='C:/path/to/hanjang/artifacts/image-analysis/coffee.png'
npm.cmd --prefix frontend run test:e2e
```

Playwright 실제 API: 커피 사진 업로드·draft facts·원본 사진 분석·12개 CLIP 단서·palette·재요청·가격/상품명 보존, 기존 사진 전처리/선택도 검증했습니다. 409 conflict와 CLIP unavailable UI는 명시적인 모의 응답입니다. 단위/API CLIP 장애 경로는 fake executor, 프로토콜 시험은 통제된 실제 subprocess이며 가중치를 로딩하지 않습니다. 실제 checksum 거부도 별도 실행했습니다. 실제 사전학습 추론은 아래와 구분합니다. CI는 공식 가중치/사진을 다운로드하지 않고 합성 fixture/offline fallback을 사용합니다.

## 실제 OpenAI 사전학습 추론

모델은 공식 OpenAI URL에서 353,976,522 bytes를 내려받아 SHA256 `40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af` 일치 확인 후 Git 제외 artifacts/models/analysis/에 저장했습니다. HF/Transformers offline으로 실행했고 추론 중 다운로드는 없습니다.

실제 사진: 공개 scikit-image v0.19.3 coffee.png (600×400 RGB).
출처: https://raw.githubusercontent.com/scikit-image/scikit-image/v0.19.3/skimage/data/coffee.png
이 사진과 결과·계측 스크립트/로그는 artifacts/image-analysis/에만 저장하며 Git fixture에 추가하지 않습니다. segmentation/분류 품질 인증이나 학습 이용 권리 확인으로 해석하지 않습니다.

동일 worker에 이 사진을 두 번 전달한 측정:

| 항목 | 관측값 |
| --- | --- |
| 첫 요청 전체 | 7.094초 |
| 첫 모델 준비(프로세스 내 import/checksum/model/text 준비 포함) | 6.943초 |
| 반복 요청 전체 | 0.0556초 |
| 반복 모델 준비 | 0초, 동일 실제 worker PID 재사용 |
| worker peak working set | 1,290.45 MiB |

위 값은 text 후보12개를 포함하는 상품 사진 **한 장** 분석이며 B의 4개 광고 ranking 벤치마크와 다릅니다. CPU 4 torch threads, QuickGELU/OpenAI fp32. 실제 연산 지연·로드·원본 API context는 결과 JSON의 내부 계측에 기록하며 내부 PID/메모리는 API에 노출하지 않습니다. Windows venv launcher의 3.37MiB를 실제 worker 메모리로 잘못 읽은 초기 진단은 폐기하고 worker 내부 ctypes 측정으로 바로잡았습니다. worker 피크는 서비스·rembg·OS 전체 RAM 예산이 아닙니다.

참고 cue: drink 0.2541, food 0.2251, dessert 0.2217, nonfood 0.2377 cosine similarity. 후보 간 차이가 작으며 **음식의 정답/확률/구매 선호 점수가 아닙니다**. 모든12개 결과와 palette는 artifacts/image-analysis/real-clip.json에 기록했습니다. 후보 정확도·일반화 성능은 평가하지 않았습니다.

## 발견·해결한 문제와 재실행

1. 초기 실제 로딩: TorchScript archive를 weights_only=True로 읽어 실패했습니다. 버전/보안 기본값을 전역 변경하지 않고 검증된 로컬 파일에 OpenCLIP OpenAI 전용 loader를 적용해 실제 추론을 재검증했습니다. 초기 load-diagnostic.log/real 검증 로그는 Git 제외입니다.
2. 초기 테스트용 mask가 전체 전경이라 기존 rembg 품질 검사에서 처리본이 거부됐습니다. 정상 전경/배경을 가진 fake mask로 시험 조건을 수정했고 기존 전처리 기준은 변경하지 않았습니다. 테스트 파일의 누락 import도 수정·재실행했습니다.
3. 최초 브라우저 분석 자체는 성공했지만 favicon 404 Console 오류가 있었습니다. 빈 data favicon을 추가하고 원래 실패 screenshot/trace/log를 artifacts/image-analysis/initial-browser-failure에 보관했습니다.
4. 개발 reload 도중 서버 RAM 세션이 유실돼 재실행이401/대기 timeout으로 실패했습니다. 이 MVP의 재시작 유실 한계와 일치하며, artifacts/image-analysis/reload-browser-failure에 보관했습니다. 8008/5179의 리로드 없는 확인 서버에서 전체17개를 재실행해 통과했습니다.

## 직접 확인과 한계

확인 서버: http://127.0.0.1:5179, API http://127.0.0.1:8008/docs. 프로세스를 유지하지만 재부팅 이후를 보장하지 않습니다. 기본 개발 서버 주소5173/8000과 구분합니다.

테스트 보고서: artifacts/playwright/report/index.html, results.json, results/의 실제/모의·모바일 screenshot과 browser.log. 로그/사진/모델은 Git 제외이며 민감 정보 검토 없이 외부 공유하지 않습니다.

선택 사진 분석 → 단서/색상 확인 → 사진 선택 변경 시 이전 결과 경고 → 재분석 → 입력 사실/원본 유지 확인 순서로 검토합니다. 모델이 없는 환경은 CLIP unavailable+palette가 정상입니다. completed 부분 결과는 같은 asset에 캐시되므로 모델 준비 후 새 업로드로 검토합니다.

남은 한계: 후보·색 추출 파라미터는 품질 보증 기준이 아니라 v1 구현 설정입니다. 투명 경계 alpha threshold, 표본 palette 오차, 원본 배경색 포함, 모델 준비 메모리/지연, 단일 서버·한 작업 제한·24h 삭제·RAM 유실, Linux 실제모델/배포 환경 미검증이 있습니다. LLM 카피·광고 렌더링·B preference 통합은 구현하지 않았습니다.
