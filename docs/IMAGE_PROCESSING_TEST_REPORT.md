# 이미지 전처리 검증 기록

2026-10-12 Windows/Python 3.12/Chrome, feat/service-image-processing 기준입니다. 실제 모델과 fake를 구분합니다.

| 검증 | 실행 결과 |
| --- | --- |
| pip check | 통과 |
| pytest service | 51개 통과, AnyIO deprecated alias 경고 1건 |
| TypeScript | 통과 |
| Vitest | 14개 통과 |
| Vite build | 통과 |
| Playwright Chrome | 최종 14개 통과(16.0초) |
| 실제 u2netp CPU smoke | 합성 그래픽 PNG에 mask/처리본 생성, corner alpha=0, RGB/프레임 동일 |
| 모델 없는 실제 subprocess | pytest에서 PHOTO_MODEL_UNAVAILABLE·원본 fallback 확인 |
| 시간 초과 | fake subprocess의 TimeoutExpired→kill/회수 검증; 첫 실제 30초 cold smoke도 timeout 관찰 |
| 손상 모델·빈/전체/잘못된 mask·작은 foreground 경고 | fixture 기반 단위/API 테스트 통과 |

실제 모델 smoke는 공식 4.36 MiB u2netp를 사용했습니다. 최초 30초 cold 실행은 timeout, 이후 120초 한도로 재실행은 약 19.12초에 성공했습니다. 기본 서비스 한도는 초기 로딩을 고려해 90초로 조정했습니다. 모든 실행 시간이 같은 것을 보장하지 않습니다.

브라우저 최종 실행은 PLAYWRIGHT_REQUIRE_PHOTO_MODEL=1로 실제 처리본을 요구했으며 real API→처리본 비교→원본/처리본 선택→사실 문자열 유지가 통과했습니다. 별도 테스트의 시간 초과 UI는 모의 응답입니다. CI는 모델을 다운로드하지 않고 원본 fallback 경로를 검증하므로 로컬 실제 모델 시험과 구분합니다.

초기 E2E는 기존 포트의 다른 작업 서버를 재사용해 실패했습니다. 새 UI 버튼 미발견, 세션 조회 404와 이전 안내 문구 assertion을 확인했습니다. 이번 작업이 만든 서버만 식별·정리하고 기존 사용자 5173/8000 서버는 유지했습니다. feature UI/API를 5174/8001로 분리하고 안내 assertion을 현재 구현 범위에 맞춰 수정한 뒤 재실행했습니다. 최종 Console/pageerror 검사는 통과했습니다. 실패 시 reporter의 screenshot/trace/video/log가 생성되며 결과 디렉터리는 다음 실행에서 갱신됩니다.

## 로컬 확인 위치

- UI: http://127.0.0.1:5174
- Swagger: http://127.0.0.1:8001/docs
- HTML report: artifacts/playwright/report/index.html (현재 feature worktree 기준)
- 처리 화면: artifacts/playwright/results/photos-real-API-process-or-6fd1f--compare-and-preserve-facts-chromium/photo-processing.png
- 별도 synthetic 원본/처리본/마스크: 주 작업 폴더 artifacts/image-processing/
- 모델: 주 작업 폴더 artifacts/models/rembg/u2netp.onnx, Git 제외

스크린샷 경로의 해시 부분은 reporter가 생성하므로 파일 목록에서 확인합니다. 실제 상품 사진·비밀·가중치·업로드·진단 artifact는 commit하지 않았습니다. 서버는 백그라운드 loopback으로 유지하며 PC 종료/재부팅 이후 유지되지 않습니다.

## 직접 확인

1. JPG/PNG 상품 사진과 가게명·상품명·가격·분위기를 입력하고 저장합니다.
2. 배경 제거 시작을 누르고 processing→completed 또는 failed를 확인합니다.
3. 성공 시 처리본의 투명 배경·윤곽·상품 누락을 원본과 비교합니다.
4. 원본 사용/처리본 사용을 눌러 선택 표시가 바뀌는지 확인합니다. 상태 다시 조회에도 선택이 유지되어야 합니다.
5. 모델 없는 다른 PC에서는 경고와 원본 선택을 확인합니다. 서비스는 모델을 자동 다운로드하지 않습니다.

## 한계

실제 모델 검증 입력은 합성 그래픽이며 실제 상품의 segmentation 품질/손상 여부를 인증하지 않습니다. 면적 휴리스틱은 모든 상품 손상을 판별하지 못하므로 수동 QA가 필요합니다. 재시작 metadata 유실, 단일 동시 작업, 모델 최초 로딩 비용이 있습니다. 광고 생성/분석/선호 순위/문구 편집/다운로드/사진 선택 후 네 광고 재렌더링은 이번 범위 밖입니다. B의 모델 코드나 평가를 실행·변경하지 않았습니다.
