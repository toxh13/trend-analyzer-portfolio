import dataclasses
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from trend_pipeline import __version__
from trend_pipeline.envelope import (
    CRAWLER_VERSION,
    ENVELOPE_VERSION,
    Envelope,
    build_envelope,
    from_bytes,
    to_bytes,
)
from trend_pipeline.feeds import FeedSpec

SPEC = FeedSpec(source="yna", feed="politics", category="정치", url="https://example.com/rss/politics.xml")
AT = datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)
KST = timezone(timedelta(hours=9))
BODY = '<?xml version="1.0" encoding="UTF-8"?><rss><channel><title>정치</title></channel></rss>'
HEADERS = {
    "ETag": '"abc123"',
    "Last-Modified": "Wed, 04 Nov 2026 02:55:00 GMT",
    "Content-Type": "application/rss+xml; charset=utf-8",
}


def ok_envelope() -> Envelope:
    return build_envelope(SPEC, AT, 200, HEADERS, BODY)


def test_constants():
    assert ENVELOPE_VERSION == 1
    assert CRAWLER_VERSION == __version__


def test_build_200_fills_all_fields():
    env = ok_envelope()
    assert env.envelope_version == ENVELOPE_VERSION
    assert env.source == "yna"
    assert env.feed == "politics"
    assert env.request_url == SPEC.url
    assert env.requested_at == AT
    assert env.crawler_version == CRAWLER_VERSION
    assert env.status == 200
    assert env.etag == '"abc123"'
    assert env.last_modified == "Wed, 04 Nov 2026 02:55:00 GMT"
    assert env.content_type == "application/rss+xml; charset=utf-8"
    assert env.body == BODY


def test_build_200_body_sha256_is_hash_of_utf8_body():
    env = ok_envelope()
    assert env.body_sha256 == hashlib.sha256(BODY.encode()).hexdigest()


def test_round_trip_200():
    env = ok_envelope()
    assert from_bytes(to_bytes(env)) == env


def test_build_304_has_no_body_and_no_hash():
    env = build_envelope(SPEC, AT, 304, {"ETag": '"abc123"'}, None)
    assert env.status == 304
    assert env.body is None
    assert env.body_sha256 is None
    assert env.etag == '"abc123"'


def test_build_304_drops_empty_string_body():
    env = build_envelope(SPEC, AT, 304, {}, "")
    assert env.body is None
    assert env.body_sha256 is None


def test_round_trip_304():
    env = build_envelope(SPEC, AT, 304, {}, None)
    assert from_bytes(to_bytes(env)) == env


@pytest.mark.parametrize("status", [201, 204, 301, 302, 400, 403, 404, 429, 500, 503])
def test_build_rejects_status_other_than_200_and_304(status):
    with pytest.raises(ValueError):
        build_envelope(SPEC, AT, status, HEADERS, BODY)


def test_build_200_without_body_is_rejected():
    with pytest.raises(ValueError):
        build_envelope(SPEC, AT, 200, HEADERS, None)


def test_build_200_with_empty_body_is_kept():
    # 빈 본문도 200이면 그대로 보존한다 (파싱 단계가 판단한다)
    env = build_envelope(SPEC, AT, 200, HEADERS, "")
    assert env.body == ""
    assert env.body_sha256 == hashlib.sha256(b"").hexdigest()


def test_headers_are_read_case_insensitively():
    headers = {"etag": '"e1"', "LAST-MODIFIED": "Mon, 02 Nov 2026 00:00:00 GMT", "content-TYPE": "text/xml"}
    env = build_envelope(SPEC, AT, 200, headers, BODY)
    assert env.etag == '"e1"'
    assert env.last_modified == "Mon, 02 Nov 2026 00:00:00 GMT"
    assert env.content_type == "text/xml"


def test_missing_headers_become_none():
    env = build_envelope(SPEC, AT, 200, {}, BODY)
    assert env.etag is None
    assert env.last_modified is None
    assert env.content_type is None


def test_requested_at_naive_is_rejected():
    with pytest.raises(ValueError):
        build_envelope(SPEC, datetime(2026, 11, 4, 3), 200, HEADERS, BODY)


def test_requested_at_is_stored_in_utc():
    kst = datetime(2026, 11, 4, 12, 0, tzinfo=KST)
    env = build_envelope(SPEC, kst, 200, HEADERS, BODY)
    assert env.requested_at == kst
    assert env.requested_at.utcoffset() == timedelta(0)
    assert json.loads(to_bytes(env))["requested_at"] == "2026-11-04T03:00:00+00:00"


def test_from_bytes_restores_aware_utc_datetime():
    kst = datetime(2026, 11, 4, 12, 0, tzinfo=KST)
    restored = from_bytes(to_bytes(build_envelope(SPEC, kst, 200, HEADERS, BODY)))
    assert restored.requested_at == kst
    assert restored.requested_at.tzinfo is not None
    assert restored.requested_at.utcoffset() == timedelta(0)


def test_same_input_gives_same_bytes():
    assert to_bytes(ok_envelope()) == to_bytes(ok_envelope())


def test_to_bytes_is_sorted_utf8_json_without_ascii_escaping():
    data = to_bytes(ok_envelope())
    assert "정치".encode() in data
    assert b"\\u" not in data
    assert list(json.loads(data)) == sorted(json.loads(data))


def test_to_bytes_has_all_envelope_fields():
    keys = set(json.loads(to_bytes(ok_envelope())))
    assert keys == {field.name for field in dataclasses.fields(Envelope)}


def test_from_bytes_rejects_unknown_envelope_version():
    payload = json.loads(to_bytes(ok_envelope()))
    payload["envelope_version"] = ENVELOPE_VERSION + 1
    with pytest.raises(ValueError):
        from_bytes(json.dumps(payload).encode("utf-8"))


def test_envelope_is_frozen():
    env = ok_envelope()
    with pytest.raises(dataclasses.FrozenInstanceError):
        env.status = 304
