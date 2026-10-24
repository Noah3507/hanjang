# S3 사진 전처리 구현과 검증

이번 범위는 배경 제거·비율 유지 축소·비공개 처리본/마스크 저장·비교/사진 선택입니다. 광고 생성, 분석 CLIP/K-means, LLM, ranking, 재렌더링은 구현하지 않습니다. B의 ml/ 코드는 변경하지 않습니다.

## 승인된 additive API

모든 경로는 `/api/v1`, `X-Hanjang-Session` 필수, no-store입니다. 업로드 소유 세션만 접근할 수 있으며 미존재/다른 소유자는 404입니다. 기존 InputDraft 응답과 광고 재생성용 PATCH 초안은 유지합니다.

| API | 요청 | 응답·동작 |
| --- | --- | --- |
| POST /jobs/{job_id}/photo-processing | body 없음 | 202 PhotoResponse, 백그라운드 전처리 시작 |
| GET /jobs/{job_id}/photo-processing | 없음 | 200 PhotoResponse, polling/결과 조회 |
| PUT /jobs/{job_id}/photo-source | {photo_source: original 또는 processed} | 200 PhotoResponse, 사진 선택만 저장; 광고 생성/재렌더링 없음 |

```text
PhotoResponse = {
 job_id, operation: "photo_processing",
 status: pending | processing | completed | failed,
 original: PhotoAsset, processed: PhotoAsset | null,
 photo_source: original | processed, warnings: string[], expires_at
}
PhotoAsset = {asset_id, width, height, mime_type, sha256}
```

이는 사진 처리 operation의 상태이며 입력 draft의 pending이나 향후 광고 JobStatus와 구분합니다. 최초 GET은 pending을 반환하지만 처리하지 않습니다. POST는 processing을 반환하고 완료 상태를 GET으로 조회합니다. processing 중 같은 POST/사진 선택은 409 PHOTO_PROCESSING_BUSY입니다. 단일 서버는 한 사진 작업만 실행하며 다른 작업은 503 PHOTO_PROCESSING_BUSY로 재시도를 안내합니다. 완료 후 중복 POST는 기존 결과를 202로 반환하고 재처리하지 않습니다. failed는 명시적인 POST 재시도를 허용합니다. 처리본 없이 processed 선택은 409 PHOTO_NOT_READY입니다. 만료는 410, body 형식 오류는 공통 422입니다. POST body/PUT JSON은 기존 middleware에서 16KiB 이하로 제한합니다.

original과 processed는 기존 보호 GET /assets/{asset_id}로 조회합니다. 파일 경로·마스크 경로·session token을 응답에 넣지 않습니다. 처리 PNG와 내부 마스크는 원본과 다른 서버 생성 UUID 파일로 저장합니다. 원본 SHA/byte와 상품 사실은 변경하지 않습니다. 처리 중 만료되면 새 결과를 저장하지 않습니다. 원본·처리본·마스크는 업로드 시점의 같은 24시간 TTL을 공유하고 조회/선택/재시도로 연장하지 않습니다. 재시작 후 metadata 유실 한계는 유지하며 orphan 파일의 mtime도 업로드 시점으로 기록해 정리합니다.

## 처리와 품질 한계

rembg u2netp의 mask만 사용하고 RGB는 Pillow로 읽은 원본에서 취합니다. 기존 alpha를 mask와 결합합니다. EXIF 방향은 표시 해석에만 적용합니다. 상품 생성·색/채도/명도 보정·crop·upscale은 없습니다. 기본 최대 변 1600px로 비율 유지 축소하고 반올림 오차는 최대 1px입니다. 이는 설정 가능한 개발 기본값이며 발표 확정 수치가 아닙니다. resize는 픽셀을 바꾸므로 원본과 byte 동일성을 주장하지 않습니다. Pillow의 premultiplied-alpha Lanczos 축소를 사용하고 OpenCV는 mask foreground 검사를 수행합니다.

빈/전체 foreground·크기 불일치 mask는 거부합니다. foreground 면적 1% 미만/99% 초과는 PHOTO_MASK_REVIEW_REQUIRED 경고를 남기는 초기 휴리스틱입니다. 검증된 상품 손상 판정기가 아니며 수동 비교가 필요합니다. 경고가 있으면 처리본을 보존하되 원본을 기본 선택합니다. 경고 없는 성공은 처리본을 기본 선택하고 사용자가 언제든 원본을 선택할 수 있습니다.

PHOTO_MODEL_UNAVAILABLE/PHOTO_PROCESSING_FAILED/PHOTO_PROCESSING_TIMEOUT/PHOTO_MASK_INVALID는 failed와 원본 선택으로 표시합니다. 실제 추론은 별도 subprocess이며 기본 90초(설정 상한 120초) 초과 시 kill 후 회수합니다. 시간 제한에는 Python/모델 초기 로딩이 포함됩니다. 파일/저장 오류도 안전한 경고만 노출합니다. 실제 background 작업은 서비스 응답과 분리되지만 재시작/배포 시 복구를 보장하지 않습니다.

## 모델·환경

Python 3.12, rembg 2.0.77, Pillow 12.3.0, OpenCV headless 4.13.0.92, CPU onnxruntime를 설치·pip check로 확인했습니다. 전이 의존성도 backend/requirements.txt에 pin했습니다.

모델: u2netp.onnx, 4,574,861 bytes(4.36 MiB), [공식 rembg release](https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx). rembg가 지정한 MD5는 8e83ca70e441ab06c318d82300c84806이며 승인 후 다운로드 파일과 일치했습니다. SHA256은 309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8입니다. [원본 U2-Net 모델 저장소](https://github.com/xuebinqin/U-2-Net)의 모델 이용 조건을 상용 배포 전에 확인합니다.

모델은 Git 제외 artifacts/models/rembg/u2netp.onnx에 별도 제공하며 서비스가 자동 다운로드하지 않습니다. 모델 부재/삭제/환경 재설치 시 원본 fallback으로 동작합니다. 새 PC 설치는 README 서비스 환경 절차와 동일합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m pip check
# 선택: 명시적 공식 모델 다운로드 (자동 실행/CI 다운로드 없음)
.\.venv\Scripts\python.exe scripts/service_download_photo_model.py --download
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
npm.cmd --prefix frontend run dev
```

HANJANG_PHOTO_MODEL_PATH는 서버 전용 로컬 경로, HANJANG_PHOTO_TIMEOUT_SECONDS/HANJANG_PHOTO_MAX_SIDE는 서버 설정입니다. 프론트엔드에는 모델 경로나 키를 제공하지 않습니다. 브라우저에서 저장→배경 제거 시작→상태 조회→원본/처리본 비교→사진 사용 버튼을 확인합니다. 상품 누락/윤곽/색을 확인하고 이상하면 원본을 선택합니다.

현재 사용자 확인 환경은 기존 5173/8000 서버를 보존하기 위해 feature 작업 폴더에서 frontend 5174/backend 8001로 분리했습니다. 다른 PC 기본 포트는 위 명령의 5173/8000입니다. 서버는 loopback만 사용합니다.
