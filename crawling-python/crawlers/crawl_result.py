from dataclasses import dataclass, field


@dataclass
class CrawlResult:
    """수집 채널의 기사와 하위 수집 단위 실행 결과를 함께 전달합니다."""

    channel: str
    articles: list[dict] = field(default_factory=list)
    successful_units: int = 0
    partial_units: int = 0
    empty_units: int = 0
    failed_units: int = 0
    invalid_articles: int = 0

    def record_unit(self, outcome: str, invalid_articles: int = 0) -> None:
        if outcome == "success":
            self.successful_units += 1
        elif outcome == "partial_failure":
            self.partial_units += 1
        elif outcome == "empty":
            self.empty_units += 1
        elif outcome == "failure":
            self.failed_units += 1
        else:
            raise ValueError(f"unsupported crawl outcome: {outcome}")
        self.invalid_articles += invalid_articles

    @property
    def total_units(self) -> int:
        return self.successful_units + self.partial_units + self.empty_units + self.failed_units

    @property
    def outcome(self) -> str:
        if self.total_units == 0 or self.empty_units == self.total_units:
            return "empty"
        if self.successful_units == 0 and self.partial_units == 0 and self.failed_units > 0:
            return "failure"
        if self.partial_units > 0 or self.empty_units > 0 or self.failed_units > 0:
            return "partial_failure"
        return "success"
