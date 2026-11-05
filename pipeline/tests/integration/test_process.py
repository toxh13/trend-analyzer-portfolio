"""처리 작업(process_interval) 통합 테스트: 원본 저장소 → 실버 테이블, 피드별 결과 기록, 재처리 멱등."""

import oracledb
import pytest

from trend_pipeline.collect import CollectResult
from trend_pipeline.envelope import build_envelope, to_bytes
from trend_pipeline.feeds import load_feeds
from trend_pipeline.keys import raw_key
from trend_pipeline.process import process_interval

from conftest import INTERVAL_END, V2_TABLES

pytestmark = pytest.mark.integration


def scalar(conn: oracledb.Connection, sql: str, **binds):
    with conn.cursor() as cursor:
        cursor.execute(sql, binds)
        return cursor.fetchone()[0]


def table_counts(conn: oracledb.Connection) -> dict[str, int]:
    return {table: scalar(conn, f"SELECT COUNT(*) FROM {table}") for table in V2_TABLES}


def feed_run(conn: oracledb.Connection, source: str, feed: str) -> tuple:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT http_status, item_count, error, raw_key FROM pipeline_feed_runs WHERE source = :s AND feed = :f",
            s=source,
            f=feed,
        )
        return cursor.fetchone()


def key_of(source: str, feed: str) -> str:
    return raw_key(INTERVAL_END, source, feed)


def spec_of(source: str, feed: str):
    return next(s for s in load_feeds() if (s.source, s.feed) == (source, feed))


def test_process_fixture_interval_loads_articles_and_keywords(conn, seeded_store):
    stats = process_interval(INTERVAL_END, "backfill", seeded_store, conn, [])

    assert stats.outcome == "SUCCESS"
    assert stats.new_articles > 0
    assert stats.keyword_rows > 0
    assert stats.excluded_notice > 0
    assert scalar(conn, "SELECT COUNT(*) FROM news_articles") == stats.new_articles
    assert scalar(conn, "SELECT COUNT(*) FROM news_keywords") == stats.keyword_rows
    assert scalar(conn, "SELECT COUNT(*) FROM pipeline_feed_runs") == 17
    assert scalar(conn, "SELECT COUNT(*) FROM pipeline_feed_runs WHERE error IS NOT NULL") == 0
    assert scalar(conn, "SELECT COUNT(*) FROM pipeline_feed_runs WHERE raw_key IS NULL") == 0
    assert not conn.transaction_in_progress


def test_reprocessing_same_interval_is_idempotent(conn, seeded_store):
    first = process_interval(INTERVAL_END, "backfill", seeded_store, conn, [])
    before = table_counts(conn)

    second = process_interval(INTERVAL_END, "backfill", seeded_store, conn, [])

    assert table_counts(conn) == before
    assert before["pipeline_feed_runs"] == 17
    assert before["pipeline_runs"] == 1
    assert second.new_articles == 0
    assert second.existing_articles == first.new_articles
    assert second.keyword_rows == first.keyword_rows


def test_304_only_interval_loads_zero_articles_and_outcome_is_empty(conn, store):
    for spec in load_feeds():
        env = build_envelope(spec, INTERVAL_END, 304, {"ETag": '"same"'}, None)
        store.put_if_absent(key_of(spec.source, spec.feed), to_bytes(env))

    stats = process_interval(INTERVAL_END, "backfill", store, conn, [])

    assert stats.outcome == "EMPTY"
    assert stats.new_articles == 0
    assert scalar(conn, "SELECT COUNT(*) FROM news_articles") == 0
    assert scalar(conn, "SELECT COUNT(*) FROM pipeline_feed_runs") == 17
    assert scalar(conn, "SELECT COUNT(*) FROM pipeline_feed_runs WHERE http_status = 304 AND item_count = 0") == 17
    assert scalar(conn, "SELECT COUNT(*) FROM pipeline_feed_runs WHERE error IS NOT NULL") == 0


def test_missing_raw_feed_is_recorded_as_raw_missing(conn, seeded_store):
    seeded_store.delete_prefix(key_of("khan", "kh_world"))

    stats = process_interval(INTERVAL_END, "backfill", seeded_store, conn, [])

    assert stats.outcome == "PARTIAL_FAILURE"
    assert feed_run(conn, "khan", "kh_world") == (None, 0, "raw_missing", None)
    assert scalar(conn, "SELECT COUNT(*) FROM pipeline_feed_runs WHERE error IS NOT NULL") == 1


def test_broken_xml_feed_errors_while_others_still_load(conn, seeded_store):
    key = key_of("yna", "economy")
    seeded_store.delete_prefix(key)
    broken = build_envelope(spec_of("yna", "economy"), INTERVAL_END, 200, {"ETag": '"x"'}, "<rss><channel><item>")
    assert seeded_store.put_if_absent(key, to_bytes(broken))

    stats = process_interval(INTERVAL_END, "backfill", seeded_store, conn, [])

    assert stats.outcome == "PARTIAL_FAILURE"
    assert stats.new_articles > 0
    status, item_count, error, stored_key = feed_run(conn, "yna", "economy")
    assert status == 200 and item_count == 0 and stored_key == key
    assert error.startswith("FeedParseError: ")
    assert scalar(conn, "SELECT COUNT(*) FROM pipeline_feed_runs WHERE error IS NOT NULL") == 1


def test_unreadable_envelope_is_recorded_as_envelope_error(conn, seeded_store):
    key = key_of("donga", "science")
    seeded_store.delete_prefix(key)
    assert seeded_store.put_if_absent(key, b"not json at all")

    stats = process_interval(INTERVAL_END, "backfill", seeded_store, conn, [])

    assert stats.outcome == "PARTIAL_FAILURE"
    _, item_count, error, _ = feed_run(conn, "donga", "science")
    assert item_count == 0 and error.startswith("EnvelopeError: ")


def test_failed_collect_result_without_raw_records_its_error(conn, seeded_store):
    seeded_store.delete_prefix(key_of("donga", "culture"))
    failed = CollectResult(spec_of("donga", "culture"), None, "failed", 503, None, "HTTP 503")

    stats = process_interval(INTERVAL_END, "scheduled", seeded_store, conn, [failed])

    assert stats.outcome == "PARTIAL_FAILURE"
    assert feed_run(conn, "donga", "culture") == (503, 0, "HTTP 503", None)
