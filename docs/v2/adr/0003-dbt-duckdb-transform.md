# ADR-0003. 집계는 dbt-duckdb로 옮긴다

- 상태: 제안 (2026-10-24)
- 결정: v1 Spring `TrendAnalysticService`·`TrendService`의 계산을 dbt 모델로 옮기고, DuckDB에서 실행한다.

## 배경

v1은 집계 로직이 Java 서비스 코드와 Oracle 쿼리에 나뉘어 있었다. 계산식이 화면 API마다 흩어져 있어(예: alias 병합은 조회 시점, 차단 키워드는 저장·집계 시점) 전체 규칙을 한눈에 보기 어려웠다.

## 검토한 대안

| 대안 | 장점 | 단점 |
| --- | --- | --- |
| pandas 스크립트 | 의존성 적음 | 테스트·문서·계보를 직접 만들어야 함 |
| Spark | 대용량 표준 | 하루 400건에는 과함 (v1 결정과 같음) |
| **dbt + DuckDB** | SQL 모델·테스트·문서·계보가 표준 구조, 파일을 바로 읽음, 서버 불필요 | dbt 학습 비용, 일부 로직(정렬 동점 등)은 SQL로 표현이 길어짐 |

## 결과

- 모든 지표 규칙이 `analytics/models`에 모이고, 품질 규칙이 dbt 테스트로 명시된다.
- v1과 같은 결과인지는 Python 기준 구현(`fixtures/reference/v1_reference.py`)과 Java 테스트 케이스로 확인한다.
- `dbt docs`로 계보(lineage) 문서를 만들어 Pages에 함께 올릴 수 있다.
