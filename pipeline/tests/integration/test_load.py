"""실버 적재(load_run)의 멱등성 통합 테스트: 두 번 실행 · 동시 실행 · 중간 실패 · 중복 0 · 차단 목록 · 규칙 버전."""

import threading
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import oracledb
import pytest

from trend_pipeline import db, load
from trend_pipeline.article_key import ArticleKey
from trend_pipeline.feeds import FeedSpec
from trend_pipeline.keys import run_id
from trend_pipeline.keywords import RuleSet, extract_keywords
from trend_pipeline.load import (
    FeedOutcome,
    LoadItem,
    LoadStats,
    RunLoadInput,
    ensure_rule_version,
    load_run,
    writable_rule_sets,
)

from conftest import INTERVAL_END, V2_TABLES, feed_spec

pytestmark = pytest.mark.integration

KST = timezone(timedelta(hours=9))


def rows(conn: oracledb.Connection, sql: str, **binds) -> list[tuple]:
    with conn.cursor() as cursor:
        cursor.execute(sql, binds)
        return [tuple(value.read() if isinstance(value, oracledb.LOB) else value for value in row) for row in cursor]


def counts(conn: oracledb.Connection) -> dict[str, int]:
    return {table: rows(conn, f"SELECT COUNT(*) FROM {table}")[0][0] for table in V2_TABLES}


def silver_rows(conn: oracledb.Connection) -> tuple[list[tuple], list[tuple]]:
    """기사·키워드 내용 전체. id 대신 기사 키로 맞춰 비교한다."""
    articles = rows(
        conn,
        "SELECT source, source_article_id, category, title, summary, link, published_at, first_seen_run_end"
        " FROM news_articles ORDER BY source, source_article_id",
    )
    keywords = rows(
        conn,
        "SELECT a.source, a.source_article_id, k.keyword, k.rule_version"
        " FROM news_keywords k JOIN news_articles a ON a.id = k.article_id"
        " ORDER BY 1, 2, 3, 4",
    )
    return articles, keywords


def duplicate_rows(conn: oracledb.Connection) -> tuple[list[tuple], list[tuple]]:
    """중복 검사 SQL. 둘 다 0행이어야 한다."""
    articles = rows(
        conn,
        "SELECT source, source_article_id FROM news_articles GROUP BY source, source_article_id HAVING COUNT(*) > 1",
    )
    keywords = rows(
        conn,
        "SELECT article_id, keyword, rule_version FROM news_keywords"
        " GROUP BY article_id, keyword, rule_version HAVING COUNT(*) > 1",
    )
    return articles, keywords


def loadable_keys(run: RunLoadInput) -> set[ArticleKey]:
    """공지 제목이 아닌 서로 다른 기사 키(차단 목록이 비어 있을 때 적재될 기사)."""
    return {item.key for item in run.items if not item.title_excluded}


def feed_rows(conn: oracledb.Connection, interval_end: datetime | None = None) -> dict[tuple[str, str], dict]:
    """피드 실행 행. interval_end를 주면 그 구간의 실행만 본다."""
    columns = (
        "source, feed, http_status, etag, last_modified, raw_key, fetched_at, item_count, new_articles,"
        " existing_articles, excluded_notice, excluded_blocklist, parse_failed, missing_required, duplicate_keys, error"
    )
    names = [name.strip() for name in columns.split(",")]
    where, binds = ("", {}) if interval_end is None else (" WHERE run_id = :run_id", {"run_id": run_id(interval_end)})
    result = {}
    for row in rows(conn, f"SELECT {columns} FROM pipeline_feed_runs{where}", **binds):
        record = dict(zip(names, row))
        result[(record["source"], record["feed"])] = record
    return result


def run_row(conn: oracledb.Connection, interval_end: datetime | None = None) -> dict:
    """실행 행 하나. interval_end가 없으면 표에 행이 하나뿐이어야 한다."""
    columns = (
        "run_id, interval_end, run_type, outcome, feed_count, failed_feed_count, new_articles, existing_articles,"
        " excluded_notice, excluded_blocklist, parse_failed, keyword_rows, started_at, completed_at"
    )
    names = [name.strip() for name in columns.split(",")]
    where, binds = ("", {}) if interval_end is None else (" WHERE run_id = :run_id", {"run_id": run_id(interval_end)})
    (row,) = rows(conn, f"SELECT {columns} FROM pipeline_runs{where}", **binds)
    return dict(zip(names, row))


def without_times(record: dict) -> dict:
    """실행 행에서 처리할 때마다 바뀌는 시각(started_at, completed_at)을 뺀다."""
    return {name: value for name, value in record.items() if name not in ("started_at", "completed_at")}


def outcome_for(
    spec: FeedSpec, item_count: int, error: str | None = None, fetched_at: datetime | None = None
) -> FeedOutcome:
    return FeedOutcome(
        feed=spec,
        status=None if error else 200,
        etag=None,
        last_modified=None,
        raw_key=None,
        fetched_at=fetched_at,
        item_count=item_count,
        parse_failed=0,
        missing_required=0,
        duplicate_keys=0,
        error=error,
    )


def article(
    spec: FeedSpec, number: str, title: str, published_at: datetime | None = None, summary: str = "요약"
) -> LoadItem:
    key = ArticleKey(spec.source, number)
    return LoadItem(
        feed=spec,
        key=key,
        title=title,
        summary=summary,
        link=f"https://www.yna.co.kr/view/{number}",
        published_at=published_at or datetime(2026, 11, 4, 2, 30, tzinfo=timezone.utc),
        title_excluded=False,
    )


def test_same_run_twice_gives_same_rows(conn, sample_run, rules):
    s1 = load_run(conn, sample_run, rules)
    rows1, silver1 = counts(conn), silver_rows(conn)
    run1, feeds1 = run_row(conn), feed_rows(conn)

    s2 = load_run(conn, sample_run, rules)

    assert counts(conn) == rows1
    assert silver_rows(conn) == silver1
    assert s1.new_articles == s1.inserted_articles == len(loadable_keys(sample_run)) > 0
    assert s1.existing_articles == 0 and s1.outcome == "SUCCESS" and s1.keyword_rows > 0
    # 실행 기록은 구간 기준으로 고정된다: 다시 실행해도 건수·결과가 같고, 이번 시도에서 넣은 행만 0이다
    assert s2.inserted_articles == 0
    assert replace(s2, inserted_articles=s1.inserted_articles) == s1
    assert rows1["pipeline_runs"] == 1 and rows1["pipeline_feed_runs"] == 2
    # 다시 실행하면 같은 실행 행을 갱신하지만 시각을 빼면 값이 같다. 피드 행은 모두 같다
    run2 = run_row(conn)
    assert without_times(run2) == without_times(run1)
    assert run2["started_at"] >= run1["started_at"] and run2["completed_at"] >= run1["completed_at"]
    assert feed_rows(conn) == feeds1


def test_article_seen_again_in_next_interval_counts_as_existing(conn, rules):
    politics = feed_spec("yna", "정치")
    seen, fresh = "AKR20261104000900009", "AKR20261104001000010"
    later_end = INTERVAL_END + timedelta(hours=1)
    first = RunLoadInput(
        interval_end=INTERVAL_END,
        run_type="scheduled",
        items=[article(politics, seen, "국회 예산안 처리 합의")],
        feeds=[outcome_for(politics, 1)],
    )
    second = RunLoadInput(
        interval_end=later_end,
        run_type="scheduled",
        items=[article(politics, seen, "국회 예산안 처리 합의"), article(politics, fresh, "반도체 수출 급증 전망")],
        feeds=[outcome_for(politics, 2)],
    )

    s1 = load_run(conn, first, rules)
    first_run, first_feeds = run_row(conn, INTERVAL_END), feed_rows(conn, INTERVAL_END)
    s2 = load_run(conn, second, rules)

    # N에서 처음 본 기사는 N+1에서 이미 있음이다(실행·피드 모두). N의 기록은 바뀌지 않는다
    assert (s1.new_articles, s1.existing_articles, s1.inserted_articles) == (1, 0, 1)
    assert (s2.new_articles, s2.existing_articles, s2.inserted_articles, s2.outcome) == (1, 1, 1, "SUCCESS")
    later_feed = feed_rows(conn, later_end)[("yna", "politics")]
    assert (later_feed["new_articles"], later_feed["existing_articles"]) == (1, 1)
    later_run = run_row(conn, later_end)
    assert (later_run["new_articles"], later_run["existing_articles"]) == (1, 1)
    assert run_row(conn, INTERVAL_END) == first_run
    assert feed_rows(conn, INTERVAL_END) == first_feeds

    # N을 다시 처리해도 그 기사는 여전히 N 소속이다. 두 구간의 기록이 모두 그대로다
    again = load_run(conn, first, rules)
    assert replace(again, inserted_articles=s1.inserted_articles) == s1 and again.inserted_articles == 0
    assert without_times(run_row(conn, INTERVAL_END)) == without_times(first_run)
    assert feed_rows(conn, INTERVAL_END) == first_feeds
    assert without_times(run_row(conn, later_end)) == without_times(later_run)


def test_rerun_keeps_run_type_of_first_load(conn, sample_run, rules):
    load_run(conn, sample_run, rules)
    first = run_row(conn)

    load_run(conn, replace(sample_run, run_type="backfill"), rules)

    # run_type은 처음 적재한 값 그대로, 시각은 가장 최근 처리 기준이다
    record = run_row(conn)
    assert (first["run_type"], record["run_type"]) == ("scheduled", "scheduled")
    assert record["started_at"] >= first["started_at"] and record["completed_at"] >= first["completed_at"]


@pytest.mark.parametrize("preloaded", [False, True], ids=["first-load", "rerun"])
def test_concurrent_runs_no_duplicates_no_errors(conn, sample_run, rules, preloaded):
    expected = len(loadable_keys(sample_run))
    if preloaded:
        # 이미 적재된 실행을 둘이 동시에 다시 돌린다(키워드 지우고 다시 쓰기·실행 행 갱신이 겹친다)
        load_run(conn, sample_run, rules)
    barrier = threading.Barrier(2)
    results: list[LoadStats | None] = [None, None]
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            # 각자 연결을 연다(conftest가 세 환경 변수를 설정해 두었다)
            with db.connect() as own:
                barrier.wait(timeout=60)
                results[index] = load_run(own, sample_run, rules)
        except BaseException as exc:  # 스레드 안의 예외를 본 스레드로 넘긴다
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=300)

    assert errors == []
    assert all(isinstance(stats, LoadStats) for stats in results)
    # 실행 기록은 구간 기준이라 둘 다 같은 건수를 본다. 실제로 넣은 행은 (처음 적재일 때) 한쪽에만 있다
    assert all((stats.new_articles, stats.existing_articles) == (expected, 0) for stats in results)
    assert sum(stats.inserted_articles for stats in results) == (0 if preloaded else expected)
    assert results[0].keyword_rows == results[1].keyword_rows > 0
    assert duplicate_rows(conn) == ([], [])
    assert counts(conn) == {
        "pipeline_feed_runs": 2,
        "pipeline_runs": 1,
        "news_keywords": results[0].keyword_rows,
        "news_articles": expected,
        "article_blocklist": 0,
        "keyword_rule_versions": 1,
    }


def test_failure_mid_transaction_rolls_back_then_rerun_succeeds(conn, sample_run, rules, monkeypatch):
    def fail(cursor, keyword_rows):
        raise RuntimeError("키워드 INSERT 중 주입한 실패")

    monkeypatch.setattr(load, "_insert_keywords", fail)
    with pytest.raises(RuntimeError, match="주입한 실패"):
        load_run(conn, sample_run, rules)

    assert not conn.transaction_in_progress
    assert counts(conn) == {table: 0 for table in V2_TABLES} | {"keyword_rule_versions": 1}

    monkeypatch.undo()
    stats = load_run(conn, sample_run, rules)
    assert stats.new_articles == len(loadable_keys(sample_run))
    assert stats.outcome == "SUCCESS"
    assert counts(conn)["news_keywords"] == stats.keyword_rows > 0


def test_unique_violation_reruns_whole_transaction_from_scratch(conn, sample_run, rules, monkeypatch):
    real_insert = load._insert_keywords
    calls = []

    def collide_once(cursor, keyword_rows):
        calls.append(len(keyword_rows))
        real_insert(cursor, keyword_rows)
        if len(calls) == 1:
            real_insert(cursor, keyword_rows[:1])  # 같은 PK를 한 번 더 넣어 진짜 ORA-00001을 낸다

    monkeypatch.setattr(load, "_insert_keywords", collide_once)
    stats = load_run(conn, sample_run, rules)

    assert len(calls) == 2
    # 첫 시도의 기사 INSERT는 롤백됐으므로 두 번째 시도가 모두 다시 넣는다(시도별 상태가 남지 않는다)
    assert stats.new_articles == stats.inserted_articles == len(loadable_keys(sample_run))
    assert stats.existing_articles == 0
    assert counts(conn)["news_keywords"] == stats.keyword_rows == calls[1]
    assert duplicate_rows(conn) == ([], [])


def test_unique_violation_gives_up_after_three_retries(conn, sample_run, rules, monkeypatch):
    real_insert = load._insert_keywords
    calls = []

    def always_collide(cursor, keyword_rows):
        calls.append(len(keyword_rows))
        real_insert(cursor, keyword_rows)
        real_insert(cursor, keyword_rows[:1])

    monkeypatch.setattr(load, "_insert_keywords", always_collide)
    with pytest.raises(oracledb.IntegrityError, match="ORA-00001"):
        load_run(conn, sample_run, rules)

    assert len(calls) == 4  # 처음 1번 + 다시 3번
    assert counts(conn) == {table: 0 for table in V2_TABLES} | {"keyword_rule_versions": 1}


def test_other_database_error_is_not_retried(conn, sample_run, rules, monkeypatch):
    calls = []

    def insert_null(cursor, keyword_rows):
        calls.append(len(keyword_rows))
        cursor.execute("INSERT INTO news_keywords (article_id, keyword, rule_version) VALUES (:1, NULL, :2)",
                       [keyword_rows[0][0], keyword_rows[0][2]])

    monkeypatch.setattr(load, "_insert_keywords", insert_null)
    with pytest.raises(oracledb.IntegrityError, match="ORA-01400"):
        load_run(conn, sample_run, rules)

    assert len(calls) == 1
    assert counts(conn)["news_articles"] == 0


def test_duplicate_check_sql_is_zero(conn, sample_run, rules):
    load_run(conn, sample_run, rules)
    load_run(conn, sample_run, rules)

    assert duplicate_rows(conn) == ([], [])


def test_key_lookups_split_into_chunks(conn, sample_run, rules, monkeypatch):
    # 17개 피드 실행은 기사 키가 1000개를 넘어 Oracle IN 목록 한도에 걸린다. 작은 단위로 나눠도 결과가 같아야 한다
    monkeypatch.setattr(load, "_IN_LIST_SIZE", 7)
    last = sorted(loadable_keys(sample_run), key=lambda key: (key.source, key.source_article_id))[-1]
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO article_blocklist (source, source_article_id, requester_type) VALUES (:1, :2, 'ADMIN')",
            [last.source, last.source_article_id],
        )
    conn.commit()

    s1 = load_run(conn, sample_run, rules)
    s2 = load_run(conn, sample_run, rules)

    expected = len(loadable_keys(sample_run)) - 1
    assert (s1.new_articles, s1.inserted_articles, s1.excluded_blocklist) == (expected, expected, 1)
    assert (s2.new_articles, s2.existing_articles, s2.inserted_articles) == (expected, 0, 0)
    assert counts(conn)["news_articles"] == expected


def test_blocklisted_article_never_loaded_even_on_rerun(conn, sample_run, rules):
    target = next(item for item in sample_run.items if item.feed.source == "khan" and not item.title_excluded)
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO article_blocklist (source, source_article_id, reason, requester_type)"
            " VALUES (:source, :source_article_id, '테스트 삭제 요청', 'ADMIN')",
            source=target.key.source,
            source_article_id=target.key.source_article_id,
        )
    conn.commit()
    blocked_items = sum(1 for item in sample_run.items if item.key == target.key)

    s1 = load_run(conn, sample_run, rules)
    s2 = load_run(conn, sample_run, rules)

    found = rows(
        conn,
        "SELECT COUNT(*) FROM news_articles WHERE source = :source AND source_article_id = :source_article_id",
        source=target.key.source,
        source_article_id=target.key.source_article_id,
    )
    assert found == [(0,)]
    assert s1.excluded_blocklist == s2.excluded_blocklist == blocked_items
    assert s1.new_articles == s2.new_articles == len(loadable_keys(sample_run)) - 1
    assert s2.inserted_articles == 0
    assert feed_rows(conn)[(target.feed.source, target.feed.feed)]["excluded_blocklist"] == blocked_items


def test_same_article_in_two_feeds_keeps_first_feed_category(conn, rules):
    politics, economy = feed_spec("yna", "정치"), feed_spec("yna", "경제")
    shared = "AKR20261104000100001"
    # 항목 목록 순서가 아니라 feeds(= feeds.yml) 순서가 기준이다: 경제 항목을 앞에 둬도 정치가 이긴다
    items = [
        article(economy, shared, "경제면 제목 반도체 수출"),
        article(economy, "AKR20261104000200002", "환율 급등 증시 하락"),
        article(politics, "AKR20261104000300003", "여야 원내대표 회동"),
        article(politics, shared, "정치면 제목 국회 예산안"),
    ]
    run = RunLoadInput(
        interval_end=INTERVAL_END,
        run_type="scheduled",
        items=items,
        feeds=[outcome_for(politics, 2), outcome_for(economy, 2)],
    )

    stats = load_run(conn, run, rules)

    assert (stats.new_articles, stats.existing_articles) == (3, 0)
    assert rows(
        conn,
        "SELECT category, title, first_seen_run_end FROM news_articles WHERE source_article_id = :id",
        id=shared,
    ) == [("정치", "정치면 제목 국회 예산안", datetime(2026, 11, 4, 3, 0))]
    by_feed = feed_rows(conn)
    assert (by_feed[("yna", "politics")]["new_articles"], by_feed[("yna", "politics")]["existing_articles"]) == (2, 0)
    assert (by_feed[("yna", "economy")]["new_articles"], by_feed[("yna", "economy")]["existing_articles"]) == (1, 1)
    (version,) = rules
    shared_keywords = rows(
        conn,
        "SELECT k.keyword FROM news_keywords k JOIN news_articles a ON a.id = k.article_id"
        " WHERE a.source_article_id = :id AND k.rule_version = :version",
        id=shared,
        version=version,
    )
    assert {keyword for (keyword,) in shared_keywords} == extract_keywords("정치면 제목 국회 예산안", rules[version])

    # 다음 실행에서 경제 피드에만 나와도 저장된 카테고리와 처음 본 실행은 그대로다
    later = RunLoadInput(
        interval_end=INTERVAL_END + timedelta(hours=1),
        run_type="scheduled",
        items=[article(economy, shared, "경제면 제목 반도체 수출")],
        feeds=[outcome_for(economy, 1)],
    )
    later_stats = load_run(conn, later, rules)

    assert (later_stats.new_articles, later_stats.existing_articles) == (0, 1)
    assert rows(
        conn, "SELECT category, first_seen_run_end FROM news_articles WHERE source_article_id = :id", id=shared
    ) == [("정치", datetime(2026, 11, 4, 3, 0))]


def keywords_of(conn: oracledb.Connection, number: str, version: str) -> set[str]:
    found = rows(
        conn,
        "SELECT k.keyword FROM news_keywords k JOIN news_articles a ON a.id = k.article_id"
        " WHERE a.source_article_id = :id AND k.rule_version = :version",
        id=number,
        version=version,
    )
    return {keyword for (keyword,) in found}


def test_keywords_follow_stored_first_seen_title(conn, rules):
    politics = feed_spec("yna", "정치")
    number = "AKR20261104000700007"
    first_title, edited_title = "국회 예산안 처리 합의", "반도체 수출 급증 전망"
    (version,) = rules
    first_keywords = extract_keywords(first_title, rules[version])
    assert first_keywords and first_keywords.isdisjoint(extract_keywords(edited_title, rules[version]))

    def run_at(hours: int, title: str) -> RunLoadInput:
        return RunLoadInput(
            interval_end=INTERVAL_END + timedelta(hours=hours),
            run_type="scheduled",
            items=[article(politics, number, title)],
            feeds=[outcome_for(politics, 1)],
        )

    load_run(conn, run_at(0, first_title), rules)
    # 다음 구간에서 언론사가 제목을 고쳐도 저장 제목과 키워드는 처음 본 제목 그대로다
    later = load_run(conn, run_at(1, edited_title), rules)
    assert rows(conn, "SELECT title FROM news_articles") == [(first_title,)]
    assert keywords_of(conn, number, version) == first_keywords
    assert later.keyword_rows == len(first_keywords)

    # 앞 구간을 다시 처리해도(처리 순서가 바뀌어도) 결과가 같다
    load_run(conn, run_at(0, first_title), rules)
    load_run(conn, run_at(1, edited_title), rules)
    assert keywords_of(conn, number, version) == first_keywords


def test_title_over_column_length_is_truncated(conn, rules):
    politics = feed_spec("yna", "정치")
    long_title = ("국회 예산안 처리 " * 200)[:1200]
    run = RunLoadInput(
        interval_end=INTERVAL_END,
        run_type="manual",
        items=[article(politics, "AKR20261104000800008", long_title)],
        feeds=[outcome_for(politics, 1)],
    )

    stats = load_run(conn, run, rules)

    assert stats.outcome == "SUCCESS" and stats.new_articles == 1
    assert rows(conn, "SELECT LENGTH(title), title FROM news_articles") == [(1000, long_title[:1000])]
    (version,) = rules
    assert keywords_of(conn, "AKR20261104000800008", version) == extract_keywords(long_title[:1000], rules[version])


def test_times_are_stored_as_utc(conn, rules):
    politics = feed_spec("yna", "정치")
    published_kst = datetime(2026, 11, 4, 12, 15, tzinfo=KST)
    run = RunLoadInput(
        interval_end=datetime(2026, 11, 4, 13, 0, tzinfo=KST),  # = 04:00 UTC
        run_type="manual",
        items=[article(politics, "AKR20261104000400004", "국회 본회의 개최", published_at=published_kst)],
        feeds=[outcome_for(politics, 1, fetched_at=datetime(2026, 11, 4, 13, 0, 2, 500000, tzinfo=KST))],
    )
    before = datetime.now(timezone.utc).replace(tzinfo=None)

    load_run(conn, run, rules)

    assert rows(conn, "SELECT published_at, first_seen_run_end FROM news_articles") == [
        (datetime(2026, 11, 4, 3, 15), datetime(2026, 11, 4, 4, 0))
    ]
    # 피드를 받은 시각도 UTC로, 소수 초까지 저장한다
    assert rows(conn, "SELECT fetched_at FROM pipeline_feed_runs") == [(datetime(2026, 11, 4, 4, 0, 2, 500000),)]
    record = run_row(conn)
    assert record["interval_end"] == datetime(2026, 11, 4, 4, 0)
    # 실행 시각도 UTC다(KST로 들어가면 9시간 어긋난다)
    assert abs(record["started_at"] - before) < timedelta(minutes=5)
    assert record["started_at"] <= record["completed_at"]


def test_long_and_empty_summary_round_trip(conn, rules):
    politics = feed_spec("yna", "정치")
    long_summary = "가나다라마바사아자차" * 1000  # 1만 자, UTF-8 3만 바이트: VARCHAR2 바인드 한도(4000바이트)를 넘는다
    run = RunLoadInput(
        interval_end=INTERVAL_END,
        run_type="manual",
        items=[
            article(politics, "AKR20261104000500005", "긴 요약 기사", summary=long_summary),
            article(politics, "AKR20261104000600006", "요약 없는 기사", summary=""),
        ],
        feeds=[outcome_for(politics, 2)],
    )

    load_run(conn, run, rules)

    assert rows(conn, "SELECT source_article_id, summary FROM news_articles ORDER BY source_article_id") == [
        ("AKR20261104000500005", long_summary),
        ("AKR20261104000600006", None),  # Oracle은 빈 문자열을 NULL로 저장한다
    ]


def test_building_rule_version_also_written(conn, sample_run, rule_set):
    assert ensure_rule_version(conn, rule_set) == "ACTIVE"
    # 샘플에서 가장 흔한 키워드를 불용어로 더한 규칙 = 다른 버전(빌드 중)
    frequency = Counter(kw for item in sample_run.items for kw in extract_keywords(item.title, rule_set))
    top_keyword, _ = frequency.most_common(1)[0]
    building = replace(rule_set, stopwords=rule_set.stopwords | {top_keyword})
    assert ensure_rule_version(conn, building) == "BUILDING"
    rule_sets = writable_rule_sets(conn)
    assert set(rule_sets) == {rule_set.version, building.version}

    stats = load_run(conn, sample_run, rule_sets)

    per_version = dict(rows(conn, "SELECT rule_version, COUNT(*) FROM news_keywords GROUP BY rule_version"))
    assert per_version[rule_set.version] > per_version[building.version] > 0
    assert sum(per_version.values()) == stats.keyword_rows

    def has_keyword(version: str) -> bool:
        found = rows(
            conn,
            "SELECT COUNT(*) FROM news_keywords WHERE keyword = :keyword AND rule_version = :version",
            keyword=top_keyword,
            version=version,
        )
        return found[0][0] > 0

    assert has_keyword(rule_set.version) and not has_keyword(building.version)


def test_feed_run_counts_reconcile(conn, sample_run, rules):
    stats = load_run(conn, sample_run, rules)

    by_feed = feed_rows(conn)
    assert set(by_feed) == {(outcome.feed.source, outcome.feed.feed) for outcome in sample_run.feeds}
    for outcome in sample_run.feeds:
        record = by_feed[(outcome.feed.source, outcome.feed.feed)]
        feed_items = [item for item in sample_run.items if item.feed == outcome.feed]
        buckets = ("new_articles", "existing_articles", "excluded_notice", "excluded_blocklist")
        assert record["item_count"] == outcome.item_count == len(feed_items)
        assert record["item_count"] == sum(record[bucket] for bucket in buckets)
        assert record["excluded_notice"] == sum(1 for item in feed_items if item.title_excluded)
        assert (record["http_status"], record["etag"], record["raw_key"], record["error"]) == (
            200, '"fixture-etag"', outcome.raw_key, None
        )
        assert record["fetched_at"] == outcome.fetched_at.astimezone(timezone.utc).replace(tzinfo=None)
        assert (record["parse_failed"], record["missing_required"], record["duplicate_keys"]) == (
            outcome.parse_failed, outcome.missing_required, outcome.duplicate_keys
        )
    yna = by_feed[("yna", "politics")]
    assert yna["excluded_notice"] > 0  # 고정 샘플에 [게시판]/[부고]/[인사] 제목이 있다

    record = run_row(conn)
    assert (record["feed_count"], record["failed_feed_count"], record["outcome"]) == (2, 0, "SUCCESS")
    assert (record["new_articles"], record["excluded_notice"], record["keyword_rows"]) == (
        stats.new_articles, stats.excluded_notice, stats.keyword_rows
    )
    assert record["parse_failed"] == sum(outcome.parse_failed for outcome in sample_run.feeds)
    assert stats.excluded_notice == sum(r["excluded_notice"] for r in by_feed.values())

    # 대조 CHECK 제약이 DB에서도 지켜진다
    with pytest.raises(oracledb.IntegrityError, match="ORA-02290"):
        with conn.cursor() as cursor:
            cursor.execute("UPDATE pipeline_feed_runs SET new_articles = new_articles + 1")
    conn.rollback()


def test_rerun_with_fewer_feeds_drops_stale_feed_rows(conn, sample_run, rules):
    # 처음: 피드 3개(A 성공, B 성공, C 실패). 같은 구간을 피드 A만으로 다시 실행한다(피드를 빼거나 이름을 바꾼 뒤 backfill)
    first_feed = sample_run.feeds[0]
    failed = outcome_for(feed_spec("yna", "경제"), 0, error="HTTP 500 Internal Server Error")
    load_run(conn, replace(sample_run, feeds=[*sample_run.feeds, failed]), rules)
    assert len(feed_rows(conn)) == 3

    only_first = replace(
        sample_run,
        items=[item for item in sample_run.items if item.feed == first_feed.feed],
        feeds=[first_feed],
    )
    load_run(conn, only_first, rules)

    # 그 입력으로 처음 실행한 것과 같은 상태: A 행만 남고 실행 행의 피드 수도 맞는다
    # (A의 기사는 이 구간에서 처음 봤으므로 다시 실행해도 새 기사다 → SUCCESS)
    assert set(feed_rows(conn)) == {(first_feed.feed.source, first_feed.feed.feed)}
    record = run_row(conn)
    assert (record["feed_count"], record["failed_feed_count"], record["outcome"]) == (1, 0, "SUCCESS")


def test_outcome_partial_failure_when_some_feeds_failed(conn, sample_run, rules):
    failed = outcome_for(feed_spec("yna", "경제"), 0, error="HTTP 500 Internal Server Error")
    run = replace(sample_run, feeds=[*sample_run.feeds, failed])

    stats = load_run(conn, run, rules)

    assert stats.outcome == "PARTIAL_FAILURE"
    assert stats.new_articles == len(loadable_keys(sample_run))
    record = run_row(conn)
    assert (record["outcome"], record["feed_count"], record["failed_feed_count"]) == ("PARTIAL_FAILURE", 3, 1)
    economy = feed_rows(conn)[("yna", "economy")]
    assert (economy["http_status"], economy["item_count"]) == (None, 0)
    assert economy["error"] == "HTTP 500 Internal Server Error"


def test_outcome_failure_when_all_feeds_failed(conn, rules):
    long_error = "연결 실패 " * 1000  # 6000자, 1만 4천 바이트: 열 한도에 맞춰 잘린다
    run = RunLoadInput(
        interval_end=INTERVAL_END,
        run_type="backfill",
        items=[],
        feeds=[
            outcome_for(feed_spec("yna", "정치"), 0, error=long_error),
            outcome_for(feed_spec("khan", "정치"), 0, error="raw_missing"),
        ],
    )

    stats = load_run(conn, run, rules)

    assert stats == LoadStats(
        new_articles=0,
        existing_articles=0,
        inserted_articles=0,
        excluded_notice=0,
        excluded_blocklist=0,
        keyword_rows=0,
        outcome="FAILURE",
    )
    record = run_row(conn)
    assert (record["outcome"], record["run_type"], record["failed_feed_count"]) == ("FAILURE", "backfill", 2)
    stored = feed_rows(conn)[("yna", "politics")]["error"]
    assert long_error.startswith(stored) and len(stored.encode("utf-8")) <= 4000 and len(stored) > 1000


def _mismatched_count(run: RunLoadInput) -> RunLoadInput:
    first = run.feeds[0]
    return replace(run, feeds=[replace(first, item_count=first.item_count + 1), *run.feeds[1:]])


def _unknown_feed(run: RunLoadInput) -> RunLoadInput:
    return replace(run, feeds=run.feeds[1:])


def _naive_fetched_at(run: RunLoadInput) -> RunLoadInput:
    first = run.feeds[0]
    return replace(run, feeds=[replace(first, fetched_at=datetime(2026, 11, 4, 3, 0, 2)), *run.feeds[1:]])


@pytest.mark.parametrize(
    "broken",
    [
        pytest.param(_mismatched_count, id="item_count-mismatch"),
        pytest.param(_unknown_feed, id="item-feed-not-in-feeds"),
        pytest.param(_naive_fetched_at, id="naive-fetched_at"),
        pytest.param(lambda run: replace(run, feeds=[], items=[]), id="no-feeds"),
        pytest.param(lambda run: replace(run, run_type="hourly"), id="bad-run-type"),
    ],
)
def test_invalid_input_raises_value_error_and_writes_nothing(conn, sample_run, rules, broken):
    with pytest.raises(ValueError):
        load_run(conn, broken(sample_run), rules)

    assert counts(conn) == {table: 0 for table in V2_TABLES} | {"keyword_rule_versions": 1}


def test_ensure_rule_version_active_then_building_then_existing(conn, rule_set):
    other = replace(rule_set, stopwords=rule_set.stopwords | {"테스트불용어"})
    assert other.version != rule_set.version

    assert ensure_rule_version(conn, rule_set) == "ACTIVE"
    assert ensure_rule_version(conn, other) == "BUILDING"
    assert ensure_rule_version(conn, rule_set) == "ACTIVE"
    assert ensure_rule_version(conn, other) == "BUILDING"
    assert counts(conn)["keyword_rule_versions"] == 2
    assert writable_rule_sets(conn) == {rule_set.version: rule_set, other.version: other}

    # ACTIVE는 하나만: 함수 기반 유니크 인덱스가 막는다
    with pytest.raises(oracledb.IntegrityError, match="ORA-00001"):
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE keyword_rule_versions SET status = 'ACTIVE' WHERE rule_version = :v", v=other.version
            )
    conn.rollback()

    # RETIRED는 쓰기 대상이 아니다
    with conn.cursor() as cursor:
        cursor.execute("UPDATE keyword_rule_versions SET status = 'RETIRED' WHERE rule_version = :v", v=other.version)
    conn.commit()
    assert writable_rule_sets(conn) == {rule_set.version: rule_set}
    assert ensure_rule_version(conn, other) == "RETIRED"


def test_keywords_need_a_registered_rule_version(conn, rule_set: RuleSet):
    # news_keywords.rule_version은 keyword_rule_versions를 참조한다: 등록하지 않은 버전으로는 쓸 수 없다
    politics = feed_spec("yna", "정치")
    run = RunLoadInput(
        interval_end=INTERVAL_END,
        run_type="manual",
        items=[article(politics, "AKR20261104001100011", "국회 예산안 처리 합의")],
        feeds=[outcome_for(politics, 1)],
    )

    with pytest.raises(oracledb.IntegrityError, match="ORA-02291"):
        load_run(conn, run, {rule_set.version: rule_set})

    assert counts(conn) == {table: 0 for table in V2_TABLES}


def test_writable_rule_sets_rejects_mismatched_version(conn, rule_set: RuleSet):
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO keyword_rule_versions (rule_version, rule_json, status)"
            " VALUES ('deadbeef', :rule_json, 'ACTIVE')",
            rule_json=rule_set.to_json(),
        )
    conn.commit()

    with pytest.raises(ValueError, match="deadbeef"):
        writable_rule_sets(conn)
