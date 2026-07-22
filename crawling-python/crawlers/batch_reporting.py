from datetime import datetime, timezone

from crawlers.batch_observability import BatchRunSummary
from crawlers.crawl_result import CrawlResult


REPORT_TIMEOUT_SECONDS = 3
REPORT_ATTEMPTS = 2


def build_started_payload(run_id: str, started_at: datetime) -> dict:
    return {
        "runId": run_id,
        "startedAt": _to_utc_isoformat(started_at),
    }


def build_completed_payload(
    run_id: str,
    started_at: datetime,
    completed_at: datetime,
    summary: BatchRunSummary,
    crawl_results: list[CrawlResult],
) -> dict:
    """기존 배치 결과를 Spring 완료 보고 API 계약으로 변환합니다."""
    return {
        "runId": run_id,
        "startedAt": _to_utc_isoformat(started_at),
        "completedAt": _to_utc_isoformat(completed_at),
        "outcome": summary.outcome.upper(),
        "crawlerOutputCount": summary.received,
        "validationRejectedCount": summary.invalid,
        "duplicateUrlCount": summary.duplicate_urls,
        "eligibleCount": summary.eligible,
        "selectedCount": summary.selected,
        "droppedByLimitCount": summary.dropped_by_limit,
        "preprocessingFailedCount": summary.preprocessing_failed,
        "backendAcknowledgedCount": summary.backend_acknowledged,
        "httpFailedCount": summary.http_failed,
        "transportFailedCount": summary.transport_failed,
        "durationMs": summary.duration_ms,
        "channels": [_channel_payload(result) for result in crawl_results],
    }


def report_batch_completed(session, endpoint: str, payload: dict) -> bool:
    """완료 보고 실패를 수집 결과와 격리하고 성공 여부만 반환합니다."""
    return _report_with_limited_retry(session, endpoint, payload, "completion")


def report_batch_started(session, endpoint: str, payload: dict) -> bool:
    """시작 이력 보고 실패를 실제 수집 흐름과 격리합니다."""
    return _report_with_limited_retry(session, endpoint, payload, "start")


def _report_with_limited_retry(session, endpoint: str, payload: dict, phase: str) -> bool:
    for attempt in range(1, REPORT_ATTEMPTS + 1):
        try:
            response = session.post(endpoint, json=payload, timeout=REPORT_TIMEOUT_SECONDS)
        except Exception as exc:
            print(f"batch {phase} report transport failed attempt={attempt}: {exc}")
            continue

        if 200 <= response.status_code < 300:
            return True
        print(f"batch {phase} report failed attempt={attempt} status={response.status_code}")
    return False


def _channel_payload(result: CrawlResult) -> dict:
    return {
        "channel": result.channel,
        "outcome": result.outcome.upper(),
        "validatedArticleCount": len(result.articles),
        "sourceInvalidCount": result.invalid_articles,
        "successfulUnits": result.successful_units,
        "partialUnits": result.partial_units,
        "emptyUnits": result.empty_units,
        "failedUnits": result.failed_units,
    }


def _to_utc_isoformat(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("batch report timestamps must include a timezone offset")
    return value.astimezone(timezone.utc).isoformat()
