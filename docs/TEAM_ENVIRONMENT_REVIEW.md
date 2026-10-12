# 2인 GitHub 환경 점검 결과

2026-10-12 확인. 권한·Ruleset은 변경하지 않습니다. 기존 서비스 업로드 브랜치와 PR #8을 보존하고 문서 PR #9에서 안내만 추가합니다.

## CI와 실제 필수 검사 이름

PR #9의 커밋 `0f4db1a`에 대한 GitHub check-runs API에서 다음 이름과 success를 확인했습니다. 발행 앱은 `github-actions`(app id 15368)입니다. 향후 Ruleset에 workflow 제목이 아니라 아래 **check 이름**을 사용합니다.

| check 이름 | 실행 범위 | 결과 |
| --- | --- | --- |
| `backend` | 의존성 검사·pytest | 통과 |
| `frontend` | TypeScript·Vitest·build | 통과 |
| `repository-policy` | index 비밀/파일·PR 제목 | 통과 |
| `browser-e2e` | Playwright Chromium | 통과 |

[PR CI run 38244790509](https://github.com/Noah3507/hanjang/actions/runs/38244790509)에서 네 job 모두 통과했습니다. browser-e2e 로그는 **5 tests, 5 passed (4.9s)**입니다. main 기반 문서 PR이므로 기본 연결 화면 테스트이며 업로드 기능 테스트가 포함됐다는 뜻은 아닙니다. 실제 로컬 FastAPI 연결과 테스트 전용 장애 모의를 구분하는 기존 테스트입니다.

동일 커밋의 push run 38244784339와 PR 설명 갱신 run 38244812639도 네 check가 success였습니다. 별도 업로드 PR #8의 run 38243504018 역시 네 job 통과를 확인했습니다. 이 관찰 범위에서는 브라우저 실패가 없지만 장기적인 무결점 안정성을 보장하지 않습니다. Actions의 Node 런타임 전환·ubuntu-latest 이미지 변경 경고가 있으므로 향후 runner/의존성 변경 시 재검증합니다. ML 평가와 외부 LLM은 CI 대상이 아닙니다.

## 현재 보호와 향후 제안

`protect-main`(id 24925172)은 active, 기본 브랜치 main 대상입니다. PR 필수·삭제 금지·non-fast-forward 금지이며 bypass actor가 없습니다. 승인 리뷰는 0건, 필수 status check와 대화 해결 요구는 없습니다. 사용자가 현재 설정 유지로 결정했으므로 변경하지 않습니다.

향후 사용자가 승인할 때 다음을 제안합니다.

1. 위 네 check를 GitHub Actions 앱에서 발생한 필수 검사로 지정합니다. check 이름 변경 또는 job 생략/필터 도입 시 규칙도 함께 검토합니다.
2. 리뷰 대화 해결을 요구합니다.
3. B 초대 수락·상호 리뷰 가능 여부를 확인한 뒤 승인 리뷰 1건을 요구합니다.
4. 최신 main과의 통합을 추가로 강제할지는 검토 후 결정합니다. 현재는 병합 전 최신 main 통합·테스트를 팀 규칙으로 수행합니다.

## 리뷰 1건을 필수로 할 때의 2인 팀 제약

- PR 작성자는 자기 PR을 승인할 수 없습니다. B 수락 대기 중인 현재는 A PR의 승인자가 없어 병합이 막힐 수 있습니다.
- 상대방 휴가·부재·계정 접근 문제 시 유일한 승인자가 없어 대기해야 합니다. 긴급 변경도 임의 우회·직접 main push로 해결하지 않습니다.
- 상대방이 changes requested 리뷰를 남겼거나 대화가 미해결이면 수정·재리뷰가 필요합니다.
- stale 승인 무효화나 마지막 push 작성자 외 승인까지 함께 요구하면 두 사람이 같은 PR에 push하는 경우 재승인 순서를 조정해야 합니다. 두 추가 조건은 이번 제안에서 자동 적용하지 않습니다.
- 동일 check 이름을 다른 workflow가 사용하거나 필수 job이 조건부로 생략되면 병합 판단이 혼란스러울 수 있습니다. 현재 단일 workflow의 네 이름을 유지합니다.

권한 변경이나 제한 해제는 별도 사용자 승인 사항입니다. 서버 측 리뷰 요구가 0건이어도 프로젝트 규칙의 사용자 검토·명시적 병합 승인과 자동 merge 금지는 유지합니다.

## B에게 전달할 순서

초대 수락→본인 계정으로 Clone→AGENTS/CONTRIBUTING/ROLE_SPLIT/API_CONTRACT 읽기→[MODEL_DEVELOPMENT](MODEL_DEVELOPMENT.md)에 따라 `feat/ml-environment`에서 전용 환경과 독립 테스트 제안→작은 검증 단위 commit/push→main 대상 PR→A/B 리뷰와 사용자 병합 승인입니다. 현재 모델 폴더·의존성·학습 코드는 없으므로 별도로 준비해야 합니다.
