import json
import os
from typing import Any

# RSS 수집원은 코드에 하드코딩하지 않고 JSON 설정으로 관리합니다.
# 뉴스 매체 추가/변경은 코드 배포 없이 설정 파일 또는 환경변수만 바꿔 처리할 수
# 있게 하기 위함입니다.
DEFAULT_RSS_SOURCE_FILE = "config/rss_sources.json"
DEFAULT_RSS_SOURCES: list[dict[str, str]] = []


def _normalize_source(raw_source: dict[str, Any], default_category: str = "IT/과학") -> dict[str, str] | None:
    """
    RSS 수집원 설정 하나를 내부 표준 형식으로 변환합니다.

    지원 입력 키:
    - feedUrl
    - feed_url
    - url
    """
    feed_url = str(
        raw_source.get("feedUrl")
        or raw_source.get("feed_url")
        or raw_source.get("url")
        or ""
    ).strip()

    if not feed_url:
        return None

    return {
        "source": str(raw_source.get("source") or "RSS").strip(),
        "category": str(raw_source.get("category") or default_category).strip(),
        "feedUrl": feed_url,
    }


def _load_sources_from_list(parsed_list: list[Any], default_category: str = "IT/과학") -> list[dict[str, str]]:
    """
    단순 배열 형태의 RSS 설정을 표준 수집원 목록으로 변환합니다.
    """
    sources: list[dict[str, str]] = []

    for item in parsed_list:
        if not isinstance(item, dict):
            continue

        normalized = _normalize_source(item, default_category=default_category)
        if normalized:
            sources.append(normalized)

    return sources


def _load_sources_from_categories(parsed: dict[str, Any]) -> list[dict[str, str]]:
    """
    카테고리별로 분리된 RSS 설정을 하나의 수집원 목록으로 평탄화합니다.

    권장 JSON 구조:
    {
      "categories": {
        "IT/과학": [ { "source": "...", "feedUrl": "..." } ],
        "경제": [ { "source": "...", "feedUrl": "..." } ]
      }
    }
    """
    categories = parsed.get("categories", {})
    if not isinstance(categories, dict):
        print("RSS categories 설정은 객체여야 합니다. RSS 수집을 건너뜁니다.")
        return []

    sources: list[dict[str, str]] = []
    for category, source_list in categories.items():
        if not isinstance(source_list, list):
            continue

        sources.extend(_load_sources_from_list(source_list, default_category=str(category)))

    return sources


def _load_sources_from_json(raw_json: str) -> list[dict[str, str]]:
    """
    JSON 문자열을 RSS 수집원 목록으로 변환합니다.

    잘못된 설정이 들어와도 크롤러 전체가 종료되지 않도록 빈 목록을 반환합니다.
    """
    try:
        parsed = json.loads(raw_json)

        if isinstance(parsed, dict):
            return _load_sources_from_categories(parsed)

        if isinstance(parsed, list):
            return _load_sources_from_list(parsed)

        print("RSS 설정은 JSON 객체 또는 배열이어야 합니다. RSS 수집을 건너뜁니다.")
        return []
    except json.JSONDecodeError as e:
        print(f"RSS 설정 JSON 파싱에 실패했습니다: {e}")
        return []


def _read_source_file(source_file: str) -> list[dict[str, str]]:
    """
    RSS 설정 JSON 파일을 읽습니다.
    """
    try:
        with open(source_file, "r", encoding="utf-8") as file:
            return _load_sources_from_json(file.read())
    except FileNotFoundError:
        print(f"RSS 설정 파일이 없어 RSS 수집을 건너뜁니다: {source_file}")
        return []
    except OSError as e:
        print(f"RSS 설정 파일을 읽을 수 없습니다: {e}")
        return []


def load_rss_sources() -> list[dict[str, str]]:
    """
    RSS 수집원 목록을 반환합니다.

    우선순위:
    1. RSS_SOURCES_JSON 환경변수
    2. RSS_SOURCE_FILE 환경변수로 지정한 JSON 파일
    3. 기본 파일 config/rss_sources.json
    4. DEFAULT_RSS_SOURCES
    """
    raw_json = os.environ.get("RSS_SOURCES_JSON", "").strip()
    if raw_json:
        return _load_sources_from_json(raw_json)

    source_file = os.environ.get("RSS_SOURCE_FILE", DEFAULT_RSS_SOURCE_FILE).strip()
    if source_file:
        sources = _read_source_file(source_file)
        if sources:
            return sources

    return DEFAULT_RSS_SOURCES
