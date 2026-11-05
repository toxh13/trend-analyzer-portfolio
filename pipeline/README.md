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

## 로컬 DB 준비

CLI는 V10 마이그레이션(`backend-spring/src/main/resources/db/migration/V10__create_v2_silver_tables.sql`)이 만드는 v2 테이블에 씁니다. 저장소의 `docker-compose.local.yml` Oracle은 호스트 포트를 열지 않고, 백엔드 `local` 프로필은 Flyway를 끄고 JPA로 스키마를 만들기 때문에 그 DB에는 V10 테이블이 없습니다. 로컬에서 CLI를 돌릴 때는 버려도 되는 Oracle 컨테이너를 따로 띄우고 V10만 적용합니다. V10은 V2~V9의 테이블을 참조하지 않으므로 V10 하나만 적용해도 됩니다.

아래 명령은 모두 저장소 루트의 PowerShell에서 실행합니다. 비밀번호는 입력받아 현재 셸의 환경 변수에만 두고 파일이나 명령 기록에 남기지 않습니다.

**1) 접속 정보.** 비밀번호는 영문자로 시작하는 영문·숫자로 정하세요. 포트 15210이 막혀 있으면 다른 번호로 바꾸고 2)의 포트도 같이 바꿉니다.

```powershell
$secure = Read-Host "로컬 Oracle 앱 계정 비밀번호" -AsSecureString
$env:ORACLE_PASSWORD = [System.Net.NetworkCredential]::new("", $secure).Password
$env:ORACLE_USER = "trend_pipeline"
$env:ORACLE_DSN = "localhost:15210/FREEPDB1"
```

**2) 컨테이너.** `gvenzl/oracle-free:23-slim`을 앱 계정과 함께 띄웁니다. `-e APP_USER_PASSWORD`처럼 값 없이 쓰면 docker가 현재 셸의 환경 변수 값을 넘깁니다. 관리자(SYS) 비밀번호는 무작위로 만들고 쓰지 않습니다.

```powershell
$env:APP_USER_PASSWORD = $env:ORACLE_PASSWORD
docker run -d --name trend-pipeline-oracle -p 127.0.0.1:15210:1521 -e ORACLE_RANDOM_PASSWORD=yes -e APP_USER=trend_pipeline -e APP_USER_PASSWORD gvenzl/oracle-free:23-slim
docker logs -f trend-pipeline-oracle  # "DATABASE IS READY TO USE!"가 나오면 Ctrl+C
```

**3) V10 적용.** 패키지의 `trend_pipeline.db` 연결(위 세 환경 변수)로 V10을 실행합니다. DDL이라 따로 커밋하지 않아도 됩니다. 여는 `@'`와 닫는 `'@`는 줄 맨 앞에 있어야 합니다.

```powershell
@'
from pathlib import Path
from trend_pipeline.db import connect

sql = Path("backend-spring/src/main/resources/db/migration/V10__create_v2_silver_tables.sql").read_text(encoding="utf-8")
with connect() as conn, conn.cursor() as cursor:
    for chunk in sql.split(";"):
        code = "\n".join(line for line in chunk.splitlines() if not line.strip().startswith("--")).strip()
        if code:
            cursor.execute(code)
print("V10 applied")
'@ | pipeline\.venv\Scripts\python -
```

**4) 정리.** 다 쓰면 컨테이너를 지웁니다. 데이터도 함께 사라집니다.

```powershell
docker rm -f trend-pipeline-oracle
```

## 실행

```text
python -m trend_pipeline run --interval-end <구간 끝> --run-type <종류> --raw-root <원본 폴더>
```

- `--interval-end`: 시간대가 있는 ISO-8601 시각으로, UTC로 바꿨을 때 정각이어야 합니다 (예: `2026-11-04T03:00:00Z`, `2026-11-04T12:00:00+09:00`). `+05:30`처럼 UTC 정각이 아닌 값은 거부합니다. `scheduled`·`manual`은 지금(UTC) − 1시간 ~ 지금 + 5분 사이의 구간만 받습니다. 받은 피드는 그 구간 이름으로 한 번만 저장되므로, 더 지난 구간을 받으면 지금 피드가 옛 구간 원본으로 굳기 때문입니다. 지난 구간은 `backfill`로 처리하고, `backfill`은 어느 시각이든 받습니다.
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

CLI는 피드 17개를 차례로 수집합니다. 응답이 느린 매체가 있으면 그 피드 하나가 재시도까지 최악 약 4분(시도 3번 × 연결 10초·읽기 30초 제한, 시도 사이 대기 최대 60초 × 2) 걸릴 수 있어 실행 전체가 길어질 수 있습니다. 같은 범위 검사를 피드마다 지금 시각으로 다시 하므로, 실행이 구간 끝에서 1시간 넘게 이어지면 남은 피드는 `too_late`로 실패합니다. 계획 2의 Airflow DAG는 피드별 작업으로 나눠 병렬로 수집합니다.

표준 출력에는 요약 한 줄만 나옵니다. 피드별 실패와 파싱 오류(원본은 저장됨)는 표준 오류에 `feed=<매체>/<피드> action=<동작> error=<내용>` 형식으로 한 줄씩 나옵니다.

```text
run_id=<uuid> outcome=SUCCESS new=1087 existing=0 inserted=1087 keywords=8093
```

- `new`: 이 구간에서 처음 본 기사 수(저장된 `first_seen_run_end`가 이 구간 끝인 기사), `existing`: 다른 구간에서 처음 본 기사 수. 실행 기록은 구간 기준으로 고정이라 같은 구간을 다시 처리해도 `new`·`existing`·`outcome`이 같습니다.
- `inserted`: 이번 실행에서 실제로 새로 넣은 기사 행 수. 같은 구간을 다시 처리하면 0입니다.
- `keywords`: 이번 실행에서 다시 쓴 키워드 행 수

종료 코드: `outcome`이 `FAILURE`이거나 예외가 나면 1, `SUCCESS`·`EMPTY`·`PARTIAL_FAILURE`는 0, 인자 오류는 2입니다.

## 원본 키 구조

원본은 한 번만 쓰고(write-once) 고치지 않습니다. 처리는 이 원본을 읽어 여러 번 할 수 있습니다. 이 CLI는 원본을 지우지 않으며, 보관 기간(30일)이 지난 원본·실버 데이터 정리는 계획 2의 보관 작업이 맡습니다.

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
