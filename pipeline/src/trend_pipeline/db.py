"""Oracle 연결. 접속 정보는 환경 변수로만 받는다(비밀번호를 파일·로그에 남기지 않는다)."""

import os

import oracledb

_ENV_VARS = ("ORACLE_DSN", "ORACLE_USER", "ORACLE_PASSWORD")


def connect() -> oracledb.Connection:
    """ORACLE_DSN·ORACLE_USER·ORACLE_PASSWORD로 연결을 연다.

    Oracle Client 없이 동작하는 thin 모드(python-oracledb 기본값)이고, autocommit은 꺼진 채로 둔다.
    환경 변수가 없거나 비어 있으면 그 이름을 담은 RuntimeError를 던진다(값은 메시지에 넣지 않는다).
    """
    values = {}
    for name in _ENV_VARS:
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"환경 변수 {name}가 설정되지 않았다")
        values[name] = value
    return oracledb.connect(user=values["ORACLE_USER"], password=values["ORACLE_PASSWORD"], dsn=values["ORACLE_DSN"])
