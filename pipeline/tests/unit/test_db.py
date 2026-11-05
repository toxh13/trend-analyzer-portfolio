import pytest

from trend_pipeline import db

ENV = {"ORACLE_DSN": "localhost:1521/FREEPDB1", "ORACLE_USER": "trend", "ORACLE_PASSWORD": "not-a-real-secret"}


@pytest.fixture
def env(monkeypatch):
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_connect_passes_env_values_to_oracledb(env):
    calls = []
    env.setattr(db.oracledb, "connect", lambda **kwargs: calls.append(kwargs) or "conn")

    assert db.connect() == "conn"
    assert calls == [{"user": "trend", "password": "not-a-real-secret", "dsn": "localhost:1521/FREEPDB1"}]


@pytest.mark.parametrize("missing", ["ORACLE_DSN", "ORACLE_USER", "ORACLE_PASSWORD"])
def test_connect_names_missing_env_var_without_revealing_password(env, missing):
    env.delenv(missing)
    env.setattr(db.oracledb, "connect", lambda **kwargs: pytest.fail("연결을 시도하면 안 된다"))

    with pytest.raises(RuntimeError, match=missing) as raised:
        db.connect()
    assert "not-a-real-secret" not in str(raised.value)


def test_connect_treats_empty_value_as_missing(env):
    env.setenv("ORACLE_USER", "")

    with pytest.raises(RuntimeError, match="ORACLE_USER"):
        db.connect()
