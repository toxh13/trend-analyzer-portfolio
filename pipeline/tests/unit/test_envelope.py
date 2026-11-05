import base64
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
    EnvelopeIntegrityError,
    body_text,
    build_envelope,
    from_bytes,
    to_bytes,
)
from trend_pipeline.feeds import FeedSpec

SPEC = FeedSpec(source="yna", feed="politics", category="정치", url="https://example.com/rss/politics.xml")
AT = datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)
KST = timezone(timedelta(hours=9))
TEXT = '<?xml version="1.0" encoding="UTF-8"?><rss><channel><title>정치</title></channel></rss>'
BODY = TEXT.encode("utf-8")
HEADERS = {
    "ETag": '"abc123"',
    "Last-Modified": "Wed, 04 Nov 2026 02:55:00 GMT",
    "Content-Type": "application/rss+xml; charset=utf-8",
}


def ok_envelope() -> Envelope:
    return build_envelope(SPEC, AT, 200, HEADERS, BODY)


def stored(env: Envelope) -> dict:
    return json.loads(to_bytes(env))


def v1_bytes(text: str | None, content_type: str | None = "text/xml; charset=EUC-KR") -> bytes:
    """계획 1 첫 형식(v1)으로 저장된 봉투: 디코드한 글자와 그 글자를 UTF-8로 다시 인코딩한 sha256."""
    payload = {
        "envelope_version": 1,
        "source": SPEC.source,
        "feed": SPEC.feed,
        "request_url": SPEC.url,
        "requested_at": AT.isoformat(),
        "crawler_version": "2.0.0",
        "status": 200 if text is not None else 304,
        "etag": '"v1"',
        "last_modified": None,
        "content_type": content_type,
        "body_sha256": None if text is None else hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "body": text,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")


def test_constants():
    assert ENVELOPE_VERSION == 2
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


def test_body_sha256_is_hash_of_received_bytes():
    # 디코드한 글자가 아니라 받은 바이트의 지문이라야 원본 증명이 된다
    raw = "<t>한국어</t>".encode("euc-kr")
    env = build_envelope(SPEC, AT, 200, {"Content-Type": "text/xml; charset=EUC-KR"}, raw)
    assert env.body == raw
    assert env.body_sha256 == hashlib.sha256(raw).hexdigest()


def test_round_trip_200():
    env = ok_envelope()
    assert from_bytes(to_bytes(env)) == env


@pytest.mark.parametrize("raw", ["<t>한국어</t>".encode("euc-kr"), b"<t>\xff\xfe</t>", b"\xef\xbb\xbf<rss/>"])
def test_round_trip_keeps_received_bytes_exactly(raw):
    # UTF-8이 아닌 바이트, 깨진 바이트, BOM도 받은 그대로 돌아온다(디코드는 읽는 쪽이 한다)
    env = build_envelope(SPEC, AT, 200, {}, raw)
    assert from_bytes(to_bytes(env)).body == raw


def test_stored_body_is_base64_of_received_bytes():
    payload = stored(ok_envelope())
    assert base64.b64decode(payload["body_base64"]) == BODY
    assert "body" not in payload


def test_build_304_has_no_body_and_no_hash():
    env = build_envelope(SPEC, AT, 304, {"ETag": '"abc123"'}, None)
    assert env.status == 304
    assert env.body is None
    assert env.body_sha256 is None
    assert env.etag == '"abc123"'


def test_build_304_drops_empty_body():
    env = build_envelope(SPEC, AT, 304, {}, b"")
    assert env.body is None
    assert env.body_sha256 is None


def test_round_trip_304():
    env = build_envelope(SPEC, AT, 304, {}, None)
    assert from_bytes(to_bytes(env)) == env
    assert stored(env)["body_base64"] is None


@pytest.mark.parametrize("status", [201, 204, 301, 302, 400, 403, 404, 429, 500, 503])
def test_build_rejects_status_other_than_200_and_304(status):
    with pytest.raises(ValueError):
        build_envelope(SPEC, AT, status, HEADERS, BODY)


def test_build_200_without_body_is_rejected():
    with pytest.raises(ValueError):
        build_envelope(SPEC, AT, 200, HEADERS, None)


def test_build_200_with_empty_body_is_kept():
    # 빈 본문도 200이면 그대로 보존한다 (파싱 단계가 판단한다)
    env = build_envelope(SPEC, AT, 200, HEADERS, b"")
    assert env.body == b""
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
    assert stored(env)["requested_at"] == "2026-11-04T03:00:00+00:00"


def test_from_bytes_restores_aware_utc_datetime():
    kst = datetime(2026, 11, 4, 12, 0, tzinfo=KST)
    restored = from_bytes(to_bytes(build_envelope(SPEC, kst, 200, HEADERS, BODY)))
    assert restored.requested_at == kst
    assert restored.requested_at.tzinfo is not None
    assert restored.requested_at.utcoffset() == timedelta(0)


def test_same_input_gives_same_bytes():
    assert to_bytes(ok_envelope()) == to_bytes(ok_envelope())


def test_to_bytes_is_sorted_utf8_json():
    data = to_bytes(ok_envelope())
    assert list(json.loads(data)) == sorted(json.loads(data))
    data.decode("utf-8")


def test_to_bytes_has_all_envelope_fields_with_body_as_base64():
    keys = set(stored(ok_envelope()))
    fields = {field.name for field in dataclasses.fields(Envelope)}
    assert keys == fields - {"body"} | {"body_base64"}


def test_to_bytes_refuses_envelope_read_from_older_version():
    # v1에서 읽은 봉투는 받은 바이트가 아니라 디코드한 글자라서 v2로 다시 쓰면 원본인 척하게 된다
    with pytest.raises(ValueError):
        to_bytes(from_bytes(v1_bytes("<t/>")))


# --- 읽을 때 지문 대조 ---


def test_from_bytes_rejects_body_that_does_not_match_its_hash():
    payload = stored(ok_envelope())
    payload["body_base64"] = base64.b64encode(BODY + b" ").decode("ascii")
    with pytest.raises(EnvelopeIntegrityError):
        from_bytes(json.dumps(payload).encode("utf-8"))


def test_from_bytes_rejects_hash_without_body_and_body_without_hash():
    payload = stored(build_envelope(SPEC, AT, 304, {}, None))
    payload["body_sha256"] = hashlib.sha256(b"").hexdigest()
    with pytest.raises(EnvelopeIntegrityError):
        from_bytes(json.dumps(payload).encode("utf-8"))
    payload = stored(ok_envelope())
    payload["body_sha256"] = None
    with pytest.raises(EnvelopeIntegrityError):
        from_bytes(json.dumps(payload).encode("utf-8"))


def test_from_bytes_rejects_invalid_base64():
    payload = stored(ok_envelope())
    payload["body_base64"] = "not base64!"
    with pytest.raises(ValueError):
        from_bytes(json.dumps(payload).encode("utf-8"))


def test_integrity_error_is_a_value_error():
    # 처리 단계는 ValueError를 그 피드의 EnvelopeError 실패로 기록한다
    assert issubclass(EnvelopeIntegrityError, ValueError)


def test_from_bytes_rejects_unknown_envelope_version():
    payload = stored(ok_envelope())
    payload["envelope_version"] = ENVELOPE_VERSION + 1
    with pytest.raises(ValueError):
        from_bytes(json.dumps(payload).encode("utf-8"))


@pytest.mark.parametrize("change", ["drop", "extra"])
def test_from_bytes_rejects_unexpected_fields(change):
    payload = stored(ok_envelope())
    if change == "drop":
        del payload["etag"]
    else:
        payload["body"] = TEXT  # v1 필드가 v2 봉투에 섞임
    with pytest.raises(ValueError):
        from_bytes(json.dumps(payload).encode("utf-8"))


# --- v1 봉투 읽기 ---


def test_reads_v1_envelope_as_utf8_text_regardless_of_declared_charset():
    # v1은 이미 디코드한 글자를 저장했다. 선언된 charset(EUC-KR)으로 다시 디코드하면 깨진다
    env = from_bytes(v1_bytes("<t>한국어</t>"))
    assert env.envelope_version == 1
    assert env.body == "<t>한국어</t>".encode("utf-8")
    assert body_text(env) == "<t>한국어</t>"


def test_reads_v1_304_envelope():
    env = from_bytes(v1_bytes(None))
    assert env.body is None and env.body_sha256 is None
    assert body_text(env) is None


def test_rejects_v1_envelope_whose_text_does_not_match_its_hash():
    payload = json.loads(v1_bytes("<t>한국어</t>"))
    payload["body"] = "<t>바뀐 글</t>"
    with pytest.raises(EnvelopeIntegrityError):
        from_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


# --- 본문 디코드 (처리 단계가 원본을 읽을 때) ---


def text_of(raw: bytes, content_type: str | None) -> str | None:
    headers = {} if content_type is None else {"Content-Type": content_type}
    return body_text(build_envelope(SPEC, AT, 200, headers, raw))


def test_body_text_of_304_is_none():
    assert body_text(build_envelope(SPEC, AT, 304, {}, None)) is None


def test_body_text_uses_declared_charset_euc_kr():
    text = "<title>한국어 뉴스 속보</title>"
    assert text_of(text.encode("euc-kr"), "text/xml; charset=EUC-KR") == text


def test_body_text_charset_parameter_may_be_quoted():
    text = "<title>한국어 뉴스 속보</title>"
    assert text_of(text.encode("euc-kr"), 'text/xml; charset="euc-kr"') == text


def test_body_text_without_charset_is_utf8_not_latin1():
    # requests의 response.text는 text/xml에 charset이 없으면 ISO-8859-1로 읽어 한글이 깨진다
    text = "<title>한국어 뉴스 속보</title>"
    assert text_of(text.encode("utf-8"), "text/xml") == text
    assert text_of(text.encode("utf-8"), None) == text


# 모르는 이름(LookupError), 텍스트 코덱이 아닌 이름(LookupError), 디코드하면 UnicodeError를 내는 코덱(undefined)
@pytest.mark.parametrize("charset", ["no-such-codec", "rot13", "undefined"])
def test_body_text_unknown_or_non_text_charset_falls_back_to_utf8(charset):
    text = "<title>한국어 뉴스 속보</title>"
    assert text_of(text.encode("utf-8"), f"text/xml; charset={charset}") == text


def test_body_text_replaces_undecodable_bytes():
    assert text_of(b"<t>\xff\xfe</t>", "text/xml; charset=utf-8") == "<t>��</t>"


def test_envelope_is_frozen():
    env = ok_envelope()
    with pytest.raises(dataclasses.FrozenInstanceError):
        env.status = 304
