"""CLI 인자 검증 단위 테스트. DB·네트워크 없이 인자 파싱 단계에서 종료 코드 2로 끝나야 한다."""

from datetime import datetime, timezone

import pytest

from trend_pipeline import __main__ as cli
from trend_pipeline.__main__ import main

NOW = datetime(2026, 11, 4, 2, 56, tzinfo=timezone.utc)


class ArgsAccepted(Exception):
    """인자 검증을 통과해 DB 연결 단계까지 왔다는 표시."""


@pytest.fixture
def stop_at_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    """DB에 연결하지 않고 인자 검증을 통과했는지만 본다. 지금 시각은 NOW로 고정한다."""

    def connect():
        raise ArgsAccepted

    monkeypatch.setattr(cli, "connect", connect)
    monkeypatch.setattr(cli, "_utc_now", lambda: NOW)


def run_args(interval_end: str, run_type: str = "backfill") -> list[str]:
    return ["run", "--interval-end", interval_end, "--run-type", run_type, "--raw-root", "unused"]


@pytest.mark.parametrize(
    "interval_end",
    [
        "2026-11-04T03:00:00",  # 시간대 없음
        "2026-11-04T03:30:00Z",  # 정각 아님(분)
        "2026-11-04T03:00:05Z",  # 정각 아님(초)
        "2026-11-04T03:00:00.5Z",  # 정각 아님(마이크로초)
        "2026-11-04T12:00:00+05:30",  # 현지로는 정각이지만 UTC로는 06:30
        "0001-01-01T00:00:00+01:00",  # UTC로 바꾸면 범위 밖
        "not-a-date",
    ],
)
def test_invalid_interval_end_exits_2(interval_end: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(run_args(interval_end))
    assert exc.value.code == 2
    assert "--interval-end" in capsys.readouterr().err


def test_bad_run_type_exits_2() -> None:
    with pytest.raises(SystemExit) as exc:
        main(run_args("2026-11-04T03:00:00Z", run_type="hourly"))
    assert exc.value.code == 2


def test_missing_subcommand_exits_2() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_whole_hour_in_other_offset_is_accepted(stop_at_connect: None) -> None:
    with pytest.raises(ArgsAccepted):
        main(run_args("2026-11-04T12:00:00+09:00"))  # = 03:00 UTC


@pytest.mark.parametrize("run_type", ["scheduled", "manual"])
@pytest.mark.parametrize("interval_end", ["2026-11-04T03:00:00Z", "2026-11-04T02:00:00Z"])
def test_collecting_run_accepts_interval_end_within_window(
    stop_at_connect: None, run_type: str, interval_end: str
) -> None:
    # 지금 02:56 → 03:00은 5분 안(시계 차이·조금 이른 실행 허용), 02:00은 1시간 안(늦은 실행 허용)
    with pytest.raises(ArgsAccepted):
        main(run_args(interval_end, run_type=run_type))


@pytest.mark.parametrize("run_type", ["scheduled", "manual"])
@pytest.mark.parametrize("interval_end", ["2026-11-04T01:00:00Z", "2020-01-01T00:00:00Z"])
def test_collecting_run_rejects_interval_end_older_than_one_hour(
    stop_at_connect: None, capsys: pytest.CaptureFixture[str], run_type: str, interval_end: str
) -> None:
    # 지금 02:56 → 01:00은 1시간 56분 전. 받으면 지금 피드를 옛 구간 이름으로 저장한다(지난 구간은 백필로)
    with pytest.raises(SystemExit) as exc:
        main(run_args(interval_end, run_type=run_type))
    assert exc.value.code == 2
    assert "backfill" in capsys.readouterr().err


@pytest.mark.parametrize("run_type", ["scheduled", "manual"])
@pytest.mark.parametrize("now_minute", [54, 56])
def test_collecting_run_rejects_future_interval_end(
    stop_at_connect: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    run_type: str,
    now_minute: int,
) -> None:
    # 02:54면 03:00이 5분 넘게 남았고, 02:56이어도 04:00은 너무 이르다
    monkeypatch.setattr(cli, "_utc_now", lambda: NOW.replace(minute=now_minute))
    interval_end = "2026-11-04T03:00:00Z" if now_minute == 54 else "2026-11-04T04:00:00Z"
    with pytest.raises(SystemExit) as exc:
        main(run_args(interval_end, run_type=run_type))
    assert exc.value.code == 2
    assert "--interval-end" in capsys.readouterr().err


@pytest.mark.parametrize("interval_end", ["2099-01-01T00:00:00Z", "2020-01-01T00:00:00Z"])
def test_backfill_accepts_any_whole_hour(stop_at_connect: None, interval_end: str) -> None:
    with pytest.raises(ArgsAccepted):
        main(run_args(interval_end, run_type="backfill"))
