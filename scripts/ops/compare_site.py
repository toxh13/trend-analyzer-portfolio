"""두 정적 JSON 디렉터리를 JSON 값으로 비교합니다(파일 목록 + 내용).

    python scripts/ops/compare_site.py <expected-dir> <actual-dir> [--ignore-key generatedAt ...]

작업 B 완료 기준("build_site 결과가 fixtures/site/data 와 같음, generatedAt 제외")을 CI 에서 확인할 때 씁니다.
무시할 키는 깊이와 관계없이 모든 객체에서 뺍니다. 기본값은 generatedAt 입니다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def strip_keys(value: Any, ignored: set[str]) -> Any:
    if isinstance(value, dict):
        return {key: strip_keys(item, ignored) for key, item in value.items() if key not in ignored}
    if isinstance(value, list):
        return [strip_keys(item, ignored) for item in value]
    return value


def first_difference(expected: Any, actual: Any, path: str = "") -> str | None:
    if type(expected) is not type(actual) and not (
        isinstance(expected, (int, float)) and isinstance(actual, (int, float))
    ):
        return f"{path or '<root>'}: 타입 {type(expected).__name__} != {type(actual).__name__}"
    if isinstance(expected, dict):
        for key in sorted(expected.keys() | actual.keys()):
            if key not in actual:
                return f"{path}/{key}: 없음"
            if key not in expected:
                return f"{path}/{key}: 예상하지 못한 키"
            found = first_difference(expected[key], actual[key], f"{path}/{key}")
            if found:
                return found
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path or '<root>'}: 길이 {len(expected)} != {len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual)):
            found = first_difference(left, right, f"{path}/{index}")
            if found:
                return found
        return None
    if expected != actual:
        return f"{path or '<root>'}: {expected!r} != {actual!r}"
    return None


def compare(expected_dir: Path, actual_dir: Path, ignored: set[str]) -> list[str]:
    def files(root: Path) -> set[str]:
        return {str(path.relative_to(root)) for path in root.rglob("*.json")}

    expected_files, actual_files = files(expected_dir), files(actual_dir)
    errors = [f"{name}: 없음" for name in sorted(expected_files - actual_files)]
    errors += [f"{name}: 예상하지 못한 파일" for name in sorted(actual_files - expected_files)]
    for name in sorted(expected_files & actual_files):
        left = strip_keys(json.loads((expected_dir / name).read_text(encoding="utf-8")), ignored)
        right = strip_keys(json.loads((actual_dir / name).read_text(encoding="utf-8")), ignored)
        found = first_difference(left, right)
        if found:
            errors.append(f"{name}: {found}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    parser.add_argument("--ignore-key", action="append", default=None)
    args = parser.parse_args(argv)
    ignored = set(args.ignore_key or ["generatedAt"])

    if not any(args.expected.rglob("*.json")):
        print(f"{args.expected}: 비교할 JSON 이 없습니다")
        return 1
    errors = compare(args.expected, args.actual, ignored)
    for error in errors:
        print(error)
    print(f"files={sum(1 for _ in args.expected.rglob('*.json'))} differences={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
