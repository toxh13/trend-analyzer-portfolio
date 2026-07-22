import time
from collections.abc import Callable, Iterable

from crawlers.crawl_result import CrawlResult


def run_source_safely(channel: str, crawler: Callable[[], CrawlResult]) -> CrawlResult:
    """한 채널의 예상하지 못한 예외가 다른 채널 실행까지 중단하지 않게 격리합니다."""
    started_at = time.perf_counter()
    try:
        result = crawler()
        if not isinstance(result, CrawlResult):
            raise TypeError(f"{channel} crawler must return CrawlResult")
    except Exception as exc:
        result = CrawlResult(channel=channel)
        result.record_unit("failure")
        print(
            f"event=crawl_channel_failed channel={channel} "
            f"error={type(exc).__name__}"
        )

    duration_ms = int((time.perf_counter() - started_at) * 1000)
    print(
        f"event=crawl_channel_completed channel={channel} outcome={result.outcome} "
        f"articles={len(result.articles)} success_units={result.successful_units} "
        f"partial_units={result.partial_units} "
        f"empty_units={result.empty_units} failed_units={result.failed_units} "
        f"invalid={result.invalid_articles} duration_ms={duration_ms}"
    )
    return result


def run_sources(source_specs: Iterable[tuple[str, Callable[[], CrawlResult]]]) -> list[CrawlResult]:
    return [run_source_safely(channel, crawler) for channel, crawler in source_specs]
