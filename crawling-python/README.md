# crawling-python

네이버·다음·Google News RSS에서 IT/과학·경제 기사를 수집하고, KoNLPy(Okt)로 키워드와 150자 요약을 만드는 수집기입니다. 같은 수집 로직을 두 가지 방식으로 실행합니다.

| 진입점 | 버전 | 결과를 보내는 곳 | 실행 방식 |
| --- | --- | --- | --- |
| `main.py` | v1 (중지됨) | Spring 백엔드 HTTP API | Flask 서비스 + 3시간 반복 스레드 |
| `batch_cli.py` | v2 | `contracts/raw` 형식 파일 (data 브랜치에 커밋) | 1회 실행 CLI (GitHub Actions) |

v2 전체 구조는 [설계 문서](../docs/v2/DESIGN.md) 4절, 파일 형식은 [`contracts/raw`](../contracts/raw)를 봅니다.

## v2 배치 실행 (`batch_cli.py`)

Python 3.12 기준으로 확인했습니다. KoNLPy가 JVM을 쓰므로 Java(JDK/JRE 11 이상, Actions에서는 21)가 필요합니다.

```bash
cd crawling-python
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-batch.txt

python batch_cli.py \
  --output-dir ../out \
  --seen-urls ../data/state/seen_urls.txt \
  --max-articles 50 \
  --trigger workflow_dispatch
```

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--output-dir` | (필수) | `raw/articles/dt=YYYY-MM-DD/<runId>.jsonl`, `raw/runs/dt=YYYY-MM-DD/<runId>.json`을 만들 디렉터리 |
| `--seen-urls` | 없음 | 이미 수집한 URL 목록(한 줄에 하나). 없으면 제외 단계를 생략합니다. 경로를 줬는데 파일이 없으면 `FAILURE` |
| `--max-articles` | `$MAX_NEWS_PER_BATCH` 또는 50 | 배치당 최대 기사 수 |
| `--trigger` | `local` | `schedule`, `workflow_dispatch`, `backfill`, `local` |
| `--code-version` | `$GITHUB_SHA` 또는 `local` | run JSON의 `codeVersion` |
| `--source-fixture` | 없음 | 네트워크 대신 고정 기사 JSON을 사용 (CI·오프라인 e2e) |

종료 코드는 `outcome`이 `FAILURE`일 때만 1입니다(`SUCCESS`·`PARTIAL_FAILURE`·`EMPTY`는 0). 표준 출력 마지막 줄은 run JSON 경로입니다. run JSON조차 쓰지 못하면 경로 대신 `event=crawl_run_file_failed ...`를 출력하고 1로 끝납니다.

### 처리 순서

v1 `main.run_job()`과 같은 순서이고, 3번만 v2에서 추가했습니다.

1. 채널(naver·daum·rss)을 각각 격리 실행 (`run_sources`)
2. 필수 필드 검증 (`find_invalid_article_reason`)
3. 배치 안 URL 중복 제거 → **seen URL 제외** → 채널×카테고리 순환 선택 (`select_articles_fairly(..., seen_urls=...)`)
4. 키워드·요약 (`preprocess_article`, v1 HTTP 경로와 같은 함수)
5. JSONL과 run JSON 쓰기

run JSON 수량은 아래 대사식을 만족해야 `reconciliationOk: true`입니다.

```text
crawlerOutputCount = validInput + validationRejectedCount
validInput         = duplicateUrlCount + previouslySeenCount + eligibleCount
eligibleCount      = selectedCount + droppedByLimitCount
selectedCount      = preprocessingFailedCount + writtenCount + writeFailedCount
```

같은 URL이 배치 안에서 두 번 나오고 seen 목록에도 있으면, 첫 번째는 `previouslySeen`, 두 번째는 `duplicateUrl`로 셉니다.

### outcome 판정

v1 `BatchRunSummary.outcome`에서 "백엔드 수신 건수"를 "파일에 쓴 건수"로 바꾼 규칙입니다.

| 조건 | outcome |
| --- | --- |
| 예외 발생 또는 대사식 불일치 | `FAILURE` |
| 선택 0건 + 실패 단위 있음 | `FAILURE` |
| 선택 0건 + 부분 실패 단위·검증 탈락 있음 | `PARTIAL_FAILURE` |
| 선택 0건 (모두 이미 본 기사인 경우 포함) | `EMPTY` |
| 선택했지만 한 건도 못 씀 | `FAILURE` |
| 실패·부분 실패 단위, 검증 탈락, 전처리·쓰기 실패 중 하나라도 있음 | `PARTIAL_FAILURE` |
| 그 외 | `SUCCESS` |

### 파일 규칙

- `dt`는 배치 **시작 시각의 서울 날짜**입니다. 기사 `publishedAt`은 서울 로컬 시각(오프셋 없음), `crawledAt`·`startedAt`·`completedAt`은 `Z`로 끝나는 UTC입니다.
- 쓸 기사가 0건이면 JSONL을 만들지 않고 run JSON만 남깁니다.
- 같은 폴더의 임시 파일(`.<이름>.*.tmp`)에 다 쓴 뒤 rename합니다. 중간에 죽어도 반쯤 쓴 파일이 `*.jsonl`·`*.json` 패턴에 잡히지 않습니다.
- 예외가 나면 그 시점까지 센 수량으로 `FAILURE` run JSON을 남깁니다. 이때 대사식이 맞지 않으면 `reconciliationOk: false`도 그대로 기록합니다.
- 기사 계약(`sourceUrl`이 `http(s)://`로 시작, 제목·URL 1000자 이하, `publishedAt` 형식)을 어기는 기사는 쓰지 않고 `preprocessingFailedCount`로 셉니다. `sourceUrl`은 앞뒤 공백을 제거해 씁니다.

### 고정 데이터로 실행 (`--source-fixture`)

클라우드 세션이나 CI처럼 뉴스 사이트에 접속할 수 없는 곳에서는 고정 기사로 같은 경로를 실행합니다.

```bash
python batch_cli.py --output-dir /tmp/out \
  --source-fixture tests/fixtures/source_fixture.json \
  --seen-urls tests/fixtures/seen_urls.txt
python ../contracts/validate.py --raw-root /tmp/out
```

예시 파일은 `fixtures/raw-root`의 R2와 같은 모양(daum 채널 실패 → `PARTIAL_FAILURE`)을 만듭니다. 위 명령의 결과는 `crawlerOutputCount 8, validationRejected 1, duplicateUrl 1, previouslySeen 1, written 5`입니다.

채널 값은 세 가지 형태를 받습니다.

```jsonc
{
  "naver": [ { "title": "...", "content": "...", "sourceUrl": "https://...", "source": "네이버 뉴스", "category": "IT/과학", "publishedAt": "2026-10-24T09:00:00" } ],
  "daum": { "units": [ { "category": "IT/과학", "outcome": "failure" }, { "category": "경제", "outcome": "failure" } ] },
  "rss": { "raise": "피드 접속 실패" }
}
```

- 배열: 카테고리마다 성공 단위 1개로 기록합니다. 빈 배열이면 빈 단위 1개입니다.
- `units`: 수집 단위 결과(`success`·`partial_failure`·`empty`·`failure`, `articles`, `sourceInvalid`)를 그대로 지정합니다.
- `raise`: 크롤러가 예외를 던져 `run_sources`의 격리 경로로 실패 처리됩니다.

키워드 추출은 고정 데이터 실행에서도 실제 KoNLPy를 씁니다. 테스트는 `batch_cli.main(argv, keyword_extractor=stub)`으로 stub 추출기를 넘겨 Java 없이 돕니다(`nlp/keyword_extractor.py`는 KoNLPy를 첫 추출 때 import합니다).

## 테스트

```bash
cd crawling-python
pip install -r requirements-dev.txt   # 배치 의존성 + Flask(v1 테스트) + jsonschema + pytest
pytest -q
```

테스트는 실제 네트워크에 접속하지 않습니다. `test_batch_cli.py`는 `--source-fixture` 산출물을 `contracts/validate.py`로 검사합니다.

## v1 서비스 (`main.py`, 중지됨)

`requirements.txt`(전체 의존성)와 `Dockerfile`로 실행하던 Flask 서비스입니다. 3시간마다 수집해 Spring 백엔드로 보내고, 키워드 병합 추천 내부 API(`/internal/keyword-merge-suggestions/recommend`)를 제공했습니다. v2 작업에서도 이 동작은 바꾸지 않았습니다.
