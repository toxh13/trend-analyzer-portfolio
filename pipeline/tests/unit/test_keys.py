import uuid
from datetime import datetime, timedelta, timezone

import pytest

from trend_pipeline.keys import DAG_ID, raw_key, run_id, run_prefix

END = datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)
KST = timezone(timedelta(hours=9))


def test_raw_key_format():
    assert raw_key(END, "yna", "politics") == "raw/dt=2026-11-04/source=yna/feed=politics/run=20261104T030000Z.json"


def test_raw_key_converts_kst_to_utc():
    kst = datetime(2026, 11, 4, 12, 0, tzinfo=KST)
    assert raw_key(kst, "khan", "kh_world").endswith("run=20261104T030000Z.json")


def test_raw_key_uses_utc_date_when_kst_date_differs():
    # 2026-11-05 08:00 KST = 2026-11-04 23:00 UTC
    kst = datetime(2026, 11, 5, 8, 0, tzinfo=KST)
    assert raw_key(kst, "donga", "science") == "raw/dt=2026-11-04/source=donga/feed=science/run=20261104T230000Z.json"


def test_raw_key_rejects_naive_datetime():
    with pytest.raises(ValueError):
        raw_key(datetime(2026, 11, 4, 3), "yna", "politics")


def test_raw_key_has_no_colon():
    assert ":" not in raw_key(END, "yna", "politics")


def test_run_id_is_deterministic_and_differs_by_interval():
    assert run_id(END) == run_id(END)
    assert run_id(END) != run_id(END + timedelta(hours=1))


def test_run_id_is_uuid5_of_dag_id_and_utc_interval_end():
    expected = str(uuid.uuid5(uuid.NAMESPACE_URL, "trend_pipeline_hourly|2026-11-04T03:00:00+00:00"))
    assert DAG_ID == "trend_pipeline_hourly"
    assert run_id(END) == expected


def test_run_id_is_the_same_for_the_same_instant_in_any_timezone():
    assert run_id(datetime(2026, 11, 4, 12, 0, tzinfo=KST)) == run_id(END)


def test_run_id_differs_by_dag_id():
    assert run_id(END, dag_id="other_dag") != run_id(END)


def test_run_id_rejects_naive_datetime():
    with pytest.raises(ValueError):
        run_id(datetime(2026, 11, 4, 3))


def test_run_prefix_is_the_utc_date_directory():
    assert run_prefix(END) == "raw/dt=2026-11-04/"


def test_run_prefix_converts_kst_to_utc_date():
    # 2026-11-05 08:00 KST = 2026-11-04 23:00 UTC
    assert run_prefix(datetime(2026, 11, 5, 8, 0, tzinfo=KST)) == "raw/dt=2026-11-04/"


def test_run_prefix_rejects_naive_datetime():
    with pytest.raises(ValueError):
        run_prefix(datetime(2026, 11, 4, 3))


def test_raw_key_lives_under_run_prefix():
    assert raw_key(END, "yna", "politics").startswith(run_prefix(END))
