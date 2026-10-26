"""v1 동등성: Java 테스트 기대값 = 기준 구현 = dbt.

analytics/tests/parity/<case>/ 마다
1. expected.json 의 Java 단언을 기준 구현 결과에 적용
2. 같은 단언을 dbt(build_site) 결과에 적용
3. 기준 구현과 dbt 의 정적 JSON 전체가 같은지 비교
케이스는 build_cases.py 로 만든다.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from tests.helpers import CODE_VERSION, GENERATED_AT, PARITY, diff_sites, load_reference

import build_site

CASES = sorted(path.parent for path in PARITY.glob("*/expected.json"))


def resolve_file(template: str, reference) -> str:
    """'keywords/{keyword:LLM}.json' 처럼 slug 자리를 채운다."""
    while "{" in template:
        start, end = template.index("{"), template.index("}")
        _, value = template[start + 1:end].split(":", 1)
        template = template[:start] + reference.slug(value) + template[end + 1:]
    return template


def follow(document, path):
    value = document
    for step in path:
        if isinstance(step, dict):
            matches = [item for item in value if all(item.get(k) == v for k, v in step.items())]
            assert len(matches) == 1, f"{step} 에 맞는 항목이 {len(matches)}개"
            value = matches[0]
        else:
            value = value[step]
    return value


def apply_checks(files: dict, expected: dict, reference, label: str) -> list[str]:
    failures = []
    for check in expected["checks"]:
        name = resolve_file(check["file"], reference)
        where = f"[{label}] {check['file']} {check['path']}"
        if name not in files:
            failures.append(f"{where}: 파일 없음")
            continue
        document = files[name]
        try:
            if check.get("absent"):
                parent, key = follow(document, check["path"][:-1]), check["path"][-1]
                if key in parent:
                    failures.append(f"{where}: 없어야 하는데 있음")
                continue
            value = follow(document, check["path"])
        except (KeyError, IndexError, AssertionError) as error:
            failures.append(f"{where}: 경로를 찾지 못함 ({error})")
            continue
        if "equals" in check and value != check["equals"]:
            failures.append(f"{where}: {value!r} != Java 기대값 {check['equals']!r}")
        if "approx" in check and not math.isclose(value, check["approx"], abs_tol=1e-4):
            failures.append(f"{where}: {value!r} ≉ Java 기대값 {check['approx']!r}")
        if "length" in check and len(value) != check["length"]:
            failures.append(f"{where}: 길이 {len(value)} != Java 기대값 {check['length']}")
    return failures


def snapshot_matches(rows: list[dict], expected: list[dict]) -> bool:
    def key(row):
        return row["keyword"], row["category"]

    if sorted(map(key, rows)) != sorted(map(key, expected)):
        return False
    actual = {key(row): row for row in rows}
    for row in expected:
        got = actual[key(row)]
        if (got["mention_count"], got["velocity_score"]) != (row["mention_count"], row["velocity_score"]):
            return False
        if not math.isclose(got["hotness_score"], row["hotness_score"], abs_tol=1e-4):
            return False
    return True


@pytest.fixture(scope="module")
def reference():
    return load_reference()


@pytest.mark.parametrize("case_dir", CASES, ids=[path.name for path in CASES])
def test_java_expectation_reference_and_dbt_agree(case_dir: Path, tmp_path, reference):
    expected = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
    raw_root, seeds, as_of = case_dir / "raw-root", case_dir / "seeds", expected["asOf"]

    # 1. 기준 구현
    reference_files = reference.build_site(
        raw_root, seeds, reference.parse_local(as_of), GENERATED_AT, CODE_VERSION,
    )
    failures = apply_checks(reference_files, expected, reference, "기준 구현")

    # 2. dbt
    work = tmp_path / "work"
    dbt_files = build_site.build_site(
        raw_root, tmp_path / "site", as_of, seeds, CODE_VERSION, generated_at=GENERATED_AT, work_dir=work,
    )
    failures += apply_checks(dbt_files, expected, reference, "dbt")

    if expected["snapshot"] is not None:
        aliases = reference.Aliases.load(seeds / "keyword_aliases.csv")
        blocked = reference.load_blocked(seeds / "blocked_keywords.csv")
        articles = reference.load_articles(raw_root, blocked)
        reference_rows = [
            {"keyword": r.keyword, "category": r.category, "mention_count": r.mention,
             "velocity_score": r.velocity, "hotness_score": r.hotness}
            for r in reference.build_snapshot(articles, aliases, blocked, datetime.fromisoformat(as_of))
        ]
        connection = duckdb.connect(str(work / "trend.duckdb"))
        cursor = connection.execute(
            "select keyword, category, mention_count, velocity_score, hotness_score from fct_trend_snapshot"
        )
        dbt_rows = [dict(zip([c[0] for c in cursor.description], row)) for row in cursor.fetchall()]
        connection.close()
        if not snapshot_matches(reference_rows, expected["snapshot"]):
            failures.append(f"[기준 구현] 스냅샷 {reference_rows} != Java 기대값 {expected['snapshot']}")
        if not snapshot_matches(dbt_rows, expected["snapshot"]):
            failures.append(f"[dbt] 스냅샷 {dbt_rows} != Java 기대값 {expected['snapshot']}")

    # 3. 기준 구현 = dbt (정적 JSON 전체)
    failures += diff_sites(dbt_files, reference_files)
    assert failures == [], "\n".join(failures)


def test_every_case_names_its_java_source():
    assert len(CASES) >= 15
    for case_dir in CASES:
        expected = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
        assert expected["java"], case_dir.name
        assert expected["checks"] or expected["snapshot"] is not None, case_dir.name
