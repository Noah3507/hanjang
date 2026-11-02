# Windows 발표용 배포 준비

## 선택과 경계

사용자 승인 범위는 **준비·로컬 검증까지**입니다. 외부 HTTPS URL 생성, Tunnel 실행, 실제 유료 OpenAI 호출은 이번 실행에서 하지 않습니다. 신규 VM·유료 서버는 사용하지 않습니다.

선택: Windows 노트북 → 단일 Uvicorn(빌드한 React + FastAPI, `127.0.0.1:8014`) → 별도 승인 후 Cloudflare Tunnel → 관람자. 모델은 기존 `.venv`, `.venv-analysis`, `.venv-rank`와 로컬 가중치를 재사용합니다. Vite는 개발용으로만 사용합니다. API/session/Candidate/ranking 계약과 B 구현은 변경하지 않습니다.

| 대안 | 판단 |
| --- | --- |
| 기존 Windows + 임시 Tunnel | 선택. 서버 임대비 0원, 기존 검증 모델 재사용. 노트북·네트워크 의존 |
| 단일 Linux VM | 미선택. 임대비 발생, 모델 환경 이전·용량 검증 필요 |
| Docker | 미선택. 현재 Windows에 Docker/WSL 없음. 별도 설치·이미지 다운로드·실행 미검증 |
| frontend/backend 별도 호스팅 | 미선택. CORS·세션·모델 서버·보안 경계 복잡성 증가 |

호스팅 예산은 월 0원입니다. 전기·기존 인터넷·장비 비용은 별도이며 무료 서비스의 향후 정책이나 가용성을 보장하지 않습니다. 모델 실행 peak는 테스트 보고를 참고하고, 발표 직전 메모리 여유·작업 관리자·절전을 확인합니다. 다중 worker/다중 서버는 메모리 저장소·비용 원장 구조상 사용하지 않습니다.

## Windows 실행

README 설치와 `npm.cmd --prefix frontend run build`를 먼저 완료합니다. 기존 환경은 재설치하지 않습니다. Git 제외 `artifacts/local-dev.json`을 **새로 필요한 경우에만** 만듭니다. 기존 파일은 덮어쓰지 않고 별도 이름과 `-ConfigFile`을 사용합니다.

```json
{
  "resource_root": "C:/path/to/hanjang",
  "runtime_root": "C:/path/to/hanjang/artifacts/presentation",
  "copy_provider": "mock",
  "copy_allow_paid": false,
  "ranking_mode": "model",
  "require_models": true
}
```

기본 모델: `artifacts/models/rembg/u2netp.onnx`, `artifacts/models/analysis/ViT-B-32.pt`, `artifacts/models/ranking/bt-logistic-v1/model.safetensors`와 같은 폴더의 B manifest/전처리 파일. ranking 설정은 **파일** 경로이며 loader에는 부모 디렉터리가 전달됩니다. JSON에서 `service_python`, `analysis_python`, `ranking_python`, `photo_model`, `clip_model`, `ranking_model_path`를 명시할 수 있습니다. 한글 CLIP 경로는 기존 검증된 ASCII junction을 재사용합니다. 모델을 복사하거나 다운로드하지 않습니다.

```powershell
# 비밀번호는 기록/JSON/인수에 넣지 않고 현재 프로세스에만 입력합니다.
$secure = Read-Host '발표 접근 비밀번호 (20자 이상, 고유 값)' -AsSecureString
$env:HANJANG_PRESENTATION_PASSWORD = [Net.NetworkCredential]::new('', $secure).Password
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/service_presentation.ps1 -CheckOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/service_presentation.ps1 -Port 8014
# 실행 터미널에서 Ctrl+C로 종료. 종료 후:
Remove-Item Env:HANJANG_PRESENTATION_PASSWORD
```

`ExecutionPolicy Bypass`는 위 프로세스에만 적용하며 시스템 정책은 변경하지 않습니다. 기본 로그인 이름은 `presenter`입니다. 브라우저에서 `http://127.0.0.1:8014`를 열어 로그인합니다. 기존 `.env`는 읽기만 하며 wrapper는 모델 경로·Mock 설정 등을 자식 프로세스 환경에 지정하고 종료 후 복원합니다. 사용자 서버나 이미 사용 중인 포트를 종료하지 않습니다.

Linux의 모델 없는 CI 발표 smoke는 `HANJANG_RANKING_MODE=mock`, `HANJANG_RELEASE_REQUIRE_MODELS=false`, `HANJANG_PRESENTATION_PASSWORD`를 설정한 뒤 `.venv/bin/python scripts/service_serve.py`로 실행합니다. 실제 모델 포함 Linux는 미검증입니다.

## 보안·비용 경계

- 발표 origin 전체에 Basic 인증 적용. HTTPS는 외부 Tunnel 단계가 담당하며 LAN에 HTTP origin을 노출하지 않습니다. URL을 아는 것만으로 접근할 수 없습니다. 공유 비밀번호 방식이므로 개인별 감사·MFA를 제공하지 않으며 소규모 임시 시연에 한정합니다.
- 기본 전체 600요청/분, 쓰기 30요청/분, 인증 실패 20회/분 제한. **단일 프로세스 전체 공유 제한**이며 한 사람이 다른 사람을 지연시킬 수 있습니다. IP/전달 헤더를 신뢰하지 않습니다. 브라우저 polling도 전체 제한에 포함됩니다.
- 다른 Origin의 쓰기는 차단. 기존 `X-Hanjang-Session` 소유권·만료 보호 유지. Basic 인증은 Job 세션을 대신하지 않습니다. 접근 키·응답 본문·쿼리를 access log에 남기지 않습니다.
- 파일 저장소·모델·`.env`를 static mount하지 않습니다. `frontend/dist`만 제공합니다. CSP, nosniff, frame 차단, no-referrer 적용. 업로드 10MiB·24MP·이미지 형식 검증은 기존 API가 유지합니다.
- 카피는 기본 Mock/paid=false. 실제 호출은 server-only 키 + provider=openai + paid=true + 별도 사용자 승인이 모두 필요합니다. `VITE_*`/브라우저 번들에 키를 넣지 않습니다.
- 누적 원장은 기본 **resource_root/artifacts/copy-usage/ledger.json** 재사용. 별도 기존 원장이 있다면 `copy_budget_path`로 같은 파일을 명시하세요. 재시작·포트 변경·롤백을 이유로 원장을 새로 만들어 한도를 우회하지 않습니다. 기본 최대 6회·$0.10, 기존 요청 예약 상한 $0.013716, 앱 재시도 최대 1회·SDK 재시도 0회. 가격·토큰 가정 기반 로컬 guard이며 공급자의 최종 청구를 대체하지 않습니다. 계정 자체의 사용 제한도 함께 확인합니다.

유료 smoke 준비만 확인:

```powershell
.\.venv\Scripts\python.exe scripts/service_openai_smoke.py
```

위 명령은 계획만 출력합니다. 별도 승인 후에만 `--execute --approved-paid-call`을 추가하고 provider/paid/key를 명시합니다. 이 경로는 synthetic facts, 호출 최대 1회, 재시도 0회, 기존 원장을 사용하며 구조·네 전략·사실 검증과 usage만 출력합니다. 실제 카피·키·원문 응답은 로그에 출력하지 않습니다. Fake SDK 테스트는 실제 API 결과와 구분합니다.

## Cloudflare Tunnel: 설치·실행·종료 안내만

현재 설치하거나 실행하지 않았습니다. 설치 자체와 외부 공개를 구분하고, 발표 전에 공식 배포처와 버전을 확인합니다. Windows 업데이트는 수동 관리가 필요합니다. [공식 다운로드](https://developers.cloudflare.com/tunnel/downloads/), [Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

```powershell
# 향후 설치 승인/운영자 선택 후 실행할 명령 (이번 작업 미실행)
winget install --id Cloudflare.cloudflared -e
cloudflared --version
# 반드시 별도 외부 공개 승인 후, origin 인증/ready/E2E 확인 후에만:
cloudflared tunnel --url http://127.0.0.1:8014
```

Quick Tunnel은 임시 HTTPS 주소를 출력하며 프로세스 종료 시 중단되고 재시작 시 주소가 달라질 수 있습니다. 주소는 비밀번호가 아니며 별도로 전달합니다. DNS·계정 로그인·Windows 서비스·자동 시작은 설정하지 않습니다. 계정/도메인이 있는 named tunnel + Cloudflare Access는 별도 권한·정책 검토 대상입니다.

공개 후에만 승인된 URL에서 로그인·업로드 제한·모든 모델·Mock 카피·순위·편집·다운로드·모바일·401/429를 다시 검사합니다. 승인 후 read-only probe는 `service_deploy_smoke.py --url https://approved-origin --allow-remote`이며 환경변수의 Basic 인증을 사용합니다. 기본 명령은 localhost만 조회합니다.

종료: Tunnel 터미널 Ctrl+C → 외부 접속 차단 확인 → 발표 서버 Ctrl+C → 환경 비밀번호 제거. 사용자 다른 서버/브라우저/모델 캐시는 종료·삭제하지 않습니다. PC를 깨어 있게 유지하고 발표 중 AC 전원을 사용합니다. 외부 네트워크가 끊기면 localhost 시연으로 전환합니다.

## health·TTL·실패·롤백

`/health`는 기존 프로세스 응답, `/ready`는 저장소 쓰기·폰트·Node/Chromium·frontend·설정한 모델 파일·카피 gate의 **설정 준비 상태**입니다. 실제 모델 추론·계정 크레딧을 보증하지 않습니다. 30초 캐시, 정리 실패 시503이며 경로/키를 응답하지 않습니다. 발표 runner에서는 둘 다 인증 필요합니다.

업로드·파생 파일은 24시간 임시 보관/60초 sweep. 재시작 시 메모리 Job·세션은 유실됩니다. 전용 마커가 있는 24시간 지난 ranking snapshot만 정리하며 unmarked/unknown 파일·활성 추론은 보존합니다. 파일 잠금 실패는 경로 없는 경고·ready503 후 다음 sweep에서 재시도합니다. 정확한 초 단위 삭제 SLA가 아닙니다.

실패 시 모델 없는 Mock으로 조용히 전환하지 않습니다. ranking 실패 상태를 표시하고 편집·다운로드·진단을 계속 사용할 수 있습니다. 모델/환경을 복구하고 재시도합니다. 원본 사진 선택은 배경 제거 품질 저하의 대안입니다.

롤백은 먼저 결과 다운로드, Tunnel 중지, 자신이 시작한 서버 종료 후 검증된 이전 소스를 **별도 worktree**에서 빌드·실행합니다. 기존 branch/사용자 파일을 reset/clean하지 않습니다. 기존 가중치와 누적 원장을 재사용하고 Job 복구 불가를 안내합니다. 이전 build와 새 backend를 섞지 않습니다.
