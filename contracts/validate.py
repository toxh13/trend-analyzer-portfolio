"""원천 파일과 정적 JSON이 contracts/ 스키마를 만족하는지 검사합니다.

    pip install jsonschema
    python contracts/validate.py --raw-root fixtures/raw-root --site-dir fixtures/site/data

검사 대상이 하나도 없으면 실패로 봅니다(경로 실수로 빈 검사를 통과하는 것을 막기 위함).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

CONTRACTS = Path(__file__).resolve().parent

# 정적 JSON 경로 패턴 → 스키마 파일
SITE_RULES = [
    ("meta.json", "site/meta.schema.json"),
    ("categories.json", "site/categories.schema.json"),
    ("trends/*.json", "site/trend-list.schema.json"),
    ("trends/*/*.json", "site/trend-list.schema.json"),
    ("stats/*.json", "site/stats.schema.json"),
    ("keywords/index.json", "site/keyword-index.schema.json"),
    ("runs/recent.json", "site/runs-recent.schema.json"),
]


def build_validators() -> dict[str, Draft202012Validator]:
    schemas = {
        str(path.relative_to(CONTRACTS)): json.loads(path.read_text(encoding="utf-8"))
        for path in CONTRACTS.glob("*/*.schema.json")
    }
    # site 스키마끼리는 "common.schema.json#/..." 처럼 같은 폴더 상대 경로로 참조한다
    registry = Registry().with_resources(
        (name.split("/", 1)[1], Resource.from_contents(schema))
        for name, schema in schemas.items()
        if name.startswith("site/")
    )
    return {
        name: Draft202012Validator(schema, registry=registry, format_checker=Draft202012Validator.FORMAT_CHECKER)
        for name, schema in schemas.items()
    }


def check(validator: Draft202012Validator, document, label: str) -> list[str]:
    return [
        f"{label}: {'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    ]


def validate_raw(root: Path, validators) -> tuple[int, list[str]]:
    checked, errors = 0, []
    for path in sorted(root.glob("raw/articles/dt=*/*.jsonl")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                errors.append(f"{path}:{line_no}: 빈 줄")
                continue
            checked += 1
            errors += check(validators["raw/article.schema.json"], json.loads(line), f"{path}:{line_no}")
    for path in sorted(root.glob("raw/runs/dt=*/*.json")):
        checked += 1
        errors += check(validators["raw/run.schema.json"], json.loads(path.read_text(encoding="utf-8")), str(path))
    return checked, errors


def validate_site(site: Path, validators) -> tuple[int, list[str]]:
    checked, errors = 0, []
    matched: set[Path] = set()
    for pattern, schema in SITE_RULES:
        for path in sorted(site.glob(pattern)):
            matched.add(path)
            checked += 1
            errors += check(validators[schema], json.loads(path.read_text(encoding="utf-8")), str(path))
    for path in sorted(site.glob("keywords/*.json")):
        if path.name == "index.json":
            continue
        matched.add(path)
        checked += 1
        errors += check(
            validators["site/keyword-detail.schema.json"], json.loads(path.read_text(encoding="utf-8")), str(path)
        )
    for path in sorted(site.rglob("*.json")):
        if path not in matched:
            errors.append(f"{path}: 계약에 없는 파일")
    return checked, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, action="append", default=[])
    parser.add_argument("--site-dir", type=Path, action="append", default=[])
    args = parser.parse_args()
    if not args.raw_root and not args.site_dir:
        parser.error("--raw-root 또는 --site-dir 중 하나는 필요합니다")

    validators = build_validators()
    total, errors = 0, []
    for root in args.raw_root:
        count, found = validate_raw(root, validators)
        total += count
        errors += found
        if count == 0:
            errors.append(f"{root}: 검사할 원천 파일이 없습니다")
    for site in args.site_dir:
        count, found = validate_site(site, validators)
        total += count
        errors += found
        if count == 0:
            errors.append(f"{site}: 검사할 정적 JSON이 없습니다")

    for error in errors:
        print(error)
    print(f"checked={total} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
