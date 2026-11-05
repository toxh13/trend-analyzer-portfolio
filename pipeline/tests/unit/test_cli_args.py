"""CLI 인자 검증 단위 테스트. DB·네트워크 없이 인자 파싱 단계에서 종료 코드 2로 끝나야 한다."""

import pytest

from trend_pipeline.__main__ import main


def run_args(interval_end: str, run_type: str = "backfill") -> list[str]:
    return ["run", "--interval-end", interval_end, "--run-type", run_type, "--raw-root", "unused"]


@pytest.mark.parametrize(
    "interval_end",
    [
        "2026-11-04T03:00:00",  # 시간대 없음
        "2026-11-04T03:30:00Z",  # 정각 아님(분)
        "2026-11-04T03:00:05Z",  # 정각 아님(초)
        "2026-11-04T03:00:00.5Z",  # 정각 아님(마이크로초)
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
