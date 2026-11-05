"""CLI 통합 테스트: 원본 저장소 → 실버 테이블 끝까지 실행, 종료 코드, validator 조회."""

import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import oracledb
import pytest

from trend_pipeline.__main__ import main
from trend_pipeline.feeds import FeedSpec, load_feeds
from trend_pipeline.http_fetch import FetchResult
from trend_pipeline.keys import raw_key, run_id
from trend_pipeline.load import last_validators
from trend_pipeline.raw_store import LocalRawStore

from conftest import INTERVAL_END, fixture_feed_xml

pytestmark = pytest.mark.integration

END_ARG = "2026-11-04T03:00:00Z"
SUMMARY = re.compile(
    r"run_id=(?P<run_id>\S+) outcome=(?P<outcome>[A-Z_]+) new=(?P<new>\d+) existing=(?P<existing>\d+)"
    r" inserted=(?P<inserted>\d+) keywords=(?P<keywords>\d+)"
)


def cli_args(raw_root: Path, run_type: str = "backfill") -> list[str]:
    return ["run", "--interval-end", END_ARG, "--run-type", run_type, "--raw-root", str(raw_root)]


def test_backfill_from_seeded_store_succeeds_then_is_idempotent(
    conn: oracledb.Connection, seeded_store: LocalRawStore, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw_root = tmp_path / "raw-store"  # seeded_store 픽스처가 채운 폴더
    assert main(cli_args(raw_root)) == 0
    first = capsys.readouterr().out.strip().splitlines()
    assert len(first) == 1
    match = SUMMARY.fullmatch(first[0])
    assert match is not None, first[0]
    assert match["run_id"] == run_id(INTERVAL_END) and match["outcome"] == "SUCCESS"
    assert int(match["new"]) > 0 and match["inserted"] == match["new"] and match["existing"] == "0"

    # 같은 원본을 다시 처리해도 실행 기록은 같다(구간 기준). 이번에 넣은 기사만 0이다
    assert main(cli_args(raw_root)) == 0
    second = SUMMARY.fullmatch(capsys.readouterr().out.strip())
    assert second is not None
    assert (second["outcome"], second["new"], second["existing"], second["keywords"]) == (
        "SUCCESS", match["new"], "0", match["keywords"]
    )
    assert second["inserted"] == "0"


def test_module_entry_point(conn: oracledb.Connection, seeded_store: LocalRawStore, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "trend_pipeline", *cli_args(tmp_path / "raw-store")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert f"run_id={run_id(INTERVAL_END)} outcome=SUCCESS" in result.stdout


def test_backfill_with_empty_raw_root_fails_with_exit_1(
    conn: oracledb.Connection, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(cli_args(tmp_path / "empty-raw")) == 1
    captured = capsys.readouterr()
    assert "outcome=FAILURE" in captured.out
    assert len(captured.out.strip().splitlines()) == 1
    assert captured.err.count("action=missing_in_backfill") == 17


def test_scheduled_runs_collect_then_send_stored_etag(
    conn: oracledb.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # 네트워크 없이 정기 실행 경로 전체: 요청 → 원본 저장 → 적재 → 다음 구간이 저장된 ETag로 조건부 요청
    xml_by_feed = fixture_feed_xml()
    calls: list[tuple[str, str, str | None]] = []

    def fake_fetch(spec: FeedSpec, *, etag: str | None, last_modified: str | None, session: object) -> FetchResult:
        calls.append((spec.source, spec.feed, etag))
        tag = f'"{spec.source}-{spec.feed}-v1"'
        now = datetime.now(timezone.utc)
        if etag == tag:
            return FetchResult(status=304, headers={"ETag": tag}, body=None, requested_at=now, attempts=1)
        headers = {"ETag": tag, "Content-Type": "application/rss+xml; charset=utf-8"}
        body = xml_by_feed[(spec.source, spec.feed)]
        return FetchResult(status=200, headers=headers, body=body, requested_at=now, attempts=1)

    monkeypatch.setattr("trend_pipeline.__main__.fetch_feed", fake_fetch)
    # 정기 실행은 지금(UTC)+5분보다 늦은 구간을 받지 않으므로 지난 정각과 이번 정각을 쓴다
    current_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    first_end, next_end = current_hour - timedelta(hours=1), current_hour
    raw_root = tmp_path / "raw"
    store = LocalRawStore(raw_root)
    specs = load_feeds()

    def scheduled(interval_end: datetime) -> list[str]:
        end = interval_end.isoformat()
        return ["run", "--interval-end", end, "--run-type", "scheduled", "--raw-root", str(raw_root)]

    assert main(scheduled(first_end)) == 0
    first = SUMMARY.fullmatch(capsys.readouterr().out.strip())
    assert first is not None and first["outcome"] == "SUCCESS" and int(first["new"]) > 0
    assert all(store.exists(raw_key(first_end, spec.source, spec.feed)) for spec in specs)
    assert calls == [(spec.source, spec.feed, None) for spec in specs]  # 처음에는 저장된 validator가 없다

    calls.clear()
    assert main(scheduled(next_end)) == 0
    second = SUMMARY.fullmatch(capsys.readouterr().out.strip())
    # 다음 구간은 pipeline_feed_runs에 남은 피드별 ETag로 요청하고, 304라 새 기사가 없다
    assert calls == [(spec.source, spec.feed, f'"{spec.source}-{spec.feed}-v1"') for spec in specs]
    assert second is not None and (second["outcome"], second["new"]) == ("EMPTY", "0")
    assert all(store.exists(raw_key(next_end, spec.source, spec.feed)) for spec in specs)


# --- last_validators ---------------------------------------------------------

SPEC = FeedSpec(source="khan", feed="kh_world", category="세계", url="https://example.invalid/rss")


def insert_feed_run(
    conn: oracledb.Connection,
    interval_end: datetime,
    status: int | None,
    etag: str | None,
    last_modified: str | None,
    spec: FeedSpec = SPEC,
) -> None:
    run = run_id(interval_end)
    naive = interval_end.astimezone(timezone.utc).replace(tzinfo=None)
    with conn.cursor() as cursor:
        cursor.execute(
            "MERGE INTO pipeline_runs t USING (SELECT :r AS run_id FROM dual) s ON (t.run_id = s.run_id) "
            "WHEN NOT MATCHED THEN INSERT (run_id, interval_end, run_type, outcome, feed_count, failed_feed_count, "
            "new_articles, existing_articles, excluded_notice, excluded_blocklist, parse_failed, keyword_rows, "
            "started_at, completed_at) VALUES (:r, :e, 'scheduled', 'SUCCESS', 1, 0, 0, 0, 0, 0, 0, 0, :e, :e)",
            r=run,
            e=naive,
        )
        cursor.execute(
            "INSERT INTO pipeline_feed_runs (run_id, source, feed, http_status, etag, last_modified, item_count, "
            "new_articles, existing_articles, excluded_notice, excluded_blocklist, parse_failed, missing_required, "
            "duplicate_keys) VALUES (:r, :s, :f, :st, :etag, :lm, 0, 0, 0, 0, 0, 0, 0, 0)",
            r=run,
            s=spec.source,
            f=spec.feed,
            st=status,
            etag=etag,
            lm=last_modified,
        )
    conn.commit()


def test_last_validators_without_rows(conn: oracledb.Connection) -> None:
    assert last_validators(conn, SPEC) == (None, None)


def test_last_validators_newer_interval_wins(conn: oracledb.Connection) -> None:
    insert_feed_run(conn, INTERVAL_END, 200, '"old"', "Wed, 04 Nov 2026 02:00:00 GMT")
    insert_feed_run(conn, INTERVAL_END + timedelta(hours=1), 304, '"new"', "Wed, 04 Nov 2026 03:00:00 GMT")
    assert last_validators(conn, SPEC) == ('"new"', "Wed, 04 Nov 2026 03:00:00 GMT")


def test_last_validators_ignores_failed_and_validatorless_rows(conn: oracledb.Connection) -> None:
    insert_feed_run(conn, INTERVAL_END, 200, '"good"', None)
    insert_feed_run(conn, INTERVAL_END + timedelta(hours=1), 503, '"bad"', None)
    insert_feed_run(conn, INTERVAL_END + timedelta(hours=2), None, None, None)
    insert_feed_run(conn, INTERVAL_END + timedelta(hours=3), 200, None, None)
    assert last_validators(conn, SPEC) == ('"good"', None)
