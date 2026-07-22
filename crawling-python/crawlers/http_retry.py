import time
from collections.abc import Callable

import requests


RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def request_with_retry(
    request_callable: Callable,
    *args,
    max_attempts: int = 2,
    backoff_seconds: float = 0.25,
    **kwargs,
):
    """일시적 연결 오류와 429·5xx만 제한적으로 다시 요청합니다."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    last_exception = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = request_callable(*args, **kwargs)
            status_code = getattr(response, "status_code", None)
            if status_code not in RETRYABLE_STATUS_CODES or attempt == max_attempts:
                return response
        except requests.RequestException as exc:
            last_exception = exc
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code is not None and 400 <= status_code < 500 and status_code != 429:
                raise
            if attempt == max_attempts:
                raise

        time.sleep(backoff_seconds * attempt)

    if last_exception:
        raise last_exception
    raise RuntimeError("request retry loop ended without a response")
