"""RSS 피드 한 건을 조건부 요청(ETag/Last-Modified)과 제한된 재시도로 가져온다."""

import math
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from trend_pipeline.feeds import FeedSpec

USER_AGENT = "TrendAnalyzerBot/2.0 (+https://github.com/toxh13/trend-analyzer-portfolio)"
# (연결, 읽기) 초. 타임아웃이 없으면 응답 없는 서버 하나가 매시간 실행 전체를 붙잡는다
REQUEST_TIMEOUT = (10.0, 30.0)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3  # 첫 시도를 포함한 총 시도 횟수
    base_delay: float = 2.0  # 첫 실패 뒤 대기(초). 시도마다 2배
    jitter: float = 0.2  # 대기에 곱하는 무작위 폭(±20%)
    max_retry_after: float = 60.0  # Retry-After를 따르는 상한(초)
    retry_statuses: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504})

    def __post_init__(self) -> None:
        # 0번 시도는 요청 없이 조용히 실패하므로 만들 때 막는다
        if self.max_attempts < 1:
            raise ValueError(f"max_attempts는 1 이상이어야 한다 (받은 값: {self.max_attempts})")


@dataclass(frozen=True)
class FetchResult:
    status: int  # 200 또는 304
    headers: dict[str, str]  # 서버가 보낸 표기 그대로
    body: bytes | None  # 받은 바이트 그대로(디코드는 처리 단계가 봉투에서 한다). 304이면 None
    requested_at: datetime  # 결과를 낸 마지막 시도를 시작한 시각(UTC, timezone 포함)
    attempts: int


class FetchError(Exception):
    """수집 실패. 마지막 HTTP 상태(전송 오류면 None)와 시도 횟수를 보관한다."""

    def __init__(self, message: str, *, status: int | None, attempts: int) -> None:
        super().__init__(message)
        self.status = status
        self.attempts = attempts


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _header(headers: Mapping[str, str], name: str) -> str | None:
    # 헤더 이름은 대소문자를 구분하지 않으므로 표기와 무관하게 찾는다
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return None


def _retry_after_seconds(headers: Mapping[str, str]) -> float | None:
    # 초 단위 숫자만 따른다. HTTP 날짜 형식 등은 None을 돌려 지수 백오프로 대신한다
    raw = _header(headers, "Retry-After")
    if raw is None:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        return None
    if not math.isfinite(seconds) or seconds < 0:
        return None
    return seconds


def _backoff(policy: RetryPolicy, attempt: int) -> float:
    jitter = random.uniform(1 - policy.jitter, 1 + policy.jitter)
    return policy.base_delay * 2 ** (attempt - 1) * jitter


def fetch_feed(
    spec: FeedSpec,
    *,
    etag: str | None,
    last_modified: str | None,
    session: requests.Session,
    policy: RetryPolicy = RetryPolicy(),
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] = _utc_now,
) -> FetchResult:
    """피드를 요청해 200·304 결과를 돌려준다. 재시도 대상 오류는 정책만큼 다시 시도하고, 그 외는 FetchError."""
    request_headers = {"User-Agent": USER_AGENT}
    if etag is not None:
        request_headers["If-None-Match"] = etag
    if last_modified is not None:
        request_headers["If-Modified-Since"] = last_modified

    label = f"{spec.source}/{spec.feed}"
    last_status: int | None = None
    last_cause: Exception | None = None

    for attempt in range(1, policy.max_attempts + 1):
        requested_at = clock()
        retry_after: float | None = None
        try:
            response = session.get(spec.url, headers=request_headers, timeout=REQUEST_TIMEOUT)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_status, last_cause = None, exc
        except requests.RequestException as exc:
            # 재시도해도 같은 결과일 오류(리다이렉트 루프, 잘못된 URL 등)
            raise FetchError(
                f"{label}: {type(exc).__name__} after {attempt} attempt(s): {exc}", status=None, attempts=attempt
            ) from exc
        else:
            status = response.status_code
            headers = dict(response.headers)
            if status in (200, 304):
                body = None if status == 304 else response.content
                return FetchResult(
                    status=status, headers=headers, body=body, requested_at=requested_at, attempts=attempt
                )
            if status not in policy.retry_statuses:
                raise FetchError(f"{label}: HTTP {status} after {attempt} attempt(s)", status=status, attempts=attempt)
            last_status, last_cause = status, None
            retry_after = _retry_after_seconds(headers)

        # 마지막 시도 뒤에는 기다릴 이유가 없다
        if attempt < policy.max_attempts:
            if retry_after is not None:
                sleep(min(retry_after, policy.max_retry_after))
            else:
                sleep(_backoff(policy, attempt))

    attempts = policy.max_attempts
    if last_cause is not None:
        raise FetchError(
            f"{label}: {type(last_cause).__name__} after {attempts} attempt(s): {last_cause}",
            status=None,
            attempts=attempts,
        ) from last_cause
    raise FetchError(f"{label}: HTTP {last_status} after {attempts} attempt(s)", status=last_status, attempts=attempts)
