"""analytics 테스트 공용 도구: 기준 구현 불러오기, 산출물 비교, 고정 경로."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ANALYTICS = Path(__file__).resolve().parents[1]
REPO = ANALYTICS.parent
FIXTURES = REPO / "fixtures"
PARITY = Path(__file__).resolve().parent / "parity"
GENERATED_AT = "2026-10-24T03:00:00Z"
CODE_VERSION = "fixture"

if str(ANALYTICS) not in sys.path:
    sys.path.insert(0, str(ANALYTICS))


def load_reference():
    """fixtures/reference/v1_reference.py (정답 계산기)."""
    if "v1_reference" in sys.modules:
        return sys.modules["v1_reference"]
    spec = importlib.util.spec_from_file_location("v1_reference", FIXTURES / "reference" / "v1_reference.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["v1_reference"] = module
    spec.loader.exec_module(module)
    return module


def without_generated_at(value):
    if isinstance(value, dict):
        return {k: without_generated_at(v) for k, v in value.items() if k != "generatedAt"}
    if isinstance(value, list):
        return [without_generated_at(v) for v in value]
    return value


def read_site(site_dir: Path) -> dict[str, object]:
    return {
        path.relative_to(site_dir).as_posix(): json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(site_dir.rglob("*.json"))
    }


def diff_sites(actual: dict[str, object], expected: dict[str, object]) -> list[str]:
    """파일 목록과 JSON 값을 비교해 차이를 사람이 읽을 수 있는 문장으로 돌려준다 (generatedAt 제외)."""
    problems = []
    for name in sorted(set(expected) - set(actual)):
        problems.append(f"없는 파일: {name}")
    for name in sorted(set(actual) - set(expected)):
        problems.append(f"남는 파일: {name}")
    for name in sorted(set(actual) & set(expected)):
        left, right = without_generated_at(actual[name]), without_generated_at(expected[name])
        if left != right:
            problems.append(
                f"값 차이: {name}\n  actual:   {json.dumps(left, ensure_ascii=False)[:800]}"
                f"\n  expected: {json.dumps(right, ensure_ascii=False)[:800]}"
            )
    return problems
