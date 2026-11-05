"""피드 하나·구간 하나의 수집 단계. 원본은 한 번만 쓰고(write-once) 처리는 그 원본으로 여러 번 한다."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from trend_pipeline.article_key import article_key
from trend_pipeline.envelope import build_envelope, to_bytes
from trend_pipeline.feeds import FeedSpec
from trend_pipeline.http_fetch import FetchError, FetchResult
from trend_pipeline.keys import raw_key
from trend_pipeline.parse import FeedParseError, parse_feed
from trend_pipeline.quality import QualityReport, check_items
from trend_pipeline.raw_store import RawStore

_RUN_TYPES = frozenset({"scheduled", "backfill", "manual"})


@dataclass(frozen=True)
class CollectResult:
    feed: FeedSpec
    raw_key: str | None  # 원본이 저장소에 있으면 그 키, 없으면 None
    action: str  # fetched | skipped_exists | skipped_backfill | missing_in_backfill | failed
    status: int | None  # fetched는 200/304, failed는 HTTP 상태(없으면 None), skipped_*는 None
    quality: QualityReport | None  # 기록용. 파싱 실패나 요청하지 않은 경우 None
    error: str | None


def collect_feed(
    spec: FeedSpec,
    interval_end: datetime,
    run_type: str,
    store: RawStore,
    validators: tuple[str | None, str | None],
    fetch: Callable[..., FetchResult],
) -> CollectResult:
    """원본이 없을 때만 요청해서 봉투로 저장한다.

    FetchError는 failed 결과로 바꾼다. 기록용 단계(파싱·기사 키·품질 검사)의 오류는 원본 저장을 막지 않고
    error에만 남긴다. 그 밖의 예외(요청 함수·저장소 오류 등)는 삼키지 않고 올린다.
    """
    if run_type not in _RUN_TYPES:
        raise ValueError(f"알 수 없는 run_type: {run_type!r}")

    key = raw_key(interval_end, spec.source, spec.feed)
    exists = store.exists(key)

    if run_type == "backfill":
        # 백필은 요청하지 않는다. 있는 원본만 쓰고, 없으면 없다고만 알린다
        if exists:
            return CollectResult(spec, key, "skipped_backfill", None, None, None)
        return CollectResult(spec, None, "missing_in_backfill", None, None, None)

    if exists:
        return CollectResult(spec, key, "skipped_exists", None, None, None)

    etag, last_modified = validators
    try:
        fetched = fetch(spec, etag=etag, last_modified=last_modified)
    except FetchError as exc:
        # 실패는 실행 기록에만 남기고 원본은 저장하지 않는다
        return CollectResult(spec, None, "failed", exc.status, None, str(exc))

    env = build_envelope(spec, fetched.requested_at, fetched.status, fetched.headers, fetched.body)

    # 품질 검사는 기록만 한다. 파싱이 깨지거나 이 단계에 버그가 있어도 원본은 저장한다(나중에 재처리할 수 있게)
    quality: QualityReport | None = None
    error: str | None = None
    try:
        items = parse_feed(env).items
        quality = check_items([(article_key(spec.source, i.link, i.guid), i) for i in items])
    except FeedParseError as exc:
        error = f"FeedParseError: {exc}"
    except Exception as exc:  # 기록용 단계라 어떤 오류도 원본 저장을 막지 않는다
        error = f"{type(exc).__name__}: {exc}"

    if not store.put_if_absent(key, to_bytes(env)):
        # 다른 작성자가 먼저 썼다. 먼저 쓴 원본이 그대로 남는다
        return CollectResult(spec, key, "skipped_exists", None, None, None)

    return CollectResult(spec, key, "fetched", fetched.status, quality, error)
