"""한 실행(run)의 기사·키워드·실행 기록을 Oracle 실버 테이블에 한 트랜잭션으로 적재한다.

같은 실행을 두 번, 동시에, 또는 중간 실패 뒤 다시 돌려도 남는 행이 같다(멱등).
- 기사: 키 (source, source_article_id)로 MERGE … WHEN NOT MATCHED THEN INSERT. 이미 있는 기사는 건드리지 않는다
- 키워드: (기사, 규칙 버전)마다 지우고 다시 쓴다. 항상 저장된(처음 본) 제목에서 뽑으므로
  구간을 어떤 순서로 처리·재처리해도 같은 기사의 키워드는 같다
- 실행 기록: 결정적 run_id로 MERGE. 다시 실행하면 같은 행을 갱신한다. 건수는 구간 기준으로 고정이다:
  저장된 first_seen_run_end가 이 구간 끝인 기사가 새 기사라서, 같은 입력을 다시 돌리면 같은 건수·결과가 나온다
  (run_type은 처음 적재한 값을 지키고, started_at·completed_at만 가장 최근 처리를 따른다)
- 동시 실행끼리 같은 키를 넣다가 ORA-00001이 나면 트랜잭션 전체를 처음부터 다시 한다
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

import oracledb

from trend_pipeline.article_key import ArticleKey
from trend_pipeline.feeds import FeedSpec
from trend_pipeline.keys import run_id
from trend_pipeline.keywords import RuleSet, extract_keywords

RUN_TYPES = frozenset({"scheduled", "backfill", "manual"})
WRITABLE_STATUSES = ("ACTIVE", "BUILDING")
MAX_RETRIES = 3  # ORA-00001 때 처음 시도 뒤 다시 시도하는 최대 횟수
_ERROR_MAX_BYTES = 4000  # pipeline_feed_runs.error: VARCHAR2(4000 CHAR)라도 실제 한도는 4000바이트
_IN_LIST_SIZE = 500  # Oracle IN 목록 한도(1000)보다 작게 나눠 조회한다
TITLE_MAX_CHARS = 1000  # news_articles.title 열 길이. 표시용 글이라 넘치면 잘라서 넣는다


@dataclass(frozen=True)
class LoadItem:
    feed: FeedSpec
    key: ArticleKey
    title: str  # 파싱한 원래 제목(머리말 포함). 새 기사면 이 제목(최대 1000자)을 저장하고 키워드를 뽑는다
    summary: str  # 이미 정리한 요약
    link: str  # 표시용 링크
    published_at: datetime  # timezone 정보가 있는 시각
    title_excluded: bool  # 공지 제목([게시판]·[부고]·[인사]) → 적재하지 않는다


@dataclass(frozen=True)
class FeedOutcome:
    feed: FeedSpec
    status: int | None
    etag: str | None
    last_modified: str | None
    raw_key: str | None
    fetched_at: datetime | None  # 봉투의 요청 시각(timezone 포함). 원본 봉투를 읽지 못했으면 None
    item_count: int  # 파싱된 항목 수(= 이 피드의 LoadItem 수). parse_failed는 들어가지 않는다
    parse_failed: int
    missing_required: int
    duplicate_keys: int
    error: str | None  # None이 아니면 실패한 피드


@dataclass(frozen=True)
class RunLoadInput:
    interval_end: datetime
    run_type: str
    items: list[LoadItem]
    feeds: list[FeedOutcome]  # feeds.yml 순서. 같은 기사가 여러 피드에 나오면 앞 피드가 이긴다


@dataclass(frozen=True)
class LoadStats:
    # 기사 건수는 서로 다른 기사 기준이고 구간 기준으로 고정이다(다시 실행해도 같다)
    new_articles: int  # 저장된 first_seen_run_end가 이 구간 끝인 기사
    existing_articles: int  # 다른 구간에서 처음 본 기사
    inserted_articles: int  # 이번 시도에서 news_articles에 실제로 넣은 행 수. 다시 실행하면 0
    excluded_notice: int
    excluded_blocklist: int
    keyword_rows: int  # 이번 실행에서 news_keywords에 넣은 행 수
    outcome: str  # SUCCESS · EMPTY · PARTIAL_FAILURE · FAILURE


@dataclass(frozen=True)
class _Plan:
    """입력만으로 정해지는 적재 계획. DB 상태를 담지 않으므로 재시도할 때 그대로 다시 쓴다."""

    run_id: str
    interval_end: datetime  # naive UTC
    ordered: list[LoadItem]  # feeds 순서로 정렬(피드 안에서는 원래 순서)
    winners: dict[ArticleKey, LoadItem]  # 기사 키마다 이번 실행에서 처음 나온 공지 아닌 항목
    # (제목, 규칙 버전) → 키워드 집합. 새 기사의 제목을 트랜잭션 밖에서 미리 뽑아 둔 것(순수 함수 결과)
    keywords: dict[tuple[str, str], frozenset[str]]


@dataclass(frozen=True)
class _Stored:
    """news_articles에 저장된 기사 한 행에서 적재에 쓰는 값."""

    id: int
    title: str  # 처음 본 제목(키워드는 항상 이 제목에서 뽑는다)
    first_seen_run_end: datetime  # naive UTC. 이 구간 끝과 같으면 이 구간의 새 기사


def load_run(conn: oracledb.Connection, data: RunLoadInput, rule_sets: Mapping[str, RuleSet]) -> LoadStats:
    """한 실행을 한 트랜잭션으로 적재하고 커밋한다. 예외가 나면 롤백한다.

    ORA-00001(동시 실행이 같은 키를 먼저 커밋함)이면 롤백하고 처음부터 최대 MAX_RETRIES번 다시 한다.
    다시 할 때는 DB를 새로 읽어 분류·건수를 처음부터 다시 만든다. 그 밖의 오류는 롤백 후 그대로 던진다.
    입력이 잘못되면 아무것도 쓰지 않고 ValueError를 던진다.
    """
    if conn.autocommit:
        raise ValueError("autocommit이 켜진 연결로는 한 트랜잭션 적재를 보장할 수 없다")
    if conn.transaction_in_progress:
        raise ValueError("이미 진행 중인 트랜잭션이 있다. 먼저 커밋하거나 롤백해야 한다")
    plan = _plan(data, rule_sets)
    started_at = _db_utc_now(conn)  # 재시도해도 처음 시작한 시각을 기록한다

    for attempt in range(MAX_RETRIES + 1):
        try:
            with conn.cursor() as cursor:
                stats = _load_once(cursor, plan, data.feeds, data.run_type, rule_sets, started_at)
            conn.commit()
            return stats
        except BaseException as exc:
            conn.rollback()
            if attempt < MAX_RETRIES and _is_unique_violation(exc):
                continue
            raise
    raise AssertionError("도달하지 않는다")


def last_validators(conn: oracledb.Connection, spec: FeedSpec) -> tuple[str | None, str | None]:
    """피드의 가장 최근 (etag, last_modified)를 돌려준다. 조건부 요청에 쓴다.

    "가장 최근"은 실행의 구간 끝(pipeline_runs.interval_end) 기준이다. 응답을 받은 행(200·304)이면서
    validator가 하나라도 있는 행만 본다. 없으면 (None, None).
    """
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT etag, last_modified FROM ("
            " SELECT f.etag, f.last_modified FROM pipeline_feed_runs f"
            " JOIN pipeline_runs r ON r.run_id = f.run_id"
            " WHERE f.source = :source AND f.feed = :feed AND f.http_status IN (200, 304)"
            " AND (f.etag IS NOT NULL OR f.last_modified IS NOT NULL)"
            " ORDER BY r.interval_end DESC"
            ") WHERE ROWNUM = 1",
            source=spec.source,
            feed=spec.feed,
        )
        row = cursor.fetchone()
    conn.rollback()  # 읽기만 했으므로 열린 트랜잭션을 남기지 않는다(load_run은 열린 트랜잭션을 거부한다)
    if row is None:
        return None, None
    return _text(row[0]), _text(row[1])


def ensure_rule_version(conn: oracledb.Connection, rules: RuleSet) -> str:
    """규칙 버전을 등록하고 그 상태를 돌려준다.

    이미 있으면 저장된 상태 그대로, 표가 비었으면 ACTIVE, 아니면 BUILDING으로 넣고 커밋한다.
    처음 등록이 동시에 일어나 ORA-00001이 나면 롤백하고 한 번 더 확인한다.
    """
    for attempt in range(2):
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT status FROM keyword_rule_versions WHERE rule_version = :rule_version",
                    rule_version=rules.version,
                )
                row = cursor.fetchone()
                if row is not None:
                    return row[0]
                cursor.execute("SELECT COUNT(*) FROM keyword_rule_versions")
                (existing,) = cursor.fetchone()
                status = "ACTIVE" if existing == 0 else "BUILDING"
                cursor.execute(
                    "INSERT INTO keyword_rule_versions (rule_version, rule_json, status)"
                    " VALUES (:rule_version, :rule_json, :status)",
                    rule_version=rules.version,
                    rule_json=rules.to_json(),
                    status=status,
                )
            conn.commit()
            return status
        except BaseException as exc:
            conn.rollback()
            if attempt == 0 and _is_unique_violation(exc):
                continue
            raise
    raise AssertionError("도달하지 않는다")


def writable_rule_sets(conn: oracledb.Connection) -> dict[str, RuleSet]:
    """키워드를 써야 하는 규칙 버전(ACTIVE + BUILDING)을 rule_json에서 복원한다. 버전 순서로 돌려준다."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT rule_version, rule_json FROM keyword_rule_versions"
            " WHERE status IN (:active, :building) ORDER BY rule_version",
            active=WRITABLE_STATUSES[0],
            building=WRITABLE_STATUSES[1],
        )
        fetched = cursor.fetchall()

    result: dict[str, RuleSet] = {}
    for version, rule_json in fetched:
        rules = RuleSet.from_json(_text(rule_json))
        if rules.version != version:
            raise ValueError(f"규칙 버전 {version}의 rule_json이 다른 버전({rules.version})으로 복원된다")
        result[version] = rules
    return result


# ---------------------------------------------------------------------------
# 계획(입력만 보고 정하는 부분)


def _plan(data: RunLoadInput, rule_sets: Mapping[str, RuleSet]) -> _Plan:
    _validate(data, rule_sets)
    positions = {outcome.feed: index for index, outcome in enumerate(data.feeds)}
    # sorted는 안정 정렬이라 같은 피드 안에서는 원래 순서가 유지된다
    ordered = sorted(data.items, key=lambda item: positions[item.feed])

    winners: dict[ArticleKey, LoadItem] = {}
    for item in ordered:
        if not item.title_excluded and item.key not in winners:
            winners[item.key] = item

    # Kiwi 분석은 무거워 트랜잭션 밖에서 미리 한다. 이미 있는 기사의 저장 제목이 다르면 시도 안에서 따로 뽑는다
    keywords = {
        (title, version): extract_keywords(title, rules)
        for title in {_stored_title(item.title) for item in winners.values()}
        for version, rules in rule_sets.items()
    }
    return _Plan(
        run_id=run_id(data.interval_end),
        interval_end=_to_db_time(data.interval_end),
        ordered=ordered,
        winners=winners,
        keywords=keywords,
    )


def _validate(data: RunLoadInput, rule_sets: Mapping[str, RuleSet]) -> None:
    if data.run_type not in RUN_TYPES:
        raise ValueError(f"run_type은 {sorted(RUN_TYPES)} 중 하나여야 한다 (받은 값: {data.run_type!r})")
    _to_db_time(data.interval_end)
    if not data.feeds:
        raise ValueError("feeds가 비어 있다. 실행에는 피드 결과가 하나 이상 필요하다")

    names = [(outcome.feed.source, outcome.feed.feed) for outcome in data.feeds]
    duplicated = sorted({name for name in names if names.count(name) > 1})
    if duplicated:
        raise ValueError(f"feeds에 같은 피드가 여러 번 있다: {duplicated}")
    for outcome in data.feeds:
        if outcome.error is not None and not outcome.error.strip():
            raise ValueError(f"{outcome.feed.source}/{outcome.feed.feed}: 실패 피드의 error가 비어 있다")
        if outcome.fetched_at is not None:
            _to_db_time(outcome.fetched_at)

    per_feed: Counter[FeedSpec] = Counter()
    known = {outcome.feed for outcome in data.feeds}
    for item in data.items:
        where = f"{item.feed.source}/{item.feed.feed} {item.key.source_article_id}"
        if item.feed not in known:
            raise ValueError(f"{where}: 항목의 피드가 feeds에 없다")
        if item.key.source != item.feed.source:
            raise ValueError(f"{where}: 기사 키의 source({item.key.source})가 피드와 다르다")
        _to_db_time(item.published_at)
        per_feed[item.feed] += 1
    for outcome in data.feeds:
        if per_feed[outcome.feed] != outcome.item_count:
            raise ValueError(
                f"{outcome.feed.source}/{outcome.feed.feed}: item_count({outcome.item_count})가"
                f" 항목 수({per_feed[outcome.feed]})와 다르다"
            )

    if not rule_sets:
        raise ValueError("쓰기 가능한 규칙 버전이 없다")
    for version, rules in rule_sets.items():
        if rules.version != version:
            raise ValueError(f"규칙 버전 키 {version}가 규칙의 버전({rules.version})과 다르다")


# ---------------------------------------------------------------------------
# 한 번의 시도(트랜잭션 하나). 상태는 모두 여기서 새로 만든다


def _load_once(
    cursor: oracledb.Cursor,
    plan: _Plan,
    feeds: Sequence[FeedOutcome],
    run_type: str,
    rule_sets: Mapping[str, RuleSet],
    started_at: datetime,
) -> LoadStats:
    blocked = {
        ArticleKey(source, source_article_id)
        for source, source_article_id in _select_by_keys(
            cursor, "SELECT source, source_article_id FROM article_blocklist", list(plan.winners)
        )
    }
    # 정렬된 키 순서로 넣어 동시 실행끼리 잠금 순서를 맞춘다(교착 방지)
    loadable = sorted((key for key in plan.winners if key not in blocked), key=_sort_key)

    inserted = _merge_articles(cursor, [plan.winners[key] for key in loadable], plan.interval_end)
    stored = _stored_articles(cursor, loadable)
    # 실행 기록은 구간 기준: 이번 시도에서 넣었는지가 아니라 저장된 처음 본 구간이 이 구간인지로 센다.
    # 그래서 같은 구간을 다시 처리해도, 동시 실행이 먼저 넣었어도 건수가 같다
    belongs = {key for key in loadable if stored[key].first_seen_run_end == plan.interval_end}

    # 키워드 = f(저장된 제목, 규칙 버전). 이번 실행 항목의 제목이 바뀌었어도 처음 본 제목을 쓴다
    def keywords_for(title: str, version: str) -> frozenset[str]:
        found = plan.keywords.get((title, version))
        return found if found is not None else extract_keywords(title, rule_sets[version])

    versions = sorted(rule_sets)
    by_id = sorted(loadable, key=lambda key: stored[key].id)
    pairs = [(stored[key].id, version) for key in by_id for version in versions]
    keyword_rows = [
        (stored[key].id, keyword, version)
        for key in by_id
        for version in versions
        for keyword in sorted(keywords_for(stored[key].title, version))
    ]
    _delete_keywords(cursor, pairs)
    _insert_keywords(cursor, keyword_rows)

    feed_counts = _classify(plan.ordered, blocked, belongs)
    new_articles = len(belongs)
    stats = LoadStats(
        new_articles=new_articles,
        existing_articles=len(loadable) - new_articles,
        inserted_articles=len(inserted),
        excluded_notice=sum(c["excluded_notice"] for c in feed_counts.values()),
        excluded_blocklist=sum(c["excluded_blocklist"] for c in feed_counts.values()),
        keyword_rows=len(keyword_rows),
        outcome=_outcome(feeds, new_articles),
    )
    _merge_run(cursor, plan, feeds, run_type, stats, started_at)
    _merge_feed_runs(cursor, plan.run_id, feeds, feed_counts)
    return stats


def _classify(
    ordered: list[LoadItem], blocked: set[ArticleKey], belongs: set[ArticleKey]
) -> dict[FeedSpec, Counter[str]]:
    """항목마다 한 칸에만 센다: 공지 → 차단 → 이번 실행에서 이미 나옴 → 새 기사/이미 있음.

    belongs = 저장된 first_seen_run_end가 이 구간 끝인 기사. 그 기사가 이번 실행에서 처음 나온 항목만
    새 기사이고, 나머지(같은 실행의 중복, 다른 구간에서 처음 본 기사)는 이미 있음이다.
    """
    counts: dict[FeedSpec, Counter[str]] = {}
    taken: set[ArticleKey] = set()
    for item in ordered:
        bucket = counts.setdefault(item.feed, Counter())
        if item.title_excluded:
            bucket["excluded_notice"] += 1
        elif item.key in blocked:
            bucket["excluded_blocklist"] += 1
        elif item.key in taken:
            bucket["existing_articles"] += 1  # 같은 실행의 앞 피드가 이미 가져간 기사
        else:
            taken.add(item.key)
            bucket["new_articles" if item.key in belongs else "existing_articles"] += 1
    return counts


def _outcome(feeds: Sequence[FeedOutcome], new_articles: int) -> str:
    failed = sum(1 for outcome in feeds if outcome.error is not None)
    if failed == 0:
        return "SUCCESS" if new_articles > 0 else "EMPTY"
    if failed == len(feeds):
        return "FAILURE"
    return "PARTIAL_FAILURE"


_MERGE_ARTICLE = """
MERGE INTO news_articles t
USING (SELECT :source AS source, :source_article_id AS source_article_id FROM dual) s
ON (t.source = s.source AND t.source_article_id = s.source_article_id)
WHEN NOT MATCHED THEN INSERT
    (source, source_article_id, category, title, summary, link, published_at, first_seen_run_end)
VALUES
    (s.source, s.source_article_id, :category, :title, :summary, :link, :published_at, :first_seen_run_end)
"""


def _merge_articles(cursor: oracledb.Cursor, items: list[LoadItem], interval_end: datetime) -> set[ArticleKey]:
    """없는 기사만 넣는다. 행마다 영향받은 행 수(1 = 새로 넣음, 0 = 이미 있음)로 이번 시도가 넣은 기사를 가려낸다."""
    if not items:
        return set()
    rows = [
        {
            "source": item.key.source,
            "source_article_id": item.key.source_article_id,
            "category": item.feed.category,
            "title": _stored_title(item.title),
            "summary": item.summary,
            "link": item.link,
            "published_at": _to_db_time(item.published_at),
            "first_seen_run_end": interval_end,
        }
        for item in items
    ]
    # python-oracledb 26.1 thin 모드는 문장 캐시에서 다시 꺼낸 문장으로 arraydmlrowcounts를 쓰면
    # DPY-4006(row counts mode is not enabled)을 낸다. 이 문장만 캐시에 넣지 않는다
    cursor.prepare(_MERGE_ARTICLE, cache_statement=False)
    # 요약은 길이와 상관없이 CLOB으로, 시각은 소수 초가 잘리지 않게 TIMESTAMP로 바인드한다
    # (datetime 기본 바인드는 DATE라 소수 초를 버린다)
    cursor.setinputsizes(
        summary=oracledb.DB_TYPE_CLOB,
        published_at=oracledb.DB_TYPE_TIMESTAMP,
        first_seen_run_end=oracledb.DB_TYPE_TIMESTAMP,
    )
    cursor.executemany(None, rows, arraydmlrowcounts=True)
    affected = cursor.getarraydmlrowcounts()
    return {item.key for item, rowcount in zip(items, affected) if rowcount == 1}


def _stored_articles(cursor: oracledb.Cursor, keys: list[ArticleKey]) -> dict[ArticleKey, _Stored]:
    """기사 키 → 저장된 행. MERGE 뒤에 읽으므로 이번에 넣은 기사와 이미 있던 기사가 모두 나온다."""
    found = _select_by_keys(
        cursor, "SELECT source, source_article_id, id, title, first_seen_run_end FROM news_articles", keys
    )
    stored = {
        ArticleKey(source, source_article_id): _Stored(article_id, title, first_seen_run_end)
        for source, source_article_id, article_id, title, first_seen_run_end in found
    }
    missing = [key for key in keys if key not in stored]
    if missing:
        raise RuntimeError(f"MERGE 뒤에도 기사를 찾지 못했다: {missing[:3]}")
    return stored


def _delete_keywords(cursor: oracledb.Cursor, pairs: list[tuple[int, str]]) -> None:
    if pairs:
        cursor.executemany("DELETE FROM news_keywords WHERE article_id = :1 AND rule_version = :2", pairs)


def _insert_keywords(cursor: oracledb.Cursor, keyword_rows: list[tuple[int, str, str]]) -> None:
    """(article_id, keyword, rule_version) 행을 넣는다. 테스트가 실패를 주입하려고 따로 떼어 둔 함수다."""
    if keyword_rows:
        cursor.executemany(
            "INSERT INTO news_keywords (article_id, keyword, rule_version) VALUES (:1, :2, :3)", keyword_rows
        )


_MERGE_RUN = """
MERGE INTO pipeline_runs t
USING (
    SELECT :run_id AS run_id, :interval_end AS interval_end, :run_type AS run_type, :outcome AS outcome,
           :feed_count AS feed_count, :failed_feed_count AS failed_feed_count,
           :new_articles AS new_articles, :existing_articles AS existing_articles,
           :excluded_notice AS excluded_notice, :excluded_blocklist AS excluded_blocklist,
           :parse_failed AS parse_failed, :keyword_rows AS keyword_rows, :started_at AS started_at
    FROM dual
) s
ON (t.run_id = s.run_id)
WHEN MATCHED THEN UPDATE SET
    t.outcome = s.outcome,
    t.feed_count = s.feed_count, t.failed_feed_count = s.failed_feed_count,
    t.new_articles = s.new_articles, t.existing_articles = s.existing_articles,
    t.excluded_notice = s.excluded_notice, t.excluded_blocklist = s.excluded_blocklist,
    t.parse_failed = s.parse_failed, t.keyword_rows = s.keyword_rows,
    t.started_at = s.started_at, t.completed_at = SYS_EXTRACT_UTC(SYSTIMESTAMP)
WHEN NOT MATCHED THEN INSERT
    (run_id, interval_end, run_type, outcome, feed_count, failed_feed_count, new_articles, existing_articles,
     excluded_notice, excluded_blocklist, parse_failed, keyword_rows, started_at, completed_at)
VALUES
    (s.run_id, s.interval_end, s.run_type, s.outcome, s.feed_count, s.failed_feed_count, s.new_articles,
     s.existing_articles, s.excluded_notice, s.excluded_blocklist, s.parse_failed, s.keyword_rows,
     s.started_at, SYS_EXTRACT_UTC(SYSTIMESTAMP))
"""


def _merge_run(
    cursor: oracledb.Cursor,
    plan: _Plan,
    feeds: Sequence[FeedOutcome],
    run_type: str,
    stats: LoadStats,
    started_at: datetime,
) -> None:
    # 실행 행은 커밋 직전에 쓴다: completed_at(DB 시각)이 적재를 마친 시각이 된다.
    # 다시 실행하면 건수·결과·started_at·completed_at을 갱신하지만 run_type은 처음 적재한 값을 지킨다
    # (정기 실행을 백필로 다시 처리해도 그 구간을 처음 만든 실행 종류가 남는다)
    cursor.setinputsizes(interval_end=oracledb.DB_TYPE_TIMESTAMP, started_at=oracledb.DB_TYPE_TIMESTAMP)
    cursor.execute(
        _MERGE_RUN,
        run_id=plan.run_id,
        interval_end=plan.interval_end,
        run_type=run_type,
        outcome=stats.outcome,
        feed_count=len(feeds),
        failed_feed_count=sum(1 for outcome in feeds if outcome.error is not None),
        new_articles=stats.new_articles,
        existing_articles=stats.existing_articles,
        excluded_notice=stats.excluded_notice,
        excluded_blocklist=stats.excluded_blocklist,
        parse_failed=sum(outcome.parse_failed for outcome in feeds),
        keyword_rows=stats.keyword_rows,
        started_at=started_at,
    )


_MERGE_FEED_RUN = """
MERGE INTO pipeline_feed_runs t
USING (
    SELECT :run_id AS run_id, :source AS source, :feed AS feed, :http_status AS http_status,
           :etag AS etag, :last_modified AS last_modified, :raw_key AS raw_key, :fetched_at AS fetched_at,
           :item_count AS item_count, :new_articles AS new_articles, :existing_articles AS existing_articles,
           :excluded_notice AS excluded_notice, :excluded_blocklist AS excluded_blocklist,
           :parse_failed AS parse_failed, :missing_required AS missing_required,
           :duplicate_keys AS duplicate_keys, :error AS error
    FROM dual
) s
ON (t.run_id = s.run_id AND t.source = s.source AND t.feed = s.feed)
WHEN MATCHED THEN UPDATE SET
    t.http_status = s.http_status, t.etag = s.etag, t.last_modified = s.last_modified, t.raw_key = s.raw_key,
    t.fetched_at = s.fetched_at, t.item_count = s.item_count, t.new_articles = s.new_articles,
    t.existing_articles = s.existing_articles,
    t.excluded_notice = s.excluded_notice, t.excluded_blocklist = s.excluded_blocklist,
    t.parse_failed = s.parse_failed, t.missing_required = s.missing_required,
    t.duplicate_keys = s.duplicate_keys, t.error = s.error
WHEN NOT MATCHED THEN INSERT
    (run_id, source, feed, http_status, etag, last_modified, raw_key, fetched_at, item_count, new_articles,
     existing_articles, excluded_notice, excluded_blocklist, parse_failed, missing_required, duplicate_keys, error)
VALUES
    (s.run_id, s.source, s.feed, s.http_status, s.etag, s.last_modified, s.raw_key, s.fetched_at, s.item_count,
     s.new_articles, s.existing_articles, s.excluded_notice, s.excluded_blocklist, s.parse_failed,
     s.missing_required, s.duplicate_keys, s.error)
"""


def _merge_feed_runs(
    cursor: oracledb.Cursor, run: str, feeds: Sequence[FeedOutcome], feed_counts: Mapping[FeedSpec, Counter[str]]
) -> None:
    rows = []
    for outcome in feeds:
        counted = feed_counts.get(outcome.feed, Counter())
        rows.append(
            {
                "run_id": run,
                "source": outcome.feed.source,
                "feed": outcome.feed.feed,
                "http_status": outcome.status,
                "etag": outcome.etag,
                "last_modified": outcome.last_modified,
                "raw_key": outcome.raw_key,
                "fetched_at": None if outcome.fetched_at is None else _to_db_time(outcome.fetched_at),
                "item_count": outcome.item_count,
                "new_articles": counted["new_articles"],
                "existing_articles": counted["existing_articles"],
                "excluded_notice": counted["excluded_notice"],
                "excluded_blocklist": counted["excluded_blocklist"],
                "parse_failed": outcome.parse_failed,
                "missing_required": outcome.missing_required,
                "duplicate_keys": outcome.duplicate_keys,
                "error": _truncate_utf8(outcome.error, _ERROR_MAX_BYTES),
            }
        )
    _delete_stale_feed_runs(cursor, run, feeds)
    # 값이 모두 None인 열도 있어 바인드 형식을 정해 둔다. 시각은 소수 초가 잘리지 않게 TIMESTAMP로 넣는다
    cursor.setinputsizes(http_status=oracledb.DB_TYPE_NUMBER, fetched_at=oracledb.DB_TYPE_TIMESTAMP)
    cursor.executemany(_MERGE_FEED_RUN, rows)


def _delete_stale_feed_runs(cursor: oracledb.Cursor, run: str, feeds: Sequence[FeedOutcome]) -> None:
    """같은 실행을 다른 피드 목록으로 다시 돌렸을 때 이번 입력에 없는 피드 행을 지운다.

    지우지 않으면 빠진 피드의 옛 건수·validator·error가 남아 feed_count와 행 수가 어긋난다.
    실행 행 MERGE 뒤에 부르므로 같은 run_id를 쓰는 동시 실행은 실행 행 잠금에서 차례로 들어온다.
    feeds는 비어 있지 않다(_validate). 피드 수는 feeds.yml 크기(17)라 IN 목록 한도(1000)에 닿지 않는다.
    """
    placeholders = ", ".join(f"(:s{index}, :f{index})" for index in range(len(feeds)))
    binds: dict[str, str] = {"run_id": run}
    for index, outcome in enumerate(feeds):
        binds[f"s{index}"] = outcome.feed.source
        binds[f"f{index}"] = outcome.feed.feed
    cursor.execute(
        f"DELETE FROM pipeline_feed_runs WHERE run_id = :run_id AND (source, feed) NOT IN ({placeholders})", binds
    )


# ---------------------------------------------------------------------------
# 도움 함수


def _select_by_keys(cursor: oracledb.Cursor, select: str, keys: list[ArticleKey]) -> list[tuple]:
    """(source, source_article_id) IN 목록으로 조회한다. 목록이 길면 나눠서 조회한다."""
    found: list[tuple] = []
    for start in range(0, len(keys), _IN_LIST_SIZE):
        chunk = keys[start : start + _IN_LIST_SIZE]
        placeholders = ", ".join(f"(:s{index}, :a{index})" for index in range(len(chunk)))
        binds = {}
        for index, key in enumerate(chunk):
            binds[f"s{index}"] = key.source
            binds[f"a{index}"] = key.source_article_id
        cursor.execute(f"{select} WHERE (source, source_article_id) IN ({placeholders})", binds)
        found.extend(cursor.fetchall())
    return found


def _stored_title(title: str) -> str:
    # 제목은 화면 표시용이라 열 길이를 넘으면 잘라서 저장한다(기사 키·링크는 자르지 않는다)
    return title[:TITLE_MAX_CHARS]


def _sort_key(key: ArticleKey) -> tuple[str, str]:
    return key.source, key.source_article_id


def _to_db_time(value: datetime) -> datetime:
    """TIMESTAMP 열에는 UTC를 naive로 넣는다. naive 입력은 어느 시간대인지 몰라 거부한다."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"timezone 정보가 있는 datetime이 필요하다: {value!r}")
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _db_utc_now(conn: oracledb.Connection) -> datetime:
    with conn.cursor() as cursor:
        cursor.execute("SELECT SYS_EXTRACT_UTC(SYSTIMESTAMP) FROM dual")
        (now,) = cursor.fetchone()
    return now


def _is_unique_violation(exc: BaseException) -> bool:
    if not isinstance(exc, oracledb.IntegrityError):
        return False
    error = exc.args[0] if exc.args else None
    return getattr(error, "full_code", None) == "ORA-00001"


def _truncate_utf8(text: str | None, max_bytes: int) -> str | None:
    if text is None:
        return None
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    # 글자 중간에서 잘린 바이트는 버린다
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _text(value: object) -> str:
    return value.read() if isinstance(value, oracledb.LOB) else value
