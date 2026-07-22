from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any


SEOUL_ZONE = timezone(timedelta(hours=9), name="Asia/Seoul")


def parse_local_published_at(raw_date: str | None, input_format: str, output_format: str) -> str | None:
    """언론사 페이지의 서울 현지 시각을 파싱하며, 실패 시 임의 시각을 만들지 않습니다."""
    if not raw_date:
        return None

    try:
        return datetime.strptime(raw_date, input_format).strftime(output_format)
    except (TypeError, ValueError):
        return None


def normalize_rss_published_at(entry: Any) -> str | None:
    """RSS 발행 시각을 서울 시각으로 변환하며, 원본 시각이 불명확하면 None을 반환합니다."""
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_time:
        utc_datetime = datetime(*parsed_time[:6], tzinfo=timezone.utc)
        return utc_datetime.astimezone(SEOUL_ZONE).strftime("%Y-%m-%dT%H:%M:%S")

    raw_date = entry.get("published") or entry.get("updated")
    if raw_date:
        try:
            parsed_date = parsedate_to_datetime(raw_date)
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
            return parsed_date.astimezone(SEOUL_ZONE).strftime("%Y-%m-%dT%H:%M:%S")
        except (TypeError, ValueError):
            return None

    return None
