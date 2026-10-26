import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from crawlers.article_fields import SEOUL_ZONE
from crawlers.batch_reporting import build_channel_payload
from crawlers.crawl_result import CrawlResult

# v2 원천 파일(contracts/raw/*.schema.json) 형식으로 기사와 실행 요약을 씁니다.
# v1은 같은 정보를 Spring API로 보냈고, v2는 data 브랜치에 커밋할 파일로 남깁니다.

SCHEMA_VERSION = 1
MAX_TITLE_LENGTH = 1000
MAX_SOURCE_URL_LENGTH = 1000
PUBLISHED_AT_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
SOURCE_URL_PATTERN = re.compile(r"^https?://")


@dataclass
class RawRunCounts:
    """배치 한 번의 수량입니다. 예외가 나도 그 시점까지 센 값으로 run JSON을 남깁니다."""

    received: int = 0
    validation_rejected: int = 0
    valid_input: int = 0
    duplicate_urls: int = 0
    previously_seen: int = 0
    eligible: int = 0
    selected: int = 0
    dropped_by_limit: int = 0
    preprocessing_failed: int = 0
    written: int = 0
    write_failed: int = 0
    channels: list[CrawlResult] = field(default_factory=list)

    @property
    def reconciliation_ok(self) -> bool:
        # channelsTotal 식은 CrawlResult.outcome이 항상 네 값 중 하나라서 따로 검사하지 않습니다.
        return (
            self.received == self.valid_input + self.validation_rejected
            and self.valid_input == self.duplicate_urls + self.previously_seen + self.eligible
            and self.eligible == self.selected + self.dropped_by_limit
            and self.selected == self.preprocessing_failed + self.written + self.write_failed
        )

    def outcome(self, failed: bool = False) -> str:
        """v1 BatchRunSummary.outcome 규칙에서 '백엔드 수신'을 '파일 기록'으로 바꾼 판정입니다."""
        if failed or not self.reconciliation_ok:
            return "FAILURE"

        failed_units = sum(result.failed_units for result in self.channels)
        partial_units = sum(result.partial_units for result in self.channels)
        if self.selected == 0:
            if failed_units > 0:
                return "FAILURE"
            if partial_units > 0 or self.validation_rejected > 0:
                return "PARTIAL_FAILURE"
            return "EMPTY"
        if self.written == 0:
            return "FAILURE"
        if (
            failed_units > 0
            or partial_units > 0
            or self.validation_rejected > 0
            or self.preprocessing_failed > 0
            or self.write_failed > 0
        ):
            return "PARTIAL_FAILURE"
        return "SUCCESS"


def build_article_record(payload: dict, run_id: str, channel: str, crawled_at: str) -> dict:
    """전처리된 기사를 article.schema.json 한 줄로 바꿉니다. 계약을 어기는 기사는 예외로 거릅니다."""
    source_url = str(payload["sourceUrl"]).strip()
    title = str(payload["title"])
    published_at = str(payload["publishedAt"])
    if not SOURCE_URL_PATTERN.match(source_url) or len(source_url) > MAX_SOURCE_URL_LENGTH:
        raise ValueError(f"sourceUrl violates contract: {source_url[:50]}")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError(f"title is longer than {MAX_TITLE_LENGTH}")
    if not PUBLISHED_AT_PATTERN.match(published_at):
        raise ValueError(f"publishedAt must be Seoul local time without offset: {published_at}")

    return {
        "schemaVersion": SCHEMA_VERSION,
        "runId": run_id,
        "channel": channel,
        "source": payload["source"],
        "category": payload["category"],
        "title": title,
        "sourceUrl": source_url,
        "publishedAt": published_at,
        "crawledAt": crawled_at,
        "summary": payload["summary"],
        "keywords": [
            {"keyword": item["keyword"], "occurrenceCount": int(item["occurrenceCount"])}
            for item in payload["keywords"]
        ],
    }


def build_run_payload(
    run_id: str,
    started_at: datetime,
    completed_at: datetime,
    outcome: str,
    trigger: str,
    counts: RawRunCounts,
    duration_ms: int,
    code_version: str,
) -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "runId": run_id,
        "startedAt": format_utc(started_at),
        "completedAt": format_utc(completed_at),
        "outcome": outcome,
        "trigger": trigger,
        "crawlerOutputCount": counts.received,
        "validationRejectedCount": counts.validation_rejected,
        "duplicateUrlCount": counts.duplicate_urls,
        "previouslySeenCount": counts.previously_seen,
        "eligibleCount": counts.eligible,
        "selectedCount": counts.selected,
        "droppedByLimitCount": counts.dropped_by_limit,
        "preprocessingFailedCount": counts.preprocessing_failed,
        "writtenCount": counts.written,
        "writeFailedCount": counts.write_failed,
        "reconciliationOk": counts.reconciliation_ok,
        "durationMs": duration_ms,
        "channels": [build_channel_payload(result) for result in counts.channels],
        "codeVersion": code_version,
    }


def format_utc(value: datetime) -> str:
    """원천 계약은 UTC를 'Z' 접미사로 적습니다(isoformat의 '+00:00'이 아님)."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("raw output timestamps must include a timezone offset")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seoul_date(value: datetime) -> date:
    """dt 파티션은 배치 시작 시각의 서울 날짜입니다."""
    return value.astimezone(SEOUL_ZONE).date()


def articles_path(output_dir: Path, dt: date, run_id: str) -> Path:
    return output_dir / "raw" / "articles" / f"dt={dt.isoformat()}" / f"{run_id}.jsonl"


def run_path(output_dir: Path, dt: date, run_id: str) -> Path:
    return output_dir / "raw" / "runs" / f"dt={dt.isoformat()}" / f"{run_id}.json"


def write_text_atomic(path: Path, text: str) -> None:
    """같은 폴더의 임시 파일에 다 쓴 뒤 rename해서, 중간에 죽어도 반쯤 쓴 파일이 남지 않게 합니다.

    임시 파일 이름은 '.'으로 시작하고 '.tmp'로 끝나 raw/**/*.jsonl, *.json 패턴에 잡히지 않습니다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as temp_file:
            temp_file.write(text)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def load_seen_urls(path: Path) -> set[str]:
    """한 줄에 URL 하나인 파일을 읽습니다. 빈 줄은 무시합니다."""
    with open(path, encoding="utf-8") as seen_file:
        return {line.strip() for line in seen_file if line.strip()}
