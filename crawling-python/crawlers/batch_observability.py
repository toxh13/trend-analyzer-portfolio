from dataclasses import dataclass

from crawlers.article_delivery import DeliveryResult
from crawlers.batch_selection import BatchSelection
from crawlers.crawl_result import CrawlResult


@dataclass(frozen=True)
class BatchRunSummary:
    """배치 한 번의 수집·선택·전송 수량을 대사하기 위한 요약입니다."""

    received: int
    valid_input: int
    invalid: int
    duplicate_urls: int
    eligible: int
    selected: int
    dropped_by_limit: int
    preprocessing_failed: int
    backend_acknowledged: int
    http_failed: int
    transport_failed: int
    channels_total: int
    successful_channels: int
    partial_channels: int
    empty_channels: int
    failed_channels: int
    successful_units: int
    partial_units: int
    empty_units: int
    failed_units: int
    duration_ms: int

    @property
    def delivery_failed(self) -> int:
        return self.preprocessing_failed + self.http_failed + self.transport_failed

    @property
    def reconciliation_ok(self) -> bool:
        return (
            self.received == self.valid_input + self.invalid
            and self.valid_input == self.duplicate_urls + self.eligible
            and self.eligible == self.selected + self.dropped_by_limit
            and self.selected
            == self.preprocessing_failed + self.backend_acknowledged + self.http_failed + self.transport_failed
            and self.channels_total
            == self.successful_channels + self.partial_channels + self.empty_channels + self.failed_channels
        )

    @property
    def outcome(self) -> str:
        if not self.reconciliation_ok:
            return "failure"
        if self.selected == 0:
            if self.failed_units > 0:
                return "failure"
            if self.partial_units > 0 or self.invalid > 0:
                return "partial_failure"
            return "empty"
        if self.backend_acknowledged == 0:
            return "failure"
        if self.failed_units > 0 or self.partial_units > 0 or self.invalid > 0 or self.delivery_failed > 0:
            return "partial_failure"
        return "success"

    def to_log_line(self) -> str:
        return (
            f"event=crawl_batch_completed outcome={self.outcome} "
            f"received={self.received} valid_input={self.valid_input} invalid={self.invalid} "
            f"duplicate_urls={self.duplicate_urls} eligible={self.eligible} "
            f"selected={self.selected} dropped_by_limit={self.dropped_by_limit} "
            f"preprocessing_failed={self.preprocessing_failed} "
            f"backend_acknowledged={self.backend_acknowledged} http_failed={self.http_failed} "
            f"transport_failed={self.transport_failed} channels_total={self.channels_total} "
            f"successful_channels={self.successful_channels} partial_channels={self.partial_channels} "
            f"empty_channels={self.empty_channels} failed_channels={self.failed_channels} "
            f"success_units={self.successful_units} partial_units={self.partial_units} "
            f"empty_units={self.empty_units} failed_units={self.failed_units} "
            f"reconciliation_ok={str(self.reconciliation_ok).lower()} duration_ms={self.duration_ms}"
        )


def build_batch_summary(
    crawl_results: list[CrawlResult],
    received: int,
    invalid: int,
    selection: BatchSelection,
    delivery: DeliveryResult,
    duration_ms: int,
) -> BatchRunSummary:
    if delivery.selected != len(selection.articles):
        raise ValueError("delivery result must cover every selected article")

    return BatchRunSummary(
        received=received,
        valid_input=selection.valid_input,
        invalid=invalid,
        duplicate_urls=selection.duplicate_urls,
        eligible=selection.eligible,
        selected=len(selection.articles),
        dropped_by_limit=selection.dropped_by_limit,
        preprocessing_failed=delivery.preprocessing_failed,
        backend_acknowledged=delivery.backend_acknowledged,
        http_failed=delivery.http_failed,
        transport_failed=delivery.transport_failed,
        channels_total=len(crawl_results),
        successful_channels=sum(result.outcome == "success" for result in crawl_results),
        partial_channels=sum(result.outcome == "partial_failure" for result in crawl_results),
        empty_channels=sum(result.outcome == "empty" for result in crawl_results),
        failed_channels=sum(result.outcome == "failure" for result in crawl_results),
        successful_units=sum(result.successful_units for result in crawl_results),
        partial_units=sum(result.partial_units for result in crawl_results),
        empty_units=sum(result.empty_units for result in crawl_results),
        failed_units=sum(result.failed_units for result in crawl_results),
        duration_ms=duration_ms,
    )
