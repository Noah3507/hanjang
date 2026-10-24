# 공통 합성 광고 fixture

emotional/price/visual/brand.png는 Pillow로 생성한 1080×1350 불투명 RGB PNG입니다. 사용자 사진·외부 광고·학습 데이터·모델 출력이 아닙니다. 테스트용 단색 geometry와 ASCII 사실 필드를 포함하며 실제 전략별 레이아웃 구현이나 renderer QA를 대신하지 않습니다.

원본 상품 사진·대용량 데이터·가중치를 이 폴더에 넣지 않습니다. 투명 상품 cutout은 최종 광고 fixture에 섞지 않습니다. 합성 fixture만 계약 PR에서 A/B 공동 리뷰하며 B 학습 입력/label/split을 임의로 바꾸지 않습니다.

재생성·검증 명령은 [계약 문서](../../../docs/RANKING_CONTRACT_V1_1.md)를 따릅니다. 파일 경계/주변 가격 텍스트 보존을 검사하는 padding fixture 확장은 실제 전처리 구현 단계에서 별도 테스트로 추가합니다. 이번 계약 테스트는 실제 CLIP preprocessing을 실행하지 않습니다.
