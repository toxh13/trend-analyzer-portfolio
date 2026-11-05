import random
from datetime import datetime, timedelta, timezone

import pytest
import requests
from requests.structures import CaseInsensitiveDict

from trend_pipeline import http_fetch
from trend_pipeline.envelope import build_envelope
from trend_pipeline.feeds import FeedSpec
from trend_pipeline.http_fetch import (
    REQUEST_TIMEOUT,
    USER_AGENT,
    FetchError,
    FetchResult,
    RetryPolicy,
    fetch_feed,
)

SPEC = FeedSpec(source="khan", feed="kh_world", category="세계", url="https://example.com/rss/world.xml")
T0 = datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)
BODY = '<?xml version="1.0" encoding="UTF-8"?><rss><channel><title>세계</title></channel></rss>'


def make_response(status=200, headers=None, content=b""):
    # 실제 requests.Response를 만들어 헤더 대소문자 무시 동작까지 그대로 쓴다
    response = requests.Response()
    response.status_code = status
    response.headers = CaseInsensitiveDict(headers or {})
    response._content = content
    return response


class FakeSession:
    """미리 정해 둔 결과(Response 또는 예외)를 순서대로 돌려주는 가짜 세션. 네트워크를 쓰지 않는다."""

    def __init__(self, *outcomes):
        self._outcomes = list(outcomes)
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": dict(headers or {}), "timeout": timeout})
        if not self._outcomes:
            raise AssertionError("준비한 결과보다 많이 요청했다")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeClock:
    """호출할 때마다 1초씩 늘어나는 시각을 돌려준다."""

    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return T0 + timedelta(seconds=self.calls - 1)


def run(session, *, etag=None, last_modified=None, policy=RetryPolicy(), clock=None):
    waits = []
    result = fetch_feed(
        SPEC,
        etag=etag,
        last_modified=last_modified,
        session=session,
        policy=policy,
        sleep=waits.append,
        clock=clock or FakeClock(),
    )
    return result, waits


def run_failing(session, *, policy=RetryPolicy(), clock=None):
    waits = []
    with pytest.raises(FetchError) as info:
        fetch_feed(
            SPEC,
            etag=None,
            last_modified=None,
            session=session,
            policy=policy,
            sleep=waits.append,
            clock=clock or FakeClock(),
        )
    return info.value, waits


# --- 상수·정책 ---


def test_user_agent_constant_matches_global_constraint():
    assert USER_AGENT == "TrendAnalyzerBot/2.0 (+https://github.com/toxh13/trend-analyzer-portfolio)"


def test_request_timeout_is_connect_and_read_tuple():
    assert REQUEST_TIMEOUT == (10.0, 30.0)


def test_retry_policy_defaults():
    policy = RetryPolicy()
    assert policy.max_attempts == 3
    assert policy.base_delay == 2.0
    assert policy.jitter == 0.2
    assert policy.max_retry_after == 60.0
    assert policy.retry_statuses == frozenset({408, 429, 500, 502, 503, 504})


def test_retry_policy_rejects_zero_attempts():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)


# --- 요청 헤더 ---


def test_sets_user_agent():
    session = FakeSession(make_response(200, content=BODY.encode()))
    run(session)
    assert session.calls[0]["headers"]["User-Agent"] == USER_AGENT


def test_sends_conditional_headers_and_returns_304():
    headers = {"ETag": '"abc"', "Last-Modified": "Wed, 04 Nov 2026 02:55:00 GMT"}
    session = FakeSession(make_response(304, headers))
    result, waits = run(session, etag='"abc"', last_modified="Wed, 04 Nov 2026 02:55:00 GMT")

    sent = session.calls[0]["headers"]
    assert sent["If-None-Match"] == '"abc"'
    assert sent["If-Modified-Since"] == "Wed, 04 Nov 2026 02:55:00 GMT"
    assert session.calls[0]["url"] == SPEC.url
    assert result.status == 304
    assert result.body is None
    assert result.headers == headers
    assert result.attempts == 1
    assert waits == []


def test_omits_conditional_headers_when_validators_are_none():
    session = FakeSession(make_response(200, content=BODY.encode()))
    run(session, etag=None, last_modified=None)
    assert set(session.calls[0]["headers"]) == {"User-Agent"}


def test_sends_only_the_validator_that_is_given():
    session = FakeSession(make_response(200, content=BODY.encode()), make_response(200, content=BODY.encode()))
    run(session, etag='"abc"')
    run(session, last_modified="Wed, 04 Nov 2026 02:55:00 GMT")
    assert set(session.calls[0]["headers"]) == {"User-Agent", "If-None-Match"}
    assert set(session.calls[1]["headers"]) == {"User-Agent", "If-Modified-Since"}


def test_passes_timeout_on_every_attempt():
    session = FakeSession(make_response(503), requests.ConnectionError("boom"), make_response(200, content=BODY.encode()))
    run(session)
    assert [call["timeout"] for call in session.calls] == [REQUEST_TIMEOUT] * 3


# --- 성공 응답 ---


def test_200_returns_decoded_body_and_server_cased_headers():
    headers = {"ETag": '"v1"', "content-type": "application/rss+xml; charset=utf-8"}
    session = FakeSession(make_response(200, headers, BODY.encode("utf-8")))
    result, waits = run(session)

    assert isinstance(result, FetchResult)
    assert result.status == 200
    assert result.body == BODY
    assert result.headers == headers
    assert list(result.headers) == ["ETag", "content-type"]
    assert result.attempts == 1
    assert waits == []


def test_result_feeds_build_envelope():
    session = FakeSession(make_response(200, {"etag": '"v1"'}, BODY.encode()))
    result, _ = run(session)
    env = build_envelope(SPEC, result.requested_at, result.status, result.headers, result.body)
    assert env.etag == '"v1"'
    assert env.body == BODY


def test_default_clock_is_timezone_aware_utc():
    session = FakeSession(make_response(200, content=BODY.encode()))
    result = fetch_feed(SPEC, etag=None, last_modified=None, session=session)
    assert result.requested_at.utcoffset() == timedelta(0)


# --- 본문 디코딩 ---


def test_decodes_declared_charset_euc_kr():
    text = "<title>한국어 뉴스 속보</title>"
    headers = {"Content-Type": "text/xml; charset=EUC-KR"}
    session = FakeSession(make_response(200, headers, text.encode("euc-kr")))
    result, _ = run(session)
    assert result.body == text


def test_charset_parameter_may_be_quoted_and_header_name_any_case():
    text = "<title>한국어 뉴스 속보</title>"
    headers = {"content-type": 'text/xml; charset="euc-kr"'}
    session = FakeSession(make_response(200, headers, text.encode("euc-kr")))
    result, _ = run(session)
    assert result.body == text


def test_missing_charset_decodes_as_utf8_not_latin1():
    # requests의 response.text는 text/xml에 charset이 없으면 ISO-8859-1로 읽어 한글이 깨진다
    text = "<title>한국어 뉴스 속보</title>"
    session = FakeSession(make_response(200, {"Content-Type": "text/xml"}, text.encode("utf-8")))
    result, _ = run(session)
    assert result.body == text


def test_missing_content_type_decodes_as_utf8():
    text = "<title>한국어 뉴스 속보</title>"
    session = FakeSession(make_response(200, {}, text.encode("utf-8")))
    result, _ = run(session)
    assert result.body == text


# 모르는 이름(LookupError), 텍스트 코덱이 아닌 이름(LookupError), 디코드하면 UnicodeError를 내는 코덱(undefined)
@pytest.mark.parametrize("charset", ["no-such-codec", "rot13", "undefined"])
def test_unknown_or_non_text_charset_falls_back_to_utf8(charset):
    text = "<title>한국어 뉴스 속보</title>"
    session = FakeSession(make_response(200, {"Content-Type": f"text/xml; charset={charset}"}, text.encode("utf-8")))
    result, _ = run(session)
    assert result.body == text


def test_undecodable_bytes_are_replaced_not_raised():
    session = FakeSession(make_response(200, {"Content-Type": "text/xml; charset=utf-8"}, b"<t>\xff\xfe</t>"))
    result, _ = run(session)
    assert result.body == "<t>��</t>"


# --- 재시도 ---


def test_retries_503_then_succeeds_with_waits_2_then_4():
    session = FakeSession(make_response(503), make_response(503), make_response(200, content=BODY.encode()))
    result, waits = run(session)

    assert result.status == 200
    assert result.attempts == 3
    assert len(session.calls) == 3
    assert len(waits) == 2
    assert waits[0] == pytest.approx(2.0, rel=0.2)
    assert waits[1] == pytest.approx(4.0, rel=0.2)


def test_backoff_applies_jitter_factor_from_policy(monkeypatch):
    seen = []

    def fake_uniform(low, high):
        seen.append((low, high))
        return 1.2

    monkeypatch.setattr(random, "uniform", fake_uniform)
    session = FakeSession(make_response(503), make_response(503), make_response(200, content=BODY.encode()))
    _, waits = run(session)

    assert waits == pytest.approx([2.4, 4.8])
    assert seen == [pytest.approx((0.8, 1.2))] * 2


def test_backoff_uses_custom_policy_values(monkeypatch):
    monkeypatch.setattr(random, "uniform", lambda low, high: 1.0)
    policy = RetryPolicy(max_attempts=4, base_delay=1.0, jitter=0.0)
    session = FakeSession(make_response(500), make_response(500), make_response(500), make_response(200))
    result, waits = run(session, policy=policy)

    assert result.attempts == 4
    assert waits == [1.0, 2.0, 4.0]


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_each_default_retry_status_is_retried(status):
    session = FakeSession(make_response(status), make_response(200, content=BODY.encode()))
    result, waits = run(session)
    assert result.status == 200
    assert result.attempts == 2
    assert len(waits) == 1


def test_honors_retry_after_capped_at_60():
    session = FakeSession(make_response(429, {"Retry-After": "120"}), make_response(200, content=BODY.encode()))
    result, waits = run(session)
    assert result.status == 200
    assert waits == [60.0]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("5", 5.0), ("1.5", 1.5), ("0", 0.0), ("60", 60.0), (" 7 ", 7.0)],
)
def test_retry_after_seconds_replace_backoff_without_jitter(value, expected):
    session = FakeSession(make_response(503, {"Retry-After": value}), make_response(200, content=BODY.encode()))
    _, waits = run(session)
    assert waits == [expected]


def test_retry_after_header_name_is_case_insensitive():
    session = FakeSession(make_response(503, {"retry-after": "9"}), make_response(200, content=BODY.encode()))
    _, waits = run(session)
    assert waits == [9.0]


def test_retry_after_cap_comes_from_policy():
    policy = RetryPolicy(max_retry_after=10.0)
    session = FakeSession(make_response(503, {"Retry-After": "30"}), make_response(200, content=BODY.encode()))
    _, waits = run(session, policy=policy)
    assert waits == [10.0]


@pytest.mark.parametrize("value", ["Wed, 04 Nov 2026 03:00:30 GMT", "soon", "", "-5", "nan", "inf"])
def test_non_numeric_or_invalid_retry_after_falls_back_to_backoff(value):
    session = FakeSession(make_response(503, {"Retry-After": value}), make_response(200, content=BODY.encode()))
    _, waits = run(session)
    assert len(waits) == 1
    assert waits[0] == pytest.approx(2.0, rel=0.2)


def test_retry_after_is_used_per_attempt_and_backoff_exponent_keeps_counting():
    session = FakeSession(
        make_response(503, {"Retry-After": "3"}),
        make_response(503),
        make_response(200, content=BODY.encode()),
    )
    _, waits = run(session)
    assert waits[0] == 3.0
    assert waits[1] == pytest.approx(4.0, rel=0.2)


def test_does_not_retry_404():
    session = FakeSession(make_response(404))
    error, waits = run_failing(session)

    assert len(session.calls) == 1
    assert waits == []
    assert error.status == 404
    assert error.attempts == 1
    assert error.__cause__ is None
    assert str(error) == "khan/kh_world: HTTP 404 after 1 attempt(s)"


@pytest.mark.parametrize("status", [204, 301, 400, 403, 404, 410, 501])
def test_non_retryable_non_success_status_fails_after_one_attempt(status):
    session = FakeSession(make_response(status))
    error, waits = run_failing(session)
    assert len(session.calls) == 1
    assert waits == []
    assert (error.status, error.attempts) == (status, 1)


def test_exhausted_retryable_status_raises_after_max_attempts_without_final_sleep():
    session = FakeSession(make_response(503), make_response(503), make_response(503))
    error, waits = run_failing(session)

    assert len(session.calls) == 3
    assert len(waits) == 2
    assert error.status == 503
    assert error.attempts == 3
    assert str(error) == "khan/kh_world: HTTP 503 after 3 attempt(s)"


def test_connection_error_is_retried_then_raises_after_3_attempts():
    errors = [requests.ConnectionError(f"boom{n}") for n in (1, 2, 3)]
    session = FakeSession(*errors)
    error, waits = run_failing(session)

    assert len(session.calls) == 3
    assert len(waits) == 2
    assert waits[0] == pytest.approx(2.0, rel=0.2)
    assert waits[1] == pytest.approx(4.0, rel=0.2)
    assert error.status is None
    assert error.attempts == 3
    assert error.__cause__ is errors[-1]
    assert str(error).startswith("khan/kh_world: ConnectionError after 3 attempt(s)")


@pytest.mark.parametrize("exc_type", [requests.Timeout, requests.ReadTimeout, requests.ConnectTimeout])
def test_timeout_is_retried(exc_type):
    session = FakeSession(exc_type("slow"), make_response(200, content=BODY.encode()))
    result, waits = run(session)
    assert result.status == 200
    assert result.attempts == 2
    assert len(waits) == 1


def test_other_request_exception_is_not_retried():
    cause = requests.TooManyRedirects("loop")
    session = FakeSession(cause)
    error, waits = run_failing(session)

    assert len(session.calls) == 1
    assert waits == []
    assert error.status is None
    assert error.attempts == 1
    assert error.__cause__ is cause


def test_status_after_transport_errors_reports_http_status_without_stale_cause():
    session = FakeSession(requests.ConnectionError("boom"), make_response(503), make_response(503))
    error, _ = run_failing(session)
    assert error.status == 503
    assert error.attempts == 3
    assert error.__cause__ is None


def test_transport_error_after_status_reports_no_status():
    session = FakeSession(make_response(503), make_response(503), requests.ConnectionError("boom"))
    error, _ = run_failing(session)
    assert error.status is None
    assert error.attempts == 3
    assert isinstance(error.__cause__, requests.ConnectionError)


def test_custom_max_attempts_limits_requests():
    policy = RetryPolicy(max_attempts=2)
    session = FakeSession(make_response(503), make_response(503))
    error, waits = run_failing(session, policy=policy)
    assert len(session.calls) == 2
    assert len(waits) == 1
    assert error.attempts == 2


def test_custom_retry_statuses_are_respected():
    policy = RetryPolicy(retry_statuses=frozenset({404}))
    session = FakeSession(make_response(404), make_response(200, content=BODY.encode()))
    result, _ = run(session, policy=policy)
    assert result.attempts == 2

    session = FakeSession(make_response(503))
    error, _ = run_failing(session, policy=policy)
    assert error.attempts == 1


# --- 요청 시각 ---


def test_requested_at_is_taken_at_start_of_final_attempt():
    clock = FakeClock()
    session = FakeSession(make_response(503), make_response(503), make_response(200, content=BODY.encode()))
    result, _ = run(session, clock=clock)

    assert clock.calls == 3
    assert result.requested_at == T0 + timedelta(seconds=2)


def test_requested_at_single_attempt_is_first_clock_reading():
    clock = FakeClock()
    session = FakeSession(make_response(304))
    result, _ = run(session, clock=clock)
    assert clock.calls == 1
    assert result.requested_at == T0


def test_clock_is_read_before_the_request_is_sent():
    order = []

    class RecordingSession(FakeSession):
        def get(self, url, headers=None, timeout=None):
            order.append("get")
            return super().get(url, headers=headers, timeout=timeout)

    def clock():
        order.append("clock")
        return T0

    run(RecordingSession(make_response(200, content=BODY.encode())), clock=clock)
    assert order == ["clock", "get"]


# --- 모듈 구조 ---


def test_fetch_error_keeps_status_and_attempts():
    error = FetchError("msg", status=500, attempts=3)
    assert isinstance(error, Exception)
    assert (error.status, error.attempts) == (500, 3)
    assert str(error) == "msg"


def test_module_exports_requested_names():
    for name in ("RetryPolicy", "FetchResult", "FetchError", "fetch_feed", "USER_AGENT", "REQUEST_TIMEOUT"):
        assert hasattr(http_fetch, name)
