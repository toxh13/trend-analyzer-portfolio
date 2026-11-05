"""한 구간의 저장된 원본을 읽어 실버 테이블에 적재하는 처리 작업.

원본 저장소에 있는 봉투가 진실이다(수집 결과가 아니라). 그래서 백필(재처리)도 같은 코드로 돈다.
피드마다 읽기·파싱에 실패해도 그 피드만 오류로 기록하고 나머지는 계속 적재한다.
"""

from collections.abc import Sequence
from datetime import datetime

import oracledb

from trend_pipeline.article_key import article_key, display_link
from trend_pipeline.collect import CollectResult
from trend_pipeline.envelope import Envelope, from_bytes
from trend_pipeline.feeds import FeedSpec, load_feeds
from trend_pipeline.keys import raw_key
from trend_pipeline.keywords import load_rules
from trend_pipeline.load import (
    FeedOutcome,
    LoadItem,
    LoadStats,
    RunLoadInput,
    ensure_rule_version,
    load_run,
    writable_rule_sets,
)
from trend_pipeline.parse import FeedParseError, parse_feed
from trend_pipeline.quality import check_items
from trend_pipeline.raw_store import RawStore
from trend_pipeline.text_clean import clean_summary, clean_title


def process_interval(
    interval_end: datetime,
    run_type: str,
    store: RawStore,
    conn: oracledb.Connection,
    collect_results: Sequence[CollectResult],
) -> LoadStats:
    """구간 하나의 원본(feeds.yml 순서)을 읽어 load_run으로 적재하고 통계를 돌려준다."""
    rules = load_rules()
    ensure_rule_version(conn, rules)
    rule_sets = writable_rule_sets(conn)
    if conn.transaction_in_progress:
        conn.rollback()  # load_run은 열린 트랜잭션이 있으면 거부한다. 읽기만 했으므로 버려도 된다

    collected = {(result.feed.source, result.feed.feed): result for result in collect_results}
    items: list[LoadItem] = []
    outcomes: list[FeedOutcome] = []
    for spec in load_feeds():
        feed_items, outcome = _process_feed(spec, interval_end, store, collected.get((spec.source, spec.feed)))
        items.extend(feed_items)
        outcomes.append(outcome)

    return load_run(conn, RunLoadInput(interval_end, run_type, items, outcomes), rule_sets)


def _process_feed(
    spec: FeedSpec, interval_end: datetime, store: RawStore, collected: CollectResult | None
) -> tuple[list[LoadItem], FeedOutcome]:
    key = raw_key(interval_end, spec.source, spec.feed)
    if not store.exists(key):
        # 원본이 없으면 수집 단계가 남긴 실패 이유를 쓰고, 그것도 없으면 원본이 없다고만 적는다
        if collected is not None and collected.action == "failed":
            return [], _failed(spec, collected.error or "failed", status=collected.status)
        return [], _failed(spec, "raw_missing")

    try:
        env = from_bytes(store.get(key))
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        return [], _failed(spec, f"EnvelopeError: {exc}", key=key)

    try:
        parsed = parse_feed(env)
    except FeedParseError as exc:
        return [], _failed(spec, f"FeedParseError: {exc}", key=key, env=env)

    keyed = [(article_key(spec.source, item.link, item.guid), item) for item in parsed.items]
    items = [
        LoadItem(
            feed=spec,
            key=item_key,
            title=item.title,  # 파싱한 원래 제목. 정리·키워드는 load_run이 저장된 제목으로 한다
            summary=clean_summary(item.summary),
            link=display_link(spec.source, item.link, item.guid),
            published_at=item.published_at,
            title_excluded=clean_title(item.title).excluded,
        )
        for item_key, item in keyed
    ]
    # 품질은 수집 때 남긴 값을 믿지 않고 여기서 다시 계산한다(백필에도 기록되게)
    quality = check_items(keyed)
    outcome = FeedOutcome(
        feed=spec,
        status=env.status,
        etag=env.etag,
        last_modified=env.last_modified,
        raw_key=key,
        fetched_at=env.requested_at,  # 봉투를 읽었으면(200·304) 그 요청 시각
        item_count=len(items),
        parse_failed=parsed.parse_failed,
        missing_required=quality.missing_required,
        duplicate_keys=quality.duplicate_keys,
        error=None,
    )
    return items, outcome


def _failed(
    spec: FeedSpec, error: str, *, status: int | None = None, key: str | None = None, env: Envelope | None = None
) -> FeedOutcome:
    """실패한 피드의 결과. 봉투를 읽었으면(파싱 실패) 상태·validator·요청 시각은 봉투 값을 쓴다."""
    return FeedOutcome(
        feed=spec,
        status=env.status if env is not None else status,
        etag=env.etag if env is not None else None,
        last_modified=env.last_modified if env is not None else None,
        raw_key=key,
        fetched_at=env.requested_at if env is not None else None,
        item_count=0,
        parse_failed=0,
        missing_required=0,
        duplicate_keys=0,
        error=error,
    )
