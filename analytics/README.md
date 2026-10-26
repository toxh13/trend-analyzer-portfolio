# analytics — 변환·품질·내보내기 (v2 작업 B)

`data` 브랜치의 원천 파일(`raw/articles/*.jsonl`, `raw/runs/*.json`)을 dbt-duckdb로 집계해 v1 Spring API와 같은 필드명의 정적 JSON(`contracts/site`)을 만듭니다. 설계는 [DESIGN 5·6절](../docs/v2/DESIGN.md), 정답은 [`fixtures/reference/v1_reference.py`](../fixtures/reference/v1_reference.py)입니다.

## 실행

```bash
pip install -r analytics/requirements.txt          # Python 3.12 기준
python analytics/build_site.py \
  --raw-root fixtures/raw-root --seeds-dir fixtures/seeds \
  --as-of 2026-10-24T12:00:00 --out /tmp/site
pytest analytics                                     # 약 2분 (동등성 18건 + 속성 150건 포함)
```

| 인자 | 의미 | 기본값 |
| --- | --- | --- |
| `--raw-root` | `raw/`를 포함한 디렉터리 | 필수 |
| `--out` | 정적 JSON 출력. 비어 있지 않으면 이전 산출물(`meta.json` 있음)일 때만 지우고 다시 씀 | 필수 |
| `--as-of` | 지표 기준 시각, 서울 로컬 `YYYY-MM-DDTHH:MM:SS` | 현재 시각 |
| `--seeds-dir` | `keyword_aliases.csv`, `blocked_keywords.csv` 위치 | `analytics/seeds` |
| `--code-version` | `meta.json`의 `codeVersion` | `$GITHUB_SHA` 또는 `local` |
| `--strict-freshness` | 마지막 성공 실행이 24시간을 넘으면 실패 | 끔 |
| `--work-dir` | dbt `target/`와 DuckDB 파일을 남길 곳 (디버깅) | 임시 디렉터리 |

처리 순서: `dbt build`(모델 + 품질 테스트) → `export_site.py`(marts → JSON) → `contracts/validate.py` 검사. 어느 단계든 실패하면 종료 코드 1이고, `--out`에 쓰기 전에 실패하면 이전 산출물은 그대로 남습니다.

dbt를 직접 돌릴 때는 `analytics/`에서 `RAW_DATA_DIR`, `SEEDS_DIR` 환경 변수와 `--vars '{as_of: "..."}'`를 줍니다.

```bash
cd analytics
RAW_DATA_DIR=../fixtures/raw-root SEEDS_DIR=../fixtures/seeds \
  dbt build --profiles-dir . --vars '{as_of: "2026-10-24T12:00:00"}'
```

## 모델 구조

```text
staging (view)                     intermediate (view)                 marts (table)
stg_article_lines ──► stg_articles ─┬─► int_article_keywords_stored ──► int_article_keywords_canonical
  (JSONL 모든 줄)      (URL 최초 행)  │     (v1 저장 규칙)                   (대표 키워드·차단 여부)
stg_article_keywords ◄──────────────┘                                         │
stg_keyword_aliases ──► int_keyword_alias_map ─────────────────────────────────┤
stg_blocked_keywords ──────────────────────────────────────────────────────────┤
stg_runs, stg_channel_runs ──► fct_ingest_runs ──► fct_pipeline_status          ▼
                                                    fct_trend_snapshot ──► fct_trend_merged ──► fct_trend_lists
                                                    dim_category, fct_dashboard_stats
                                                    dim_keyword ──► dim_keyword_search ──► dim_keyword_lookup
                                                                   fct_keyword_articles ──► fct_keyword_daily
```

| 모델 | v1 대응 | 내용 |
| --- | --- | --- |
| `stg_articles` | `articles` + unique 제약 | `sourceUrl`별 가장 먼저 수집된 행 (crawledAt, runId, 줄 번호) |
| `int_article_keywords_stored` | `CrawlingService.saveCrawledData` | 기사 안 대소문자 병합(첫 표기 유지), 차단 키워드 제외, weight = max(1, n) |
| `int_article_keywords_canonical` | `KeywordAliasCacheService.resolveKeyword` | 대표 키워드, 원본·대표 차단 여부 |
| `fct_trend_snapshot` | `TrendAnalysticService` | 대표 키워드 × 카테고리, 24시간 두 창의 고유 기사 수 |
| `fct_trend_merged` | `TrendService.mergeAliases` | 범위(전체·카테고리)별 병합, 카테고리 = mention 최대 → 이름순 |
| `fct_trend_lists` | `getTop20Trend`, `getTopMentionedTrends`, `getTopSurgingTrends` | top 20 / popular 50 / surging 50, 동점은 키워드순 |
| `fct_dashboard_stats` | `getDashboardStatsWithin24Hours` | 기사 수, 원본 키워드 수, 최대 증가·감소 |
| `dim_keyword` · `dim_keyword_search` | `resolveSearchKeywords` | 상세 파일 대상(30일 2건 이상 또는 목록 등장, 최대 3,000)과 검색 묶음 |
| `fct_keyword_articles` · `fct_keyword_daily` | `getArticlesContainingKeyword`, `buildKeywordHistory`, 근거 기사 | 최신 100건, 날짜별 5건, 30일 추이 |
| `fct_ingest_runs` · `fct_pipeline_status` | `crawl_batch_runs` | 운영 현황, 신선도 계산 입력 |

`export_site.py`는 계산하지 않고 행을 JSON으로 옮기기만 합니다(예외: 신선도 시간 반올림).

### 기준 구현과 같은 값을 내기 위해 한 일

- Python `str.strip()`·`split()`이 공백으로 보는 유니코드 문자를 SQL 정규식에 모두 나열 (`macros/keyword_rules.sql`).
- hotness 합계와 일별 가중치 합계를 **기준 구현과 같은 순서로** 더함(`ordered_fsum`). 순서가 다르면 2.8 과 2.8000000000000003 처럼 끝자리가 달라져 동점 정렬이 바뀝니다. 속성 테스트에서 일반 `sum()`으로 바꾸면 300건 중 2건이 실제로 어긋났습니다.
- 일별 `weightedScore`는 v1 `Math.round(x * 1000) / 1000`(half-up)과 같게 `floor(x * 1000 + 0.5) / 1000`.

## 품질 게이트 (DESIGN 5.2)

`dbt build`가 실패하면 `build_site.py`가 1로 끝나 배포하지 않습니다.

| 종류 | 테스트 | 등급 |
| --- | --- | --- |
| 스키마 | `stg_articles.source_url`·`article_id` unique·not null, `stg_runs.run_id` unique | error |
| 스키마 | `channel`(기사·채널 실행), `outcome`(실행·채널), `trigger` 허용값 | error |
| 스키마 | `publishedAt`·`crawledAt`·`startedAt`·`completedAt` 형식 (파싱 실패 → not null 실패) | error |
| 스키마 | 빈 카테고리 금지 `assert_article_category_not_blank` | error |
| 스키마 | alias 충돌 금지 `assert_alias_no_conflict` (정규화가 같은데 대표가 다르면 실패, `AI`·`A.I.` → 같은 대표는 허용) | error |
| 관계 | `stg_article_keywords.source_url` → `stg_articles`, `dim_keyword_lookup.keyword` → `dim_keyword` | error |
| 대사 | `assert_run_written_count_matches_lines`: run JSON `writtenCount` = 그 run의 JSONL 줄 수 | error |
| 대사 | `assert_run_reconciliation_equations`: `reconciliationOk=true`면 DESIGN 4절 대사식 성립 | error |
| 대사 | `assert_article_lines_have_run`: 기사 줄의 runId에 run JSON 존재 | warn |
| 계산식 | `assert_hotness_formula`: hotness = mention×0.4 + velocity×0.6 (1e-6), mention·previous ≥ 0, 두 창 모두 0인 행 없음 | error |
| 계산식 | `assert_trend_lists_consistent`: 순위 1부터 연속, score·changeValue 일치, surging은 velocity > 0 | error |
| 계산식 | `assert_keyword_daily_complete`: 키워드마다 30일, 오늘만 partial | error |
| 유일성 | 스냅샷(키워드, 카테고리), 목록(종류, 범위, 순위/키워드), 일별(키워드, 날짜) 등 | error |
| 신선도 | `assert_freshness_warn_6h`: 마지막 성공 실행 6시간 이내 | warn |
| 신선도 | `assert_freshness_fail_24h`: 24시간 이내 | warn, `--strict-freshness`면 error |
| 동등성 | `tests/test_parity.py` (아래) | pytest |

24시간 초과를 기본 경고로 둔 이유: 수집이 멈췄을 때 publish가 실패하면 직전 배포본의 `freshness: ok`가 계속 보입니다. 그래서 build는 성공시키고 `meta.freshness = "down"`을 배포해 운영 현황 화면과 배지가 정지를 알리게 했습니다. 빈 `raw-root`(첫 실행)도 같은 이유로 성공합니다.

카테고리 허용값은 두지 않았습니다. RSS 검색 피드와 포털 섹션에서 카테고리가 열린 집합으로 들어오기 때문에, 빈 값만 막습니다.

## v1 동등성

`tests/parity/<case>/`는 Java 테스트(`TrendAnalysticServiceTest`, `TrendServiceTest`, `TrendEvidenceServiceTest`)의 입력을 원천 기사로 옮긴 18개 케이스입니다. `build_cases.py`가 만들고, `expected.json`에 Java 단언과 출처(`*.java#메서드`)를 적었습니다. `test_parity.py`는 케이스마다 **Java 기대값 = 기준 구현 = dbt**를 확인합니다.

1. Java 단언을 기준 구현 결과에 적용
2. 같은 단언을 `build_site`(dbt build) 결과에 적용, 스냅샷 케이스는 `fct_trend_snapshot` 행도 비교
3. 기준 구현과 dbt의 정적 JSON 전체 비교

Java 테스트는 저장소를 mock 해서 계산식으로 만들 수 없는 값(예: hotness 95.5, previous가 음수가 되는 velocity)을 넣기도 합니다. 그런 케이스는 단언이 확인하는 성질(순위, 변화 방향, 합산)이 그대로 남도록 기사 수를 정하고 `expected.json`의 `adapted`에 이유를 적었습니다. 화면 검증 규칙(`days` 2~30, `limit` 1~5, 같은 대표 키워드 비교 거부의 400 응답)은 static 어댑터(작업 C) 몫이고, 여기서는 그 판단 근거인 `aliasToCanonical`만 확인합니다.

옮기지 않은 Java 테스트: `analyzeAndUpdateTrendsRecordsFailureAndRethrows`(DB 예외 전달, v2에는 해당 경로 없음), 배치 지표 수(`completeAfterTransaction`) 단언.

## 속성 테스트

`tests/test_property.py`는 무작위 원천 데이터 150건(`PROPERTY_CASES`로 조정)을 만들어 기준 구현과 dbt 결과(정적 JSON 전체)를 비교하고, 정상 데이터에서 error 등급 품질 테스트가 하나도 실패하지 않는지도 봅니다. alias 표기 변형·연쇄 alias, 차단 키워드, 대소문자 중복, 공백 키워드, 창 경계 정각, as_of 이후 기사, 다른 실행의 같은 URL, occurrence 16(반올림 중간값) 등을 일부러 섞습니다.

dbt build를 150번 돌리면 너무 느려서, 경로와 `as_of`를 자리표시자로 둔 채 `dbt compile`을 한 번 하고 케이스마다 컴파일된 SQL을 메모리 DuckDB에서 실행합니다(`tests/replay.py`). 실행되는 SQL은 dbt build와 같은 컴파일 결과입니다.
