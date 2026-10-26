# 데이터 계약 (v2)

v2 파이프라인의 단계 사이 인터페이스입니다. 작업 A·B·C·D가 서로를 기다리지 않고 병렬로 개발할 수 있도록, 각 단계는 이 스키마만 보고 입력·출력을 맞춥니다. CI(`ci-v2.yml`)가 고정 데이터와 실제 산출물을 이 스키마로 검증합니다.

| 파일 | 생산자 | 소비자 |
| --- | --- | --- |
| `raw/article.schema.json` | 수집기 `batch_cli.py` (작업 A) | dbt staging (작업 B) |
| `raw/run.schema.json` | 수집기 (작업 A) | dbt staging, 운영 현황 (작업 B·D) |
| `site/*.schema.json` | `export_site.py` (작업 B) | React static 어댑터 (작업 C) |

스키마를 바꿔야 하면 해당 PR에서 스키마·고정 데이터·생산자·소비자를 함께 고치고, PR 설명에 "계약 변경"을 적습니다.

검증 예시:

```bash
pip install check-jsonschema
check-jsonschema --schemafile contracts/raw/article.schema.json fixtures/raw-root/raw/articles/**/*.jsonl  # JSONL은 줄 단위로 나눠서 검증
check-jsonschema --schemafile contracts/site/meta.schema.json fixtures/site/data/meta.json
```
