from datetime import datetime, timezone
from pathlib import Path

import pytest

from trend_pipeline.collect import CollectResult, collect_feed
from trend_pipeline.envelope import from_bytes
from trend_pipeline.feeds import FeedSpec
from trend_pipeline.http_fetch import FetchError, FetchResult
from trend_pipeline.keys import raw_key
from trend_pipeline.raw_store import LocalRawStore

FIXTURES = Path(__file__).parent.parent / "fixtures" / "feeds"
SPEC = FeedSpec(source="yna", feed="yna_politics", category="정치", url="https://example.com/politics.xml")
INTERVAL_END = datetime(2026, 11, 5, 3, 0, tzinfo=timezone.utc)
REQUESTED_AT = datetime(2026, 11, 5, 3, 0, 2, tzinfo=timezone.utc)
KEY = raw_key(INTERVAL_END, SPEC.source, SPEC.feed)
NO_VALIDATORS = (None, None)


class FakeFetch:
    """호출을 기록하고 정해 둔 결과(또는 예외)를 돌려주는 가짜 fetch."""

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def __call__(self, spec, **kwargs):
        self.calls.append((spec, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


def ok(body, headers=None):
    return FetchResult(status=200, headers=headers or {}, body=body, requested_at=REQUESTED_AT, attempts=1)


def collect(store, fetch, run_type="scheduled", validators=NO_VALIDATORS, spec=SPEC):
    return collect_feed(spec, INTERVAL_END, run_type, store, validators, fetch)


@pytest.fixture
def store(tmp_path):
    return LocalRawStore(tmp_path)


def test_backfill_never_calls_fetch(store):
    fetch = FakeFetch(result=ok("<rss/>"))
    result = collect(store, fetch, run_type="backfill")
    assert fetch.calls == []
    assert result == CollectResult(SPEC, None, "missing_in_backfill", None, None, None)
    assert store.list_keys("") == []


def test_backfill_existing_raw_is_skipped(store):
    store.put_if_absent(KEY, b"old")
    fetch = FakeFetch()
    result = collect(store, fetch, run_type="backfill")
    assert fetch.calls == []
    assert result == CollectResult(SPEC, KEY, "skipped_backfill", None, None, None)


@pytest.mark.parametrize("run_type", ["scheduled", "manual"])
def test_existing_raw_skips_fetch(store, run_type):
    store.put_if_absent(KEY, b"old")
    fetch = FakeFetch()
    result = collect(store, fetch, run_type=run_type)
    assert fetch.calls == []
    assert result == CollectResult(SPEC, KEY, "skipped_exists", None, None, None)
    assert store.get(KEY) == b"old"


def test_manual_fetches_like_scheduled(store):
    fetch = FakeFetch(result=ok("<rss><channel></channel></rss>"))
    result = collect(store, fetch, run_type="manual")
    assert result.action == "fetched"
    assert len(fetch.calls) == 1
    assert store.exists(KEY)


def test_validators_passed_to_fetch(store):
    fetch = FakeFetch(result=ok("<rss><channel></channel></rss>"))
    collect(store, fetch, validators=('"abc"', "Wed, 05 Nov 2026 02:00:00 GMT"))
    spec, kwargs = fetch.calls[0]
    assert spec == SPEC
    assert kwargs == {"etag": '"abc"', "last_modified": "Wed, 05 Nov 2026 02:00:00 GMT"}


def test_304_saves_bodyless_envelope(store):
    fetch = FakeFetch(
        result=FetchResult(status=304, headers={"ETag": '"abc"'}, body=None, requested_at=REQUESTED_AT, attempts=1)
    )
    result = collect(store, fetch, validators=('"abc"', None))
    assert result.action == "fetched"
    assert result.status == 304
    assert result.raw_key == KEY
    assert result.error is None
    env = from_bytes(store.get(KEY))
    assert env.status == 304
    assert env.body is None
    assert env.body_sha256 is None


def test_fetch_error_saves_nothing(store):
    fetch = FakeFetch(error=FetchError("HTTP 503", status=503, attempts=3))
    result = collect(store, fetch)
    assert result == CollectResult(SPEC, None, "failed", 503, None, "HTTP 503")
    assert store.list_keys("") == []


def test_fetch_error_without_status(store):
    fetch = FakeFetch(error=FetchError("connection reset", status=None, attempts=3))
    result = collect(store, fetch)
    assert result.action == "failed"
    assert result.status is None
    assert result.error == "connection reset"


def test_broken_xml_is_still_saved_and_reported(store):
    fetch = FakeFetch(result=ok("<rss><channel><item>"))
    result = collect(store, fetch)
    assert result.action == "fetched"
    assert result.raw_key == KEY
    assert result.status == 200
    assert result.quality is None
    assert result.error is not None and result.error.startswith("FeedParseError: ")
    assert from_bytes(store.get(KEY)).body == "<rss><channel><item>"


def test_200_bytes_round_trip_to_fetched_body(store):
    body = (FIXTURES / "yna_politics.xml").read_text(encoding="utf-8")
    fetch = FakeFetch(result=ok(body, {"ETag": '"v1"'}))
    result = collect(store, fetch)
    env = from_bytes(store.get(KEY))
    assert env.body == body
    assert env.status == 200
    assert env.etag == '"v1"'
    assert env.requested_at == REQUESTED_AT
    assert result.raw_key == KEY


def test_quality_counts_for_fixture_feed(store):
    body = (FIXTURES / "yna_politics.xml").read_text(encoding="utf-8")
    result = collect(store, FakeFetch(result=ok(body)))
    assert result.action == "fetched"
    assert result.error is None
    assert result.quality is not None
    assert result.quality.item_count == 120


def test_lost_race_keeps_first_writer(store, monkeypatch):
    fetch = FakeFetch(result=ok("<rss><channel></channel></rss>"))
    real_put = store.put_if_absent

    def racing_put(key, data):
        real_put(key, b"winner")  # 다른 작성자가 먼저 쓴다
        return real_put(key, data)

    monkeypatch.setattr(store, "put_if_absent", racing_put)
    result = collect(store, fetch)
    assert result == CollectResult(SPEC, KEY, "skipped_exists", None, None, None)
    assert store.get(KEY) == b"winner"


def test_invalid_run_type(store):
    fetch = FakeFetch()
    with pytest.raises(ValueError):
        collect(store, fetch, run_type="weekly")
    assert fetch.calls == []


def test_non_fetch_errors_propagate(store):
    with pytest.raises(OSError):
        collect(store, FakeFetch(error=OSError("disk")))
