"""피드 하나·구간 하나의 수집 단계. 원본은 한 번만 쓰고(write-once) 처리는 그 원본으로 여러 번 한다."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from trend_pipeline.article_key import article_key
from trend_pipeline.envelope import build_envelope, to_bytes
from trend_pipeline.feeds import FeedSpec
from trend_pipeline.http_fetch import FetchError, FetchResult
from trend_pipeline.keys import raw_key
from trend_pipeline.parse import FeedParseError, parse_feed
from trend_pipeline.quality import QualityReport, check_items
from trend_pipeline.raw_store import RawStore

_RUN_TYPES = frozenset({"scheduled", "backfill", "manual"})

# 요청해서 저장하는 실행(scheduled·manual)이 받는 구간: 지금 − MAX_LATENESS ≤ interval_end ≤ 지금 + FUTURE_ALLOWANCE.
# 받은 피드는 그 구간 이름으로 한 번만 저장되므로, 지난 구간을 받으면 지금 피드가 옛 구간 원본으로 굳는다.
# 늦음 허용 1시간은 측정값이 아닌 임시값이다(재시도·조금 늦은 실행만 허용). 그보다 지난 구간은 백필로만 처리한다
MAX_LATENESS = timedelta(hours=1)
FUTURE_ALLOWANCE = timedelta(minutes=5)  # 시계 차이와 조금 이른 시작을 허용한다


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def collect_window_error(interval_end: datetime, now: datetime) -> str | None:
    """요청해서 이 구간 이름으로 저장해도 되는지 본다. 안 되면 이유를, 되면 None을 돌려준다."""
    if interval_end < now - MAX_LATENESS:
        return f"too_late: interval_end {interval_end.isoformat()}는 지금보다 {MAX_LATENESS} 넘게 지났다(백필로만 처리)"
    if interval_end > now + FUTURE_ALLOWANCE:
        return f"too_early: interval_end {interval_end.isoformat()}는 지금 + {FUTURE_ALLOWANCE}보다 늦다"
    return None


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
    *,
    clock: Callable[[], datetime] | None = None,
) -> CollectResult:
    """원본이 없을 때만 요청해서 봉투로 저장한다.

    요청은 구간이 지금 기준 수집 범위 안일 때만 한다(collect_window_error). 범위 밖이면 요청하지 않고 failed로 돌려준다.
    검사를 호출하는 쪽(CLI·DAG)이 아니라 여기 두고, 지금 시각도 호출자에게 받지 않고 실제 시계로 읽는다.
    (DAG가 논리 시각 data_interval_end를 '지금'으로 넘기면 지난 구간도 늘 범위 안이 된다)
    clock은 테스트가 시계를 바꿔 끼우는 자리다.
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

    window_error = collect_window_error(interval_end, (clock or _utc_now)())
    if window_error is not None:
        return CollectResult(spec, None, "failed", None, None, window_error)

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
