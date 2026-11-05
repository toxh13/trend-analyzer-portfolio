# trend-pipeline

Trend Analyzer v2의 데이터 파이프라인입니다. RSS 피드 17개를 한 시간 구간 단위로 **수집 → 원본 봉투(raw envelope) 저장 → Oracle silver 테이블 적재**까지 처리합니다. 같은 구간을 몇 번 다시 실행해도 결과 행이 같습니다(멱등). 설계 배경은 [v2 설계 문서](../docs/design/2026-11-04-trend-analyzer-v2-design.md)를 보세요.

## 설치

Python 3.11이 필요합니다.

```powershell
py -3.11 -m venv pipeline/.venv
pipeline\.venv\Scripts\python -m pip install -e "pipeline[test]"
```

## 환경 변수

Oracle 접속 정보는 환경 변수로만 받습니다. 값을 파일·코드·저장소에 쓰지 마세요.

| 이름 | 설명 |
| --- | --- |
| `ORACLE_DSN` | 접속 주소 (`host:port/service`) |
| `ORACLE_USER` | DB 사용자 |
| `ORACLE_PASSWORD` | DB 비밀번호 |

## 실행

```text
python -m trend_pipeline run --interval-end <구간 끝> --run-type <종류> --raw-root <원본 폴더>
```

- `--interval-end`: 시간대가 있는 ISO-8601 시각으로, UTC로 바꿨을 때 정각이어야 합니다 (예: `2026-11-04T03:00:00Z`, `2026-11-04T12:00:00+09:00`). `+05:30`처럼 UTC 정각이 아닌 값은 거부합니다. `scheduled`·`manual`은 지금(UTC) + 5분보다 늦은 구간을 받지 않습니다. `backfill`은 어느 시각이든 받습니다.
- `--run-type`: `scheduled`(정기), `manual`(수동), `backfill`(재처리)
- `--raw-root`: 원본 봉투를 저장·읽는 폴더

```powershell
# 정기 실행: 원본이 없는 피드만 요청해 저장하고 적재
python -m trend_pipeline run --interval-end 2026-11-04T03:00:00Z --run-type scheduled --raw-root .\raw

# 수동 실행
python -m trend_pipeline run --interval-end 2026-11-04T03:00:00Z --run-type manual --raw-root .\raw

# 백필: 네트워크 요청 없이 저장된 원본만 다시 처리
python -m trend_pipeline run --interval-end 2026-11-04T03:00:00Z --run-type backfill --raw-root .\raw
```

표준 출력에는 요약 한 줄만 나옵니다. 피드별 실패는 표준 오류에 한 줄씩 나옵니다.

```text
run_id=<uuid> outcome=SUCCESS new=1087 existing=0 inserted=1087 keywords=8093
```

- `new`: 이 구간에서 처음 본 기사 수(저장된 `first_seen_run_end`가 이 구간 끝인 기사), `existing`: 다른 구간에서 처음 본 기사 수. 실행 기록은 구간 기준으로 고정이라 같은 구간을 다시 처리해도 `new`·`existing`·`outcome`이 같습니다.
- `inserted`: 이번 실행에서 실제로 새로 넣은 기사 행 수. 같은 구간을 다시 처리하면 0입니다.
- `keywords`: 이번 실행에서 다시 쓴 키워드 행 수

종료 코드: `outcome`이 `FAILURE`이거나 예외가 나면 1, `SUCCESS`·`EMPTY`·`PARTIAL_FAILURE`는 0, 인자 오류는 2입니다.

## 원본 키 구조

원본은 한 번만 쓰고(write-once) 지우지 않습니다. 처리는 이 원본을 읽어 여러 번 할 수 있습니다.

```text
raw/dt=YYYY-MM-DD/source={yna|khan|donga}/feed={feed}/run=YYYYMMDDTHHMMSSZ.json
```

시각은 모두 UTC이고 키에 콜론이 없습니다.

## 테스트

```powershell
# 단위 테스트 (Docker 불필요)
pipeline\.venv\Scripts\python -m pytest pipeline/tests/unit -q

# 통합 테스트 (Docker 필요. gvenzl/oracle-free:23-slim 컨테이너를 자동으로 띄웁니다)
pipeline\.venv\Scripts\python -m pytest pipeline/tests/integration -q

# 전체
pipeline\.venv\Scripts\python -m pytest pipeline/tests -q
```

통합 테스트는 Docker Desktop이 꺼져 있으면 건너뛰지 않고 실패합니다.
