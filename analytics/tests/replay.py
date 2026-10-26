"""dbt 가 컴파일한 SQL 을 메모리 DuckDB 에서 다시 실행하는 도구 (속성 테스트용).

dbt build 는 한 번에 몇 초가 걸려 무작위 입력 수백 개에 쓰기 어렵습니다. 그래서 입력 경로와 as_of 를
자리표시자로 둔 채 한 번만 `dbt compile` 하고, 케이스마다 자리표시자만 바꿔 모델 SQL 을 의존 순서대로 실행합니다.
실행하는 SQL 은 dbt build 와 같은 컴파일 결과이므로 모델 의미를 그대로 검사합니다.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb

from tests.helpers import ANALYTICS

RAW_PLACEHOLDER = "/__RAW_ROOT_PLACEHOLDER__"
SEEDS_PLACEHOLDER = "/__SEEDS_DIR_PLACEHOLDER__"
AS_OF_PLACEHOLDER = "1999-12-31T23:59:58"


class CompiledProject:
    def __init__(self, work_dir: Path):
        from dbt.cli.main import dbtRunner

        work_dir.mkdir(parents=True, exist_ok=True)
        saved = {key: os.environ.get(key) for key in ("RAW_DATA_DIR", "SEEDS_DIR", "DBT_DUCKDB_PATH")}
        os.environ.update({
            "RAW_DATA_DIR": RAW_PLACEHOLDER,
            "SEEDS_DIR": SEEDS_PLACEHOLDER,
            "DBT_DUCKDB_PATH": str(work_dir / "trend.duckdb"),
        })
        try:
            result = dbtRunner().invoke([
                "compile",
                "--project-dir", str(ANALYTICS),
                "--profiles-dir", str(ANALYTICS),
                "--target-path", str(work_dir / "target"),
                "--log-path", str(work_dir / "logs"),
                "--no-partial-parse",
                "--quiet",
                "--vars", json.dumps({"as_of": AS_OF_PLACEHOLDER}),
            ])
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        if not result.success:
            raise RuntimeError(f"dbt compile 실패: {result.exception}")

        manifest = json.loads((work_dir / "target" / "manifest.json").read_text(encoding="utf-8"))
        nodes = {uid: node for uid, node in manifest["nodes"].items() if node["resource_type"] in ("model", "test")}
        self.models = self._topological([n for n in nodes.values() if n["resource_type"] == "model"])
        self.tests = [n for n in nodes.values() if n["resource_type"] == "test"]

    @staticmethod
    def _topological(models: list[dict]) -> list[dict]:
        by_id = {model["unique_id"]: model for model in models}
        ordered, seen = [], set()

        def visit(uid):
            if uid in seen or uid not in by_id:
                return
            seen.add(uid)
            for dependency in by_id[uid]["depends_on"]["nodes"]:
                visit(dependency)
            ordered.append(by_id[uid])

        for uid in sorted(by_id):
            visit(uid)
        return ordered

    @staticmethod
    def _bind(sql: str, raw_root: Path, seeds_dir: Path, as_of: str) -> str:
        return (
            sql.replace(RAW_PLACEHOLDER, str(raw_root).replace("'", "''"))
            .replace(SEEDS_PLACEHOLDER, str(seeds_dir).replace("'", "''"))
            .replace(AS_OF_PLACEHOLDER, as_of)
        )

    def run(self, raw_root: Path, seeds_dir: Path, as_of: str) -> tuple[duckdb.DuckDBPyConnection, list[str]]:
        """모델을 만들고 연결과 실패한 error 등급 테스트 이름 목록을 돌려준다."""
        connection = duckdb.connect()
        connection.execute("attach ':memory:' as trend")
        connection.execute("use trend")
        for model in self.models:
            sql = self._bind(model["compiled_code"], raw_root, seeds_dir, as_of)
            connection.execute(f'create table "{model["name"]}" as {sql}')
        failed = []
        for test in self.tests:
            if test["config"].get("severity", "error").lower() != "error":
                continue
            sql = self._bind(test["compiled_code"], raw_root, seeds_dir, as_of)
            if connection.execute(f"select count(*) from ({sql}) as failures").fetchone()[0]:
                failed.append(test["name"])
        return connection, failed
