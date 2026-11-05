"""`python -m trend_pipeline run …`: 한 시간 구간을 수집(평소만)하고 Oracle 실버 테이블까지 처리한다."""

import argparse
import functools
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from trend_pipeline.collect import collect_feed
from trend_pipeline.db import connect
from trend_pipeline.feeds import load_feeds
from trend_pipeline.http_fetch import fetch_feed
from trend_pipeline.keys import run_id
from trend_pipeline.load import last_validators
from trend_pipeline.process import process_interval
from trend_pipeline.raw_store import LocalRawStore

_FAILURE_ACTIONS = frozenset({"failed", "missing_in_backfill"})
# 요청해서 저장하는 실행(scheduled·manual)이 받는 구간 끝의 상한: 지금(UTC) + 이 여유. 시계 차이와 조금 이른 시작을 허용한다
_FUTURE_ALLOWANCE = timedelta(minutes=5)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trend_pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="한 시간 구간을 수집하고 처리한다")
    run.add_argument("--interval-end", required=True, help="구간 끝. 시간대가 있는 정각 ISO-8601 (예: 2026-11-04T03:00:00Z)")
    run.add_argument("--run-type", required=True, choices=["scheduled", "backfill", "manual"])
    run.add_argument("--raw-root", required=True, help="원본 봉투를 저장하는 폴더")
    return parser


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_interval_end(parser: argparse.ArgumentParser, text: str, run_type: str) -> datetime:
    """시간대가 있고 UTC로 정각인 시각만 받아 UTC로 바꾼다. 아니면 종료 코드 2.

    요청해서 그 구간 이름으로 원본을 저장하는 실행(scheduled·manual)은 아직 오지 않은 구간을 받지 않는다
    (지금 + 5분까지만). 백필은 저장된 원본만 다시 처리하므로 어느 시각이든 받는다.
    """
    try:
        # Python 3.11의 fromisoformat은 끝의 Z도 읽는다
        value = datetime.fromisoformat(text)
    except ValueError:
        parser.error(f"--interval-end를 ISO-8601 시각으로 읽을 수 없다: {text!r}")
    if value.tzinfo is None or value.utcoffset() is None:
        parser.error(f"--interval-end에는 시간대(예: Z, +09:00)가 있어야 한다: {text!r}")
    try:
        value = value.astimezone(timezone.utc)
    except OverflowError:
        parser.error(f"--interval-end를 UTC로 바꿀 수 없다(범위 밖): {text!r}")
    # 정각인지는 UTC로 바꾼 뒤에 본다. +05:30 같은 시간대의 정각은 UTC 정각이 아니다
    if value.minute or value.second or value.microsecond:
        parser.error(f"--interval-end는 UTC 기준 정각이어야 한다: {text!r}")
    if run_type != "backfill" and value > _utc_now() + _FUTURE_ALLOWANCE:
        parser.error(f"--run-type {run_type}의 --interval-end는 지금(UTC) + 5분보다 늦을 수 없다: {text!r}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    interval_end = _parse_interval_end(parser, args.interval_end, args.run_type)  # DB 연결 전에 인자부터 검증한다

    store = LocalRawStore(Path(args.raw_root))
    conn = connect()
    session = requests.Session()
    try:
        results = []
        for spec in load_feeds():
            # 백필은 요청하지 않으므로 validator 조회도 건너뛴다
            validators = (None, None) if args.run_type == "backfill" else last_validators(conn, spec)
            result = collect_feed(
                spec, interval_end, args.run_type, store, validators, functools.partial(fetch_feed, session=session)
            )
            if result.action in _FAILURE_ACTIONS or result.error is not None:
                error = " ".join((result.error or "").split())
                print(f"feed={spec.source}/{spec.feed} action={result.action} error={error}", file=sys.stderr)
            results.append(result)
        stats = process_interval(interval_end, args.run_type, store, conn, results)
    finally:
        session.close()
        conn.close()

    print(
        f"run_id={run_id(interval_end)} outcome={stats.outcome} new={stats.new_articles} "
        f"existing={stats.existing_articles} inserted={stats.inserted_articles} keywords={stats.keyword_rows}"
    )
    return 1 if stats.outcome == "FAILURE" else 0


if __name__ == "__main__":
    sys.exit(main())
