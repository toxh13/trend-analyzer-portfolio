"""실행 ID와 원본(raw) 객체 키. 같은 구간이면 항상 같은 값이 나오는 결정적 규칙이다."""

import uuid
from datetime import datetime, timezone

DAG_ID = "trend_pipeline_hourly"


def _to_utc(interval_end: datetime) -> datetime:
    # naive 시각은 어느 시간대인지 알 수 없어 키가 흔들리므로 거부한다
    if interval_end.tzinfo is None or interval_end.utcoffset() is None:
        raise ValueError(f"timezone 정보가 있는 datetime이 필요하다: {interval_end!r}")
    return interval_end.astimezone(timezone.utc)


def run_id(interval_end: datetime, dag_id: str = DAG_ID) -> str:
    """구간 끝(UTC 기준)과 DAG ID로 만든 결정적 UUID5 문자열."""
    end_utc = _to_utc(interval_end)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{dag_id}|{end_utc.isoformat()}"))


def run_prefix(interval_end: datetime) -> str:
    """해당 실행의 원본 파일이 놓이는 UTC 날짜 디렉터리 접두어. 예: raw/dt=2026-11-04/"""
    end_utc = _to_utc(interval_end)
    return f"raw/dt={end_utc:%Y-%m-%d}/"


def raw_key(interval_end: datetime, source: str, feed: str) -> str:
    """피드 하나의 원본 봉투 객체 키. 파일명에 ':'를 쓰지 않도록 시각은 기본 형식(YYYYMMDDTHHMMSSZ)으로 쓴다."""
    end_utc = _to_utc(interval_end)
    return f"{run_prefix(end_utc)}source={source}/feed={feed}/run={end_utc:%Y%m%dT%H%M%SZ}.json"
