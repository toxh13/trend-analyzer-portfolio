# 계획 1 — 파이프라인 핵심 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 언론사 RSS 17개를 수집해 원본 봉투로 저장하고, 원본에서 기사·키워드를 Oracle 실버에 멱등하게 적재하는 Python 패키지와 CLI를 만든다.

**Architecture:** 저장소 루트에 새 패키지 `pipeline/`(`trend_pipeline`)를 둔다. Airflow에 묶이지 않은 순수 함수(수집 `collect_feed`, 처리 `process_interval`)로 만들어 계획 2에서 DAG 작업으로 감싼다. 실버는 v1 테이블을 건드리지 않는 새 테이블(`news_articles`, `news_keywords` 등)에 쓰고, 백엔드 전환과 v1 테이블 삭제는 계획 3에서 한다.

**Tech Stack:** Python 3.11 · requests · kiwipiepy 0.24.1 · duckdb · python-oracledb 26.1.0 (thin) · PyYAML · pytest · testcontainers(Oracle) · Flyway SQL(백엔드 마이그레이션 폴더)

**Spec:** `D:\GitHub\프로젝트노트\TrendAnalyzer_v2\설계 문서.md` (볼트) → Task 0에서 저장소 `docs/design/2026-11-04-trend-analyzer-v2-design.md`로 복사

> **계획 완료 뒤 바뀐 것 (2026-11-05, 계획 2 전 수정 · 사용자 결정):** 아래 본문은 계획 당시 그대로 둔다. 이후 바뀐 점:
> ① 카테고리는 `news_articles.category` 대신 기사-카테고리 다대다 `news_article_categories`(본 섹션의 합집합, 처리 순서와 무관). "먼저 나온 피드가 이긴다"는 기사 행(제목 등)에만 남음
> ② 봉투 v2(`ENVELOPE_VERSION = 2`): 받은 본문 바이트(base64) + 그 sha256, 읽을 때 대조. 디코드는 처리 단계(`envelope.body_text`). v1도 읽음
> ③ 정기·수동 수집은 구간 끝이 지금 − 1시간 ~ 지금 + 5분일 때만(`collect_feed`가 실제 시계로 검사). 지난 구간은 백필로만
> ④ 조건부 요청 validator는 오류 없는 피드 행에서만 고름
> 이유: 볼트 `결정/06_처리와 적재.md` "계획 2 전 수정"

## Global Constraints

- 저장소: `D:\GitHub\trend-analyzer-portfolio`, 브랜치 `v2/p1-pipeline-core`, PR로 `main`에 합침
- Python 3.11 (기존 `crawling-python/Dockerfile`과 같음)
- 모든 시각은 timezone-aware UTC로 다루고 저장. KST 변환은 화면에서만
- 실행 이름표 = `data_interval_end`(UTC). `now()`로 기준을 정하지 않음
- 원본 키: `raw/dt=YYYY-MM-DD/source={yna|khan|donga}/feed={feed}/run=YYYYMMDDTHHMMSSZ.json` (콜론 없음)
- 실행 ID: `uuid5(NAMESPACE_URL, f"{dag_id}|{interval_end_iso}")`, `dag_id = "trend_pipeline_hourly"`
- 피드 17개(카테고리 6개, 카테고리마다 매체당 1개). 카테고리 문자열: `정치` `경제` `사회` `세계` `문화` `IT/과학`
- HTTP: 최대 3번 시도, 대기 2초 → 4초(±20% 무작위), `Retry-After` 최대 60초, 재시도 대상 = 연결 오류 · 408 · 429 · 500 · 502 · 503 · 504
- User-Agent: `TrendAnalyzerBot/2.0 (+https://github.com/toxh13/trend-analyzer-portfolio)`
- 봉투는 200 · 304만 저장. 실패는 실행 기록에만
- 키워드 입력 = 제목만. 품사 NNG · NNP · SL · SH, 2글자 이상, 기사당 집합(상한 없음)
- 비밀 값(DB 비밀번호 등)은 환경 변수로만. 저장소에 커밋 금지
- 코드 주석은 기존 저장소처럼 한국어, 커밋 메시지는 기존처럼 영어 Conventional(`feat:` `test:` `docs:`)
- 통합 테스트는 Docker 필요 (로컬 Docker Desktop 켜기). 이미지 `gvenzl/oracle-free:23-slim`

## Review Focus

1. **발행 시각이 없거나 형식이 다른 항목** → 그 항목만 `parse_failed`로 세고 제외, 피드 전체는 계속 (Task 5 테스트)
2. **같은 기사가 한 실행 안 두 섹션 피드에 나옴** → `feeds.yml` 순서상 먼저 나온 피드의 카테고리 하나로만 적재 (Task 10 테스트)
3. **304 응답** → 본문 없는 봉투 저장, 처리 단계는 새 기사 0건, 피드 결과는 정상 (Task 11 테스트)
4. **정리 후 제목이 비거나 머리말만 있음** (`"[속보]"`) → 키워드 0개, 기사는 저장 (Task 7 테스트)
5. **시간대 혼재** (`+0900` RFC 822 · ISO `+09:00` · `GMT`) → 모두 UTC aware로 변환 (Task 5 테스트)

## 계획에서 정한 것 (설계 문서와 다른 점 — 검토 필요)

1. **새 실버 테이블 이름 사용** (`news_articles` · `news_keywords`): 설계 §7-1은 `articles` 변경이었으나, 바로 바꾸면 v1 백엔드가 깨짐. 계획 3에서 백엔드를 옮기고 v1 테이블 삭제
2. **원본 검사는 업로드를 막지 않고 기록만**: 받은 그대로가 원본이라, 깨진 응답도 디버깅 증거로 저장. 검사 결과는 `pipeline_feed_runs`(Task 10)와 실행 상태(부분 실패)에 반영. 설계 4-1의 "검사 → 업로드" 순서는 유지
3. **DuckDB 검사 대상 = 파싱한 항목(JSONL)**: 봉투 본문이 XML이라 DuckDB가 바로 읽지 못함
4. **규칙 버전 해시 = 규칙 파일을 정규화한 JSON의 sha256 앞 8자리**: 줄바꿈·공백만 바뀌어도 버전이 바뀌는 것을 막음
5. **첫 규칙 버전의 불용어 = 빈 목록**: 불용어는 수집 뒤 측정으로 정함(값 7). 측정 전까지는 비워 둠

---

## File Structure

```text
pipeline/
  pyproject.toml                         패키지·의존성·pytest 마커(integration)
  src/trend_pipeline/
    __init__.py
    __main__.py                          CLI (Task 13)
    resources/feeds.yml                  피드 17개 (Task 1)
    resources/keyword_rules.yml          추출 규칙 (Task 8)
    feeds.py          FeedSpec, load_feeds                      (Task 1)
    keys.py           run_id, raw_key                           (Task 2)
    envelope.py       Envelope, build_envelope, 직렬화           (Task 3)
    http_fetch.py     RetryPolicy, FetchResult, fetch_feed      (Task 4)
    parse.py          FeedItem, parse_feed                      (Task 5)
    article_key.py    ArticleKey, article_key, display_link     (Task 6)
    text_clean.py     CleanTitle, clean_title, clean_summary    (Task 7)
    keywords.py       RuleSet, load_rules, extract_keywords     (Task 8)
    raw_store.py      RawStore, LocalRawStore                   (Task 9)
    quality.py        QualityReport, check_items (DuckDB)       (Task 9)
    db.py             connect                                   (Task 10)
    load.py           RunLoadInput, LoadStats, load_run         (Task 10)
    collect.py        collect_feed                              (Task 11)
    process.py        process_interval                          (Task 12)
  tests/
    fixtures/feeds/*.xml                 볼트 샘플 17개 복사
    unit/…                               Task별
    integration/conftest.py              Oracle 컨테이너 + 마이그레이션 적용
    integration/…
backend-spring/src/main/resources/db/migration/V10__create_v2_silver_tables.sql   (Task 10)
.github/workflows/pipeline-tests.yml     (Task 0, Task 10에서 통합 추가)
docs/design/2026-11-04-trend-analyzer-v2-design.md
docs/superpowers/plans/2026-11-04-p1-pipeline-core.md
```

---

### Task 0: 저장소 준비

**Files:**
- Create: `pipeline/pyproject.toml`, `pipeline/src/trend_pipeline/__init__.py`, `pipeline/tests/unit/test_smoke.py`
- Create: `docs/design/2026-11-04-trend-analyzer-v2-design.md`(볼트 설계 문서 복사), `docs/superpowers/plans/2026-11-04-p1-pipeline-core.md`(이 계획 복사)
- Create: `pipeline/tests/fixtures/feeds/`(`D:\GitHub\프로젝트노트\TrendAnalyzer_v2\샘플_피드_2026-11-04\*.xml` 17개 복사)
- Create: `.github/workflows/pipeline-tests.yml`

**Interfaces:**
- Produces: `pip install -e "pipeline[test]"`로 설치되는 `trend_pipeline` 패키지, pytest 마커 `integration`

- [x] **Step 1:** 사용자 확인 후 `main`에 태그 `v1-final` 생성, 브랜치 `v2/p1-pipeline-core` 생성
- [x] **Step 2:** `pyproject.toml` 작성 — `requires-python = ">=3.11,<3.12"`, 의존성 `requests==2.34.2` `kiwipiepy==0.24.1` `oracledb==26.1.0` `PyYAML` `duckdb`, extra `test` = `pytest` `testcontainers[oracle]`. 버전이 안 적힌 것은 작업 시점 최신 안정판으로 고정(`==`)
- [x] **Step 3:** `test_smoke.py`: `import trend_pipeline` 성공 테스트 작성 → `pytest pipeline/tests/unit -q` 통과 확인
- [x] **Step 4:** CI `pipeline-tests.yml`: push·PR에서 `pipeline/**` 변경 시 Python 3.11로 `pytest pipeline/tests/unit -q` 실행
- [x] **Step 5:** 커밋 `chore: scaffold v2 pipeline package and docs`

---

### Task 1: 피드 설정

**Files:**
- Create: `pipeline/src/trend_pipeline/resources/feeds.yml`, `pipeline/src/trend_pipeline/feeds.py`
- Test: `pipeline/tests/unit/test_feeds.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) FeedSpec(source: str, feed: str, category: str, url: str)`, `load_feeds(path: Path | None = None) -> list[FeedSpec]` (기본 = 패키지 리소스, 파일 순서 유지)

`feeds.yml` 값 (순서 그대로):
```text
yna:   politics  정치  https://www.yna.co.kr/rss/politics.xml
       economy   경제  https://www.yna.co.kr/rss/economy.xml
       society   사회  https://www.yna.co.kr/rss/society.xml
       international 세계 https://www.yna.co.kr/rss/international.xml
       culture   문화  https://www.yna.co.kr/rss/culture.xml
khan:  politic_news 정치 · economy_news 경제 · society_news 사회 · kh_world 세계 · culture_news 문화 · science_news IT/과학
       URL = https://www.khan.co.kr/rss/rssdata/{feed}.xml
donga: politics 정치 · economy 경제 · national 사회 · international 세계 · culture 문화 · science IT/과학
       URL = https://rss.donga.com/{feed}.xml
```

- [x] **Step 1: 실패하는 테스트**
```python
def test_loads_17_feeds_in_file_order():
    feeds = load_feeds()
    assert len(feeds) == 17
    assert feeds[0] == FeedSpec("yna", "politics", "정치", "https://www.yna.co.kr/rss/politics.xml")

def test_one_feed_per_source_and_category():
    feeds = load_feeds()
    assert len({(f.source, f.category) for f in feeds}) == 17
    assert {f.category for f in feeds} == {"정치", "경제", "사회", "세계", "문화", "IT/과학"}
    assert not [f for f in feeds if f.source == "yna" and f.category == "IT/과학"]

def test_rejects_duplicate_source_category(tmp_path):
    # 같은 (source, category) 두 줄 → ValueError
```
- [x] **Step 2:** `pytest pipeline/tests/unit/test_feeds.py -q` → 실패 확인
- [x] **Step 3:** `load_feeds` 구현 (YAML 읽기 → 검증: source ∈ {yna, khan, donga}, category ∈ 6개, (source, category) 중복 금지)
- [x] **Step 4:** 테스트 통과 확인
- [x] **Step 5:** 커밋 `feat: add feed configuration for 17 RSS feeds`

---

### Task 2: 실행 ID와 원본 키

**Files:**
- Create: `pipeline/src/trend_pipeline/keys.py`
- Test: `pipeline/tests/unit/test_keys.py`

**Interfaces:**
- Produces: `DAG_ID = "trend_pipeline_hourly"`, `run_id(interval_end: datetime, dag_id: str = DAG_ID) -> str`, `raw_key(interval_end: datetime, source: str, feed: str) -> str`, `run_prefix(interval_end: datetime) -> str`(= `raw/dt=…/` 아래 해당 실행 파일을 찾기 위한 날짜 접두어)

- [x] **Step 1: 실패하는 테스트**
```python
END = datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)

def test_raw_key_format():
    assert raw_key(END, "yna", "politics") == "raw/dt=2026-11-04/source=yna/feed=politics/run=20261104T030000Z.json"

def test_raw_key_converts_kst_to_utc():
    kst = datetime(2026, 11, 4, 12, 0, tzinfo=timezone(timedelta(hours=9)))
    assert raw_key(kst, "khan", "kh_world").endswith("run=20261104T030000Z.json")

def test_raw_key_rejects_naive_datetime():
    with pytest.raises(ValueError): raw_key(datetime(2026, 11, 4, 3), "yna", "politics")

def test_run_id_is_deterministic_and_differs_by_interval():
    assert run_id(END) == run_id(END)
    assert run_id(END) != run_id(END + timedelta(hours=1))
    assert ":" not in raw_key(END, "yna", "politics")
```
- [x] **Step 2:** 실패 확인 → **Step 3:** 구현(`uuid5(NAMESPACE_URL, f"{dag_id}|{interval_end_utc.isoformat()}")`) → **Step 4:** 통과 확인
- [x] **Step 5:** 커밋 `feat: add deterministic run id and raw key`

---

### Task 3: 봉투

**Files:**
- Create: `pipeline/src/trend_pipeline/envelope.py`
- Test: `pipeline/tests/unit/test_envelope.py`

**Interfaces:**
- Consumes: `FeedSpec`
- Produces:
  - `ENVELOPE_VERSION = 1`, `CRAWLER_VERSION`(패키지 버전 문자열)
  - `@dataclass(frozen=True) Envelope(envelope_version, source, feed, request_url, requested_at: datetime, crawler_version, status: int, etag: str | None, last_modified: str | None, content_type: str | None, body_sha256: str | None, body: str | None)`
  - `build_envelope(spec: FeedSpec, requested_at: datetime, status: int, headers: Mapping[str, str], body: str | None) -> Envelope`
  - `to_bytes(env: Envelope) -> bytes` (UTF-8 JSON, `sort_keys=True`, `ensure_ascii=False`), `from_bytes(data: bytes) -> Envelope`

- [x] **Step 1: 실패하는 테스트** — 200: `body_sha256 == sha256(body.encode()).hexdigest()`, `from_bytes(to_bytes(e)) == e` / 304: `body is None` 이고 `body_sha256 is None` / `status` 가 200·304가 아니면 `ValueError` / 같은 입력 → 같은 바이트
- [x] **Step 2~4:** 실패 확인 → 구현 → 통과 확인
- [x] **Step 5:** 커밋 `feat: add raw envelope model`

---

### Task 4: HTTP 수집 (조건부 요청 + 재시도)

**Files:**
- Create: `pipeline/src/trend_pipeline/http_fetch.py`
- Test: `pipeline/tests/unit/test_http_fetch.py`

**Interfaces:**
- Consumes: `FeedSpec`
- Produces:
  - `@dataclass(frozen=True) RetryPolicy(max_attempts=3, base_delay=2.0, jitter=0.2, max_retry_after=60.0, retry_statuses=frozenset({408, 429, 500, 502, 503, 504}))`
  - `@dataclass(frozen=True) FetchResult(status: int, headers: dict[str, str], body: str | None, requested_at: datetime, attempts: int)`
  - `class FetchError(Exception)` (마지막 상태·원인 보관)
  - `fetch_feed(spec: FeedSpec, *, etag: str | None, last_modified: str | None, session: requests.Session, policy: RetryPolicy = RetryPolicy(), sleep: Callable[[float], None] = time.sleep, clock: Callable[[], datetime]) -> FetchResult`
- 대기: 시도 n(1부터) 실패 뒤 `base_delay * 2**(n-1)`에 ±jitter. `Retry-After`(초) 있으면 그 값(최대 60)
- 요청 헤더: User-Agent(전역 제약), `If-None-Match`, `If-Modified-Since`
- 200·304 → 반환. 재시도 대상 아닌 4xx → 즉시 `FetchError`. 시도 소진 → `FetchError`

- [x] **Step 1: 실패하는 테스트** (가짜 세션 사용)
```python
def test_sends_conditional_headers_and_returns_304(): ...
def test_retries_503_then_succeeds_with_waits_2_then_4(): # sleep 호출 [≈2.0, ≈4.0] (±20%)
def test_honors_retry_after_capped_at_60(): # Retry-After: 120 → sleep(60)
def test_does_not_retry_404():  # 시도 1번, FetchError
def test_connection_error_is_retried_then_raises_after_3_attempts():
def test_sets_user_agent():
```
- [x] **Step 2~4:** 실패 확인 → 구현 → 통과 확인
- [x] **Step 5:** 커밋 `feat: add conditional RSS fetch with bounded retries`

---

### Task 5: RSS 파싱

**Files:**
- Create: `pipeline/src/trend_pipeline/parse.py`
- Test: `pipeline/tests/unit/test_parse.py`

**Interfaces:**
- Consumes: `Envelope`
- Produces:
  - `@dataclass(frozen=True) FeedItem(title: str, link: str, guid: str | None, summary: str, published_at: datetime)` (published_at = UTC aware)
  - `@dataclass(frozen=True) ParseResult(items: list[FeedItem], parse_failed: int)`
  - `parse_feed(env: Envelope) -> ParseResult` (본문 None이면 빈 결과)
- 요약 = `description`, 비어 있으면 `content:encoded`. HTML 태그 제거 + `html.unescape`
- 발행 시각 = `pubDate`(RFC 822) 또는 `dc:date`(ISO). 없거나 못 읽으면 그 항목 제외 + `parse_failed += 1`
- XML 자체가 깨지면 `ParseResult([], 0)`가 아니라 `FeedParseError` 발생 (Task 11이 피드 실패로 기록)

- [x] **Step 1: 실패하는 테스트** — 고정 샘플 사용
```python
@pytest.mark.parametrize("name,count", [("yna_politics.xml", 120), ("khan_politics.xml", 50), ("donga_politics.xml", 50)])
def test_parses_fixture_item_counts(name, count): ...
def test_timezones_normalized_to_utc():  # "Wed, 04 Nov 2026 13:11:05 +0900", "2026-11-04T13:11:05+09:00", "... GMT" → 같은 UTC 순간
def test_item_without_pubdate_is_counted_not_fatal():  # Review Focus 1
def test_html_in_description_is_stripped_and_unescaped():
def test_broken_xml_raises_feed_parse_error():
def test_304_envelope_returns_empty_result():
```
- 샘플 파일 이름은 Task 0 복사본 기준(`{source}_{섹션}.xml`). 건수는 그 파일 기준으로 맞춤
- [x] **Step 2~4:** 실패 확인 → 구현(`xml.etree.ElementTree`, 네임스페이스 `dc`·`content`) → 통과 확인
- [x] **Step 5:** 커밋 `feat: parse RSS items with UTC timestamps`

---

### Task 6: 기사 키와 표시 링크

**Files:**
- Create: `pipeline/src/trend_pipeline/article_key.py`
- Test: `pipeline/tests/unit/test_article_key.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) ArticleKey(source: str, source_article_id: str)`, `article_key(source: str, link: str, guid: str | None) -> ArticleKey`, `display_link(source: str, link: str, guid: str | None) -> str`
- 규칙: yna `/view/(AKR\d+)` · khan `/article/(\d+)` · donga `/article/all/\d{8}/(\d+)/` · 못 뽑으면 정규화 URL(소문자 호스트, `https`, 쿼리·`#` 제거, 끝 `/` 제거)
- 표시 링크: guid가 `http`로 시작하면 guid, 아니면 쿼리 뗀 link (끝 `/` 제거)

- [x] **Step 1: 실패하는 테스트**
```python
def test_yna(): assert article_key("yna", "https://www.yna.co.kr/view/AKR20261104055151504", None) == ArticleKey("yna", "AKR20261104055151504")
def test_khan_ignores_utm():
    link = "https://www.khan.co.kr/article/202611041132001/?utm_source=khan_rss&utm_medium=rss"
    assert article_key("khan", link, "https://www.khan.co.kr/article/202611041132001").source_article_id == "202611041132001"
def test_donga_same_article_with_suffix_1_and_2():
    a = article_key("donga", "https://www.donga.com/news/Politics/article/all/20261104/134963513/1", None)
    b = article_key("donga", "https://www.donga.com/news/Politics/article/all/20261104/134963513/2", None)
    assert a == b == ArticleKey("donga", "134963513")
def test_fallback_normalized_url(): ...
def test_display_link_prefers_guid_and_strips_utm(): ...
```
- [x] **Step 2~4:** 실패 확인 → 구현 → 통과 확인
- [x] **Step 5:** 커밋 `feat: derive stable article keys per publisher`

---

### Task 7: 텍스트 정리

**Files:**
- Create: `pipeline/src/trend_pipeline/text_clean.py`
- Test: `pipeline/tests/unit/test_text_clean.py`

**Interfaces:**
- Produces:
  - `FORMAT_TAGS = {"속보", "단독", "영상", "포토뉴스", "쇼츠", "특징주"}`, `NOTICE_TAGS = {"게시판", "부고", "인사"}`
  - `@dataclass(frozen=True) CleanTitle(text: str, excluded: bool, tags: tuple[str, ...])`
  - `clean_title(title: str) -> CleanTitle`
  - `clean_summary(summary: str) -> str`
- 제목 앞 `[...]`·`【...】` 머리말을 반복해서 읽음: 형식 태그 → 지움, 공지 태그 → `excluded=True`, 그 밖 → 괄호만 벗기고 내용 유지
- 요약: 앞의 `(지역=연합뉴스)`, `OOO 기자 =`/`OOO 특파원 =` 제거, 끝의 사진 출처(`연합뉴스`·`뉴스1`·`뉴시스`·`경향신문`·`동아일보`, 앞에 `/`·`ⓒ` 가능) 제거

- [x] **Step 1: 실패하는 테스트**
```python
def test_format_tag_removed(): assert clean_title("[속보]尹 선거법 2심 …").text == "尹 선거법 2심 …"
def test_notice_tag_excludes(): assert clean_title("[게시판] 행사 안내").excluded is True
def test_topic_tag_unwrapped(): assert clean_title("[美중간선거] '경합지' …").text.startswith("美중간선거 ")
def test_only_tag_left_gives_empty_text(): assert clean_title("[속보]").text == ""   # Review Focus 4
def test_yna_lead_removed():
    s = "(서울=연합뉴스) 박원희 기자 = 국내 최대 규모의 경쟁 독립영화제"
    assert clean_summary(s) == "국내 최대 규모의 경쟁 독립영화제"
def test_trailing_photo_credit_removed(): ...
```
- [x] **Step 2~4:** 실패 확인 → 구현 → 통과 확인
- [x] **Step 5:** 커밋 `feat: clean title tags and summary bylines`

---

### Task 8: 추출 규칙과 Kiwi 키워드

**Files:**
- Create: `pipeline/src/trend_pipeline/resources/keyword_rules.yml`, `pipeline/src/trend_pipeline/keywords.py`
- Test: `pipeline/tests/unit/test_keywords.py`

**Interfaces:**
- Consumes: `clean_title`
- Produces:
  - `@dataclass(frozen=True) RuleSet(input_field: str, analyzer: str, analyzer_version: str, pos_tags: tuple[str, ...], min_length: int, stopwords: frozenset[str], hanja_map: tuple[tuple[str, str], ...])`
  - `RuleSet.version -> str` (정규화 JSON sha256 앞 8자리), `RuleSet.to_json() -> str`, `RuleSet.from_json(s: str) -> RuleSet`
  - `load_rules(path: Path | None = None) -> RuleSet`
  - `extract_keywords(title: str, rules: RuleSet) -> frozenset[str]`

`keyword_rules.yml` 첫 버전 값:
```text
input_field: title · analyzer: kiwi · analyzer_version: 0.24.1
pos_tags: [NNG, NNP, SL, SH] · min_length: 2 · stopwords: []
hanja_map (이 순서, 긴 것 먼저):
  中企→중소기업 · 美→미국 · 中→중국 · 日→일본 · 北→북한 · 韓→한국
  英→영국 · 伊→이탈리아 · 與→여당 · 野→야당 · 靑→청와대
```
- 처리 순서: `clean_title` → 한자 사전 치환(앞뒤에 공백 넣어 치환) → Kiwi 토큰화 → 품사 필터 → 길이 ≥ 2 → 불용어 제외 → 집합
- `analyzer_version`이 설치된 kiwipiepy 버전과 다르면 `load_rules`가 `RuntimeError`
- Kiwi 인스턴스는 모듈에서 한 번만 생성

- [x] **Step 1: 실패하는 테스트**
```python
def test_hanja_abbreviations_expanded():
    kws = extract_keywords("美 관세 압박에 中企 수출 비상", load_rules())
    assert {"미국", "관세", "중소기업", "수출"} <= kws
    assert not kws & {"美", "中", "企", "中企"}
def test_surname_hanja_dropped(): assert "尹" not in extract_keywords("[속보]尹 선거법 2심", load_rules())
def test_foreign_word_kept(): assert "AI" in extract_keywords("AI 반도체 수출 증가", load_rules())
def test_notice_title_has_no_keywords(): assert extract_keywords("[부고] 홍길동씨 별세", load_rules()) == frozenset()
def test_version_ignores_yaml_formatting(tmp_path): # 같은 내용, 다른 들여쓰기 → 같은 version
def test_version_changes_when_stopword_added(): ...
def test_json_round_trip(): assert RuleSet.from_json(r.to_json()) == r
```
- [x] **Step 2~4:** 실패 확인 → 구현 → 통과 확인
- [x] **Step 5:** 커밋 `feat: add versioned keyword rules with Kiwi`

---

### Task 9: 원본 저장소와 DuckDB 검사

**Files:**
- Create: `pipeline/src/trend_pipeline/raw_store.py`, `pipeline/src/trend_pipeline/quality.py`
- Test: `pipeline/tests/unit/test_raw_store.py`, `pipeline/tests/unit/test_quality.py`

**Interfaces:**
- Produces:
  - `class RawStore(Protocol)`: `exists(key: str) -> bool`, `put_if_absent(key: str, data: bytes) -> bool`, `get(key: str) -> bytes`, `list_keys(prefix: str) -> list[str]`, `delete_prefix(prefix: str) -> int`
  - `LocalRawStore(root: Path)` — 임시 파일에 쓰고 `os.link`로 최종 경로에 연결(이미 있으면 `False`), 쓴 뒤 다시 읽어 sha256 대조, 불일치면 `RawIntegrityError`
  - `@dataclass(frozen=True) QualityReport(item_count: int, missing_required: int, duplicate_keys: int)`
  - `check_items(items: list[tuple[ArticleKey, FeedItem]]) -> QualityReport` — 임시 JSONL을 DuckDB `read_json`으로 읽어 SQL로 셈

- [x] **Step 1: 실패하는 테스트**
```python
def test_put_if_absent_only_first_wins(tmp_path):
    s = LocalRawStore(tmp_path); assert s.put_if_absent("raw/a.json", b"1") is True
    assert s.put_if_absent("raw/a.json", b"2") is False; assert s.get("raw/a.json") == b"1"
def test_concurrent_put_exactly_one_true(tmp_path):  # 스레드 8개 동시 → True 1개
def test_no_partial_file_visible(tmp_path):  # 쓰기 중 예외 → exists False
def test_list_and_delete_prefix(tmp_path): ...
def test_quality_counts_duplicates_and_missing(): ...
```
- [x] **Step 2~4:** 실패 확인 → 구현 → 통과 확인
- [x] **Step 5:** 커밋 `feat: add write-once local raw store and DuckDB checks`

---

### Task 10: 실버 테이블과 멱등 적재

**Files:**
- Create: `backend-spring/src/main/resources/db/migration/V10__create_v2_silver_tables.sql`
- Create: `pipeline/src/trend_pipeline/db.py`, `pipeline/src/trend_pipeline/load.py`
- Create: `pipeline/tests/integration/conftest.py`, `pipeline/tests/integration/test_load.py`
- Modify: `.github/workflows/pipeline-tests.yml` (통합 테스트 job 추가: `pytest -m integration`)

**Interfaces:**
- Consumes: `ArticleKey`, `FeedItem`, `CleanTitle`, `RuleSet`, `run_id`
- Produces:
  - `connect() -> oracledb.Connection` (환경 변수 `ORACLE_DSN` `ORACLE_USER` `ORACLE_PASSWORD`, thin 모드)
  - `@dataclass(frozen=True) LoadItem(feed: FeedSpec, key: ArticleKey, title: str, summary: str, link: str, published_at: datetime, title_excluded: bool)`
  - `@dataclass(frozen=True) FeedOutcome(feed: FeedSpec, status: int | None, etag: str | None, last_modified: str | None, raw_key: str | None, item_count: int, parse_failed: int, missing_required: int, duplicate_keys: int, error: str | None)`
  - `@dataclass(frozen=True) RunLoadInput(interval_end: datetime, run_type: str, items: list[LoadItem], feeds: list[FeedOutcome])`
  - `@dataclass(frozen=True) LoadStats(new_articles: int, existing_articles: int, excluded_notice: int, excluded_blocklist: int, keyword_rows: int, outcome: str)`
  - `load_run(conn, data: RunLoadInput, rule_sets: Mapping[str, RuleSet]) -> LoadStats`
  - `ensure_rule_version(conn, rules: RuleSet) -> str` (테이블이 비면 ACTIVE로, 아니면 없을 때 BUILDING으로 등록. 반환 = 상태)
  - `writable_rule_sets(conn) -> dict[str, RuleSet]` (ACTIVE + BUILDING, `rule_json`에서 복원)

마이그레이션 `V10` 테이블 (v1 테이블은 그대로):
```text
news_articles      id(시퀀스) · source · source_article_id · category · title(1000) · summary(CLOB)
                   · link(1000) · published_at(TIMESTAMP) · first_seen_run_end(TIMESTAMP)
                   UNIQUE(source, source_article_id)
news_keywords      article_id(FK) · keyword(255) · rule_version(8)  PK(article_id, keyword, rule_version)
keyword_rule_versions  rule_version(8) PK · rule_json(CLOB) · status CHECK(BUILDING·ACTIVE·RETIRED) · created_at
                   ACTIVE 1개만: 함수 기반 유니크 인덱스 (CASE WHEN status='ACTIVE' THEN 1 END)
pipeline_runs      run_id(36) PK · interval_end · run_type CHECK(scheduled·backfill·manual)
                   · outcome CHECK(SUCCESS·EMPTY·PARTIAL_FAILURE·FAILURE) · 건수 열 · started_at · completed_at
pipeline_feed_runs run_id(FK) · source · feed · http_status · etag · last_modified · raw_key
                   · item_count · new_articles · existing_articles · excluded_notice · excluded_blocklist · parse_failed
                   · missing_required · duplicate_keys (DuckDB 검사 결과) · error
                   UNIQUE(run_id, source, feed)
                   CHECK(item_count = new_articles + existing_articles + excluded_notice + excluded_blocklist)
                   (parse_failed는 item_count에 안 들어감: 파싱 단계에서 이미 빠짐)
article_blocklist  source · source_article_id PK · requested_at · reason · requester_type
```
- 이름이 v1 `crawl_batch_runs`와 겹치지 않도록 `pipeline_*` 사용 (v1 테이블은 계획 3에서 삭제)

`load_run` 규칙:
- 한 트랜잭션. 끝에 commit, 예외 시 rollback
- 한 실행 안 중복 기사: `feeds.yml` 순서상 먼저 나온 것만 (Review Focus 2)
- 공지 제목(`title_excluded`) → 적재 안 함, `excluded_notice` 셈 / 차단 목록 → 적재 안 함, `excluded_blocklist` 셈
- 기사: `MERGE … WHEN NOT MATCHED THEN INSERT` (`executemany`), `first_seen_run_end = interval_end`
- 키워드: 이번 실행 기사 id × 쓰기 가능 규칙 버전마다 `DELETE` 후 `INSERT`
- `ORA-00001`이면 전체 트랜잭션을 처음부터 최대 3번 다시 시도
- `pipeline_runs`·`pipeline_feed_runs`는 `MERGE`로 쓰기 (재실행 시 같은 행 갱신)
- outcome: 피드 전부 성공 → SUCCESS(새 기사 0이면 EMPTY) / 일부 실패 → PARTIAL_FAILURE / 전부 실패 → FAILURE

- [x] **Step 1:** `conftest.py`: `OracleDbContainer("gvenzl/oracle-free:23-slim")` 세션 범위로 띄우고, `backend-spring/src/main/resources/db/migration/V*.sql`을 버전 순으로 `;` 단위 실행 (이 폴더에는 PL/SQL 블록 없음 — 확인됨). 테스트마다 v2 테이블 비우기
- [x] **Step 2: 실패하는 통합 테스트** (`@pytest.mark.integration`)
```python
def test_same_run_twice_gives_same_rows(conn, sample_run):
    s1 = load_run(conn, sample_run, rules); rows1 = counts(conn)
    s2 = load_run(conn, sample_run, rules); assert counts(conn) == rows1
    assert s2.new_articles == 0 and s2.existing_articles == s1.new_articles
def test_concurrent_runs_no_duplicates_no_errors(dsn, sample_run):  # 스레드 2개, 각자 연결
def test_failure_mid_transaction_rolls_back_then_rerun_succeeds(conn, sample_run, monkeypatch):
    # 키워드 INSERT에서 예외 주입 → news_articles 0행 → 주입 해제 후 재실행 성공
def test_duplicate_check_sql_is_zero(conn, sample_run):
    # SELECT source, source_article_id FROM news_articles GROUP BY 1,2 HAVING COUNT(*)>1 → 0행
    # news_keywords도 (article_id, keyword, rule_version) 기준 0행
def test_blocklisted_article_never_loaded_even_on_rerun(conn, sample_run): ...
def test_same_article_in_two_feeds_keeps_first_feed_category(conn): ...   # Review Focus 2
def test_building_rule_version_also_written(conn, sample_run): ...
def test_feed_run_counts_reconcile(conn, sample_run): # CHECK 제약 위반 없이 기록
```
- [x] **Step 3:** Docker 켠 상태에서 `pytest pipeline/tests/integration -m integration -q` → 실패 확인
- [x] **Step 4:** 마이그레이션 + `db.py` + `load.py` 구현
- [x] **Step 5:** 통합 테스트 통과 확인, 단위 테스트 전체 통과 확인
- [x] **Step 6:** 커밋 `feat: add v2 silver tables and idempotent run loader`

---

### Task 11: 수집 작업 함수

**Files:**
- Create: `pipeline/src/trend_pipeline/collect.py`
- Test: `pipeline/tests/unit/test_collect.py`

**Interfaces:**
- Consumes: `FeedSpec`, `raw_key`, `fetch_feed`, `build_envelope`/`to_bytes`, `parse_feed`, `article_key`, `check_items`, `RawStore`
- Produces:
  - `@dataclass(frozen=True) CollectResult(feed: FeedSpec, raw_key: str | None, action: str, status: int | None, quality: QualityReport | None, error: str | None)` — `action` ∈ `"fetched"` `"skipped_exists"` `"skipped_backfill"` `"missing_in_backfill"` `"failed"`
  - `collect_feed(spec: FeedSpec, interval_end: datetime, run_type: str, store: RawStore, validators: tuple[str | None, str | None], fetch: Callable[..., FetchResult]) -> CollectResult`
- 순서: 백필 → 원본 있으면 `skipped_backfill`, 없으면 `missing_in_backfill`(요청 안 함) / 평소 → 원본 있으면 `skipped_exists` / 없으면 요청 → 200·304 봉투 → 파싱·검사(기록만) → `put_if_absent` / `FetchError` → `failed`(원본 없음)
- `validators` = 그 피드의 직전 성공 기록(ETag, Last-Modified) — 호출하는 쪽이 `pipeline_feed_runs`에서 넘김

- [x] **Step 1: 실패하는 테스트**
```python
def test_backfill_never_calls_fetch(): ...            # fetch 호출 0회
def test_existing_raw_skips_fetch(): ...
def test_304_saves_bodyless_envelope(): ...           # Review Focus 3
def test_fetch_error_saves_nothing(): ...
def test_broken_xml_is_still_saved_and_reported(): ... # 계획에서 정한 것 2
```
- [x] **Step 2~4:** 실패 확인 → 구현 → 통과 확인
- [x] **Step 5:** 커밋 `feat: add write-once feed collection step`

---

### Task 12: 처리 작업 함수

**Files:**
- Create: `pipeline/src/trend_pipeline/process.py`
- Test: `pipeline/tests/integration/test_process.py`

**Interfaces:**
- Consumes: `RawStore`, `from_bytes`, `parse_feed`, `clean_title`, `clean_summary`, `article_key`, `display_link`, `load_run`, `writable_rule_sets`, `ensure_rule_version`, `load_rules`, `load_feeds`
- Produces: `process_interval(interval_end: datetime, run_type: str, store: RawStore, conn, collect_results: list[CollectResult]) -> LoadStats`
- 이 구간의 원본 키를 `feeds.yml` 순서대로 읽음 → 304·누락은 기사 0 → `LoadItem`·`FeedOutcome` 만들기 → `load_run`
- 시작 시 `ensure_rule_version(conn, load_rules())`

- [x] **Step 1: 실패하는 통합 테스트** — 고정 샘플 17개로 `LocalRawStore`를 미리 채우고 `run_type="backfill"`로 처리
```python
def test_process_fixture_interval_loads_articles_and_keywords(conn, seeded_store): ...
def test_reprocessing_same_interval_is_idempotent(conn, seeded_store): ...
def test_304_only_interval_loads_zero_articles_and_outcome_is_empty(conn, store): ...
```
- [x] **Step 2~4:** 실패 확인 → 구현 → 통과 확인
- [x] **Step 5:** 커밋 `feat: process raw interval into silver`

---

### Task 13: CLI와 끝까지 실행

**Files:**
- Create: `pipeline/src/trend_pipeline/__main__.py`
- Test: `pipeline/tests/integration/test_cli.py`
- Modify: `pipeline/README.md`(새로 만들기: 실행 방법·환경 변수·테스트 방법)

**Interfaces:**
- Consumes: `load_feeds`, `collect_feed`, `process_interval`, `LocalRawStore`, `connect`
- Produces: `python -m trend_pipeline run --interval-end 2026-11-04T03:00:00Z --run-type scheduled|backfill|manual --raw-root PATH` → 피드별 수집(평소만) 후 처리, 요약 한 줄 출력 `run_id=… outcome=… new=… existing=… keywords=…`, 실패 시 종료 코드 1

- [x] **Step 1: 실패하는 통합 테스트** — 샘플로 채운 원본 폴더 + `--run-type backfill` → 종료 코드 0, 출력에 `outcome=SUCCESS`, 같은 명령 두 번 → 두 번째 `new=0`
- [x] **Step 2~4:** 실패 확인 → 구현(`argparse`) → 통과 확인
- [x] **Step 5:** 단위 + 통합 전체 실행 `pytest pipeline/tests -q` 통과 확인
- [x] **Step 6:** 실제 수집 1회 수동 확인: `--run-type manual`로 지금 구간 실행 → 원본 17개 생성·적재 확인 (네트워크 사용, 사용자 승인 뒤)
- [x] **Step 7:** 커밋 `feat: add pipeline CLI for local end-to-end runs`
- [ ] **Step 8:** 사용자 확인 후 푸시·PR 생성 (PR 설명에 결정 근거 링크)

---

## 이 계획이 끝나면

- 로컬에서 명령 한 줄로 수집 → 원본 → 실버 적재가 되고, 멱등성 통합 테스트(두 번·동시·중간 실패·중복 0)가 CI에서 통과
- 다음: 계획 2 (Airflow DAG 3개 + dbt 골드)
- 계획 2 전에 할 측정: Kiwi vs Okt 비교, 불용어 후보 추출 (이 패키지로 고정 샘플에 실행)
