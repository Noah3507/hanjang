# 모델 저장 경로와 데이터셋 후보 협의

2026-10-24 사용자 결정 반영. B 학습/평가 코드와 기존 artifact 파일은 수정·이동·삭제하지 않습니다. 데이터셋·모델을 다운로드하거나 학습하지 않았습니다.

## 후보 데이터셋: 확인한 사실과 확인하지 못한 권리

후보는 [Hugging Face Evan12/CreativeRanking](https://huggingface.co/datasets/Evan12/CreativeRanking)입니다. [공개 metadata API](https://huggingface.co/api/datasets/Evan12/CreativeRanking)에서 다음을 확인했습니다. 원본 파일은 다운로드하거나 비교하지 않았습니다.

| 구분 | 확인 결과 |
| --- | --- |
| 조회 시 revision | 16ad7beb2af81fb35b72b0d4797c688680e3bb05 |
| 공개 metadata | private=false, gated=false |
| card의 주장 | license: apache-2.0 |
| 목록에 있는 파일명 | README.md, images.zip, list.zip, test_data_list.txt 등 |
| 원본 복사본이라는 설명 | 사용자가 전달한 정보이며 독립 검증되지 않음 |
| 원본 동일성 | 미검증: 원본 출처·revision·파일 목록/개수·checksum·label/split 대조 필요 |
| 원본 라이선스·권리 관계 | 미검증: 원본 권리자의 이용 조건과 업로더 재배포 권한 확인 필요 |
| 학습·평가·상용 이용·재배포 권한 | 미확인: 공개 접근 및 card 표기만으로 허가됐다고 해석하지 않음 |

[고정 revision의 card](https://huggingface.co/datasets/Evan12/CreativeRanking/blob/16ad7beb2af81fb35b72b0d4797c688680e3bb05/README.md)는 license front matter 외 근거 설명이 없습니다. `apache-2.0`는 해당 업로더의 metadata 표기라는 사실만 기록하며 원본 광고 이미지·개인정보·제3자 권리까지 검증했다는 의미가 아닙니다. 후보를 승인된 학습 데이터로 표시하지 않습니다.

B는 다운로드/사용 전 원본 공식 출처와 이용 조건을 확인하고 근거 URL·조회일·revision·checksum·차이점·허용 범위를 기록해 공동 리뷰합니다. 모델/데이터 카드에는 미확인 항목을 그대로 남깁니다. CreativeRanking/TASTE 방향의 기존 계획은 유지하며 이 후보 선정만으로 데이터 접근·B1 완료가 되지 않습니다.

## 확정된 저장 정책

- 모든 모델 가중치·학습 산출물의 기본 root는 저장소의 **artifacts/models/**입니다. 예: ranking/v1 아래 model 파일·scaler/config·checkpoint·학습 log.
- backend/models/는 신규 artifact 저장 경로로 사용하지 않습니다. 기존 파일이 있으면 소유자 확인 후 별도 이관 작업으로 다루며 이번에는 이동·삭제하지 않습니다.
- 원본 데이터셋·추출 이미지·label 원본·캐시는 Git 제외 /data/ 또는 datasets/에 둡니다. ml/data/는 B 코드 영역이며 원본 저장소로 사용하지 않습니다.
- artifact 안의 manifest/model card 사본도 runtime 산출물로 Git 제외입니다. 리뷰용 비밀 없는 manifest/checksum·의존성·보고서 요약은 docs 등 추적 가능한 경로에 별도 기록합니다.
- .gitignore의 artifacts/, models/, weights/, checkpoints/, 원본 data/datasets와 모델 확장자 규칙을 유지합니다. Git 제외는 백업이 아니며 승인된 비공개 전달/백업 수단은 A/B가 별도 합의합니다.

## 백엔드 설정과 전달 절차

```dotenv
# 실제 .env는 각 PC에서 작성. 공개 예시에는 비밀을 넣지 않음.
RANKING_MODEL_PATH=artifacts/models/ranking/v1/model.onnx
```

이는 **모델 파일** 경로이고 확장자/형식의 최종 확정은 아닙니다. B가 실제 전달 형식을 합의한 뒤 해당 파일명으로 설정합니다. 정확한 환경변수 이름은 RANKING_MODEL_PATH이며 HANJANG_ 접두사를 붙이지 않습니다. 상대 경로는 실행 cwd와 관계없이 저장소 root 기준, 절대 경로도 허용합니다. 기본값은 None이며 빈 문자열도 None입니다. 설정 파싱 단계는 존재 여부를 강제하지 않고 파일을 load/download하지 않습니다. 기존 photo 전처리의 HANJANG_PHOTO_MODEL_PATH와 별도 역할입니다.

1. B는 합의한 모델/scaler/config·feature 및 preprocessing version·checksum·의존성·model card·smoke 절차를 준비합니다.
2. 승인된 파일을 각 PC의 artifacts/models/ranking/<version>/에 배치하고 checksum을 대조합니다. Git으로 파일을 공유하지 않습니다.
3. 각 PC의 실제 .env에 RANKING_MODEL_PATH를 지정합니다. 모델이 없으면 비워둡니다.
4. 향후 S8 adapter가 파일 부재·손상·불일치를 감지하면 네 후보 전체 mock fallback을 사용하는 기존 설계를 유지합니다. 모델을 자동 다운로드하거나 잘못된 파일을 임의 load하지 않습니다.

**현재 main에는 MockRanker/RealRanker와 광고 전체 흐름 구현이 없습니다.** 이번 변경은 선택적 환경 설정과 서비스 기동 검증입니다. 모델 없는 환경에서 기존 서비스 health가 동작함을 확인하며, MockRanker 실행 성공을 주장하지 않습니다. S5c/S6의 mock 구현과 S8 실제 연결은 별도 단계입니다.

## API 충돌·B에게 전달할 사항

기존 B 함수 초안은 load_model(artifact_dir: Path)이고 환경변수는 단일 파일을 가리키므로 경계 차이가 있습니다. HTTP와 B 함수 signature는 변경하지 않습니다. 향후 A adapter가 파일을 검증한 뒤 부모 bundle directory를 넘기는 방안은 **B 합의 전 제안**입니다. model 파일명 규칙·manifest 위치·scaler 탐색 방식과 package version을 먼저 합의해야 합니다. 같은 폴더의 임의 파일을 자동 선택하지 않습니다.

B의 PR #13(feat/ml-environment)은 별도로 유지하며 A가 그 브랜치나 ml/·scripts/ml_*·tests/ml/를 수정하지 않습니다. B에게 후보 데이터의 권리/동일성 증거, artifacts/models 정책, RANKING_MODEL_PATH 파일 의미, 미확정 loader 경계를 전달해 공동 리뷰해야 합니다.
