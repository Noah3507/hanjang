# Hanjang

AI 마케팅 광고 제작 웹서비스를 위한 공동 개발 저장소입니다.
현재 단계는 개발 환경 및 GitHub 초기 설정이며 서비스 기능은 아직 구현하지 않았습니다.

## 역할

- 개발자 A: 서비스, API, 프론트엔드 및 ML 통합
- 개발자 B: ML 모델, 데이터 및 평가

## 개발 환경

Git, Python, Node.js LTS 및 npm, GitHub CLI를 사용합니다.
Python 버전과 서비스 구조, 의존성 관리 방식은 ML 호환성을 확인한 뒤 함께 확정합니다.

```powershell
git --version
python --version
node --version
npm --version
gh --version
Copy-Item .env.example .env
```

`.env` 값은 각자 로컬에서 설정합니다. `.env.example`에는 변수명과 비밀이 아닌 예시만 기록합니다.

## 협업

기본 브랜치는 `main`입니다. 작업 브랜치에서 개발하고 Pull Request로 리뷰합니다.

```powershell
git switch main
git pull --ff-only
git switch -c chore/your-task
# 필요한 파일만 선택하여 stage합니다.
git add <file>
git diff --cached
git commit -m "chore: describe your change"
git push -u origin HEAD
```

main에는 PR과 승인 1건을 요구하고 force push 및 브랜치 삭제를 허용하지 않는 설정을 권장합니다.
CI가 만들어지면 실제 존재하는 검사만 필수 상태 검사로 등록합니다.
팀원 초대는 GitHub 저장소 Settings > Collaborators에서 진행합니다.

## 데이터와 비밀 관리

- 실제 `.env`, 비밀키, 클라우드 인증 파일을 커밋하지 않습니다.
- 데이터는 `data/` 또는 `datasets/`, 업로드는 `uploads/`, 모델 가중치는 `weights/` 또는 `checkpoints/`에 보관합니다.
- 대용량 파일은 접근 권한을 관리하는 외부 스토리지에 두고 비밀이 없는 메타데이터만 Git으로 관리합니다.
- `.gitignore`는 이미 추적 중인 파일이나 임의 이름의 모든 비밀을 자동으로 제거하지 않습니다. 커밋 전 `git status`와 `git diff --cached`를 반드시 확인합니다.
- 비밀이 유출되면 해당 키를 즉시 폐기·재발급합니다.

## 다음 단계

1. 팀원 B 초대와 main 보호 설정을 완료합니다.
2. Python/Node 버전, 서비스·ML API 계약, 폴더 구조를 합의합니다.
3. 의존성과 잠금 파일, 실행 방법, CI를 별도 PR에서 추가합니다.
