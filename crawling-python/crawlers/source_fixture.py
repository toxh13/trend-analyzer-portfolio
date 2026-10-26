import json
from collections.abc import Callable
from pathlib import Path

from crawlers.crawl_result import CrawlResult

# --source-fixture 로 넘긴 JSON을 실제 크롤러 대신 쓰는 채널 실행기로 바꿉니다.
# CI와 오프라인 e2e가 뉴스 사이트에 접속하지 않고도 같은 수집·검증·선택 경로를 타게 하기 위함입니다.
#
# 채널 값은 세 가지 형태를 받습니다.
#   [기사, ...]                     카테고리마다 성공 단위 1개. 빈 배열이면 빈 단위 1개
#   {"units": [{"category": "IT/과학", "outcome": "success", "articles": [...], "sourceInvalid": 0}, ...]}
#                                   수집 단위 결과를 그대로 지정 (부분 실패·실패 재현용)
#   {"raise": "메시지"}             크롤러가 예외를 던짐 → run_sources 격리 경로로 실패 처리
# 기사는 크롤러 출력과 같은 dict(title, content, sourceUrl, source, category, publishedAt)입니다.

CHANNELS = ("naver", "daum", "rss")


def load_source_fixture(path: Path) -> list[tuple[str, Callable[[], CrawlResult]]]:
    with open(path, encoding="utf-8") as fixture_file:
        fixture = json.load(fixture_file)
    if not isinstance(fixture, dict):
        raise ValueError("source fixture must be a JSON object keyed by channel")
    unknown = set(fixture) - set(CHANNELS)
    if unknown:
        raise ValueError(f"unknown channels in source fixture: {sorted(unknown)}")

    return [(channel, _fixture_crawler(channel, fixture.get(channel, []))) for channel in CHANNELS]


def _fixture_crawler(channel: str, spec) -> Callable[[], CrawlResult]:
    def crawl() -> CrawlResult:
        if isinstance(spec, dict) and "raise" in spec:
            raise RuntimeError(str(spec["raise"]))

        result = CrawlResult(channel=channel)
        for unit in _units(spec):
            articles = [dict(article) for article in unit.get("articles", [])]
            result.articles.extend(articles)
            result.record_unit(unit["outcome"], int(unit.get("sourceInvalid", 0)))
        return result

    return crawl


def _units(spec) -> list[dict]:
    if isinstance(spec, dict):
        return list(spec["units"])
    if not isinstance(spec, list):
        raise ValueError("channel fixture must be a list of articles or an object")
    if not spec:
        return [{"outcome": "empty", "articles": []}]

    by_category: dict[str, list[dict]] = {}
    for article in spec:
        by_category.setdefault(str(article.get("category", "")), []).append(article)
    return [{"outcome": "success", "articles": articles} for articles in by_category.values()]
