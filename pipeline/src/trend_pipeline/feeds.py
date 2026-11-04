"""수집 대상 RSS 피드 설정(feeds.yml)을 읽고 검증한다."""

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import yaml

SOURCES = frozenset({"yna", "khan", "donga"})
CATEGORIES = frozenset({"정치", "경제", "사회", "세계", "문화", "IT/과학"})

_REQUIRED_KEYS = ("source", "feed", "category", "url")


@dataclass(frozen=True)
class FeedSpec:
    source: str
    feed: str
    category: str
    url: str


def load_feeds(path: Path | None = None) -> list[FeedSpec]:
    """피드 설정을 파일 순서대로 반환한다. path가 없으면 패키지 리소스를 읽는다."""
    if path is None:
        text = resources.files("trend_pipeline").joinpath("resources/feeds.yml").read_text(encoding="utf-8")
    else:
        text = Path(path).read_text(encoding="utf-8")

    data = yaml.safe_load(text)
    entries = data.get("feeds") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ValueError("feeds.yml 최상위에 'feeds' 목록이 필요하다")

    specs = [_parse_entry(index, entry) for index, entry in enumerate(entries)]
    _check_unique(specs)
    return specs


def _parse_entry(index: int, entry: object) -> FeedSpec:
    where = f"feeds[{index}]"
    if not isinstance(entry, dict):
        raise ValueError(f"{where}: 매핑이어야 한다 (받은 값: {entry!r})")

    missing = [key for key in _REQUIRED_KEYS if key not in entry]
    if missing:
        raise ValueError(f"{where}: 필수 키 누락 {missing}")
    for key in _REQUIRED_KEYS:
        if not isinstance(entry[key], str) or not entry[key]:
            raise ValueError(f"{where}: '{key}'는 비어 있지 않은 문자열이어야 한다 (받은 값: {entry[key]!r})")

    spec = FeedSpec(**{key: entry[key] for key in _REQUIRED_KEYS})
    where = f"{where} ({spec.source}/{spec.feed})"
    if spec.source not in SOURCES:
        raise ValueError(f"{where}: 알 수 없는 source '{spec.source}' (허용: {sorted(SOURCES)})")
    if spec.category not in CATEGORIES:
        raise ValueError(f"{where}: 알 수 없는 category '{spec.category}' (허용: {sorted(CATEGORIES)})")
    return spec


def _check_unique(specs: list[FeedSpec]) -> None:
    seen_category: set[tuple[str, str]] = set()
    seen_feed: set[tuple[str, str]] = set()
    for index, spec in enumerate(specs):
        where = f"feeds[{index}] ({spec.source}/{spec.feed})"
        # 소스당 카테고리 하나에 피드 하나
        if (spec.source, spec.category) in seen_category:
            raise ValueError(f"{where}: (source, category) 중복 ({spec.source}, {spec.category})")
        # 원본 키(raw key)가 피드 단위로 유일해야 한다
        if (spec.source, spec.feed) in seen_feed:
            raise ValueError(f"{where}: (source, feed) 중복 ({spec.source}, {spec.feed})")
        seen_category.add((spec.source, spec.category))
        seen_feed.add((spec.source, spec.feed))
