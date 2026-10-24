# 계약 예제

- candidates.json: 입력 순서의 네 후보 wrapper
- ranking.mock.json, ranking.fallback.json: 서비스 rank 순 응답, 확률 없음
- ranking.model.json: 합성 점수/확률로 작성한 서비스 응답 (실제 모델 결과 아님)
- rank-output.model.json: B 응답, candidate 입력 순서 유지
- *.schema.json: tests/integration/contract_models.py가 export한 구조 명세

버전·확정 범위·pairwise 의미와 테스트는 [RANKING_CONTRACT_V1_1](../../../docs/RANKING_CONTRACT_V1_1.md)을 따릅니다. 이 JSON의 asset ID는 실제 서버에 존재하지 않으며 URL을 호출하지 않습니다. path·token·개인정보·실제 사용자 자료가 없습니다.
