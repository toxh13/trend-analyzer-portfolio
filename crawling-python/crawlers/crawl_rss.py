import os
from typing import Any

import feedparser
import requests
from bs4 import BeautifulSoup

from crawlers.rss_sources import load_rss_sources
from crawlers.article_fields import normalize_rss_published_at
from crawlers.crawl_result import CrawlResult
from crawlers.http_retry import request_with_retry

# RSS는 HTML 목록 페이지보다 구조가 안정적이지만, 매체마다 본문 제공 수준이
# 다릅니다. 현재는 안정적인 추가 수집 채널로 사용하고, 상세 본문 품질은
# 네이버/다음 HTML 크롤러가 보완합니다.
REQUEST_TIMEOUT = int(os.environ.get("RSS_REQUEST_TIMEOUT", "10"))
MAX_ENTRIES_PER_SOURCE = int(os.environ.get("MAX_RSS_ENTRIES_PER_SOURCE", "4"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TrendRadarRSSBot/1.0; +https://github.com/toxh13/Crawling_Project)"
}


def _clean_html(raw_text: str | None) -> str:
    """
    RSS summary/content 안에 포함된 HTML 태그를 제거합니다.

    백엔드에서도 XSS 정제를 수행하지만, 크롤러 단계에서 한 번 더 텍스트화하면
    전송 데이터가 작아지고 키워드 추출 품질도 안정됩니다.
    """
    if not raw_text:
        return ""

    return BeautifulSoup(raw_text, "html.parser").get_text(separator=" ", strip=True)


def _extract_content(entry: Any) -> str:
    """
    RSS 항목에서 키워드 추출에 사용할 본문 후보를 고릅니다.

    우선순위:
    1. content[0].value
    2. summary 또는 description
    본문 후보가 없으면 빈 문자열을 반환해 정상 기사로 저장하지 않습니다.
    """
    content_items = entry.get("content") or []
    if content_items and isinstance(content_items, list):
        first_content = content_items[0]
        if isinstance(first_content, dict):
            content_value = first_content.get("value")
            if content_value:
                return _clean_html(content_value)

    summary = entry.get("summary") or entry.get("description")
    if summary:
        return _clean_html(summary)

    return ""


def crawl_rss(sources: list[dict[str, str]] | None = None) -> CrawlResult:
    """
    RSS 피드를 읽어 네이버/다음 크롤러와 같은 기사 dict 목록으로 반환합니다.

    개별 RSS 피드가 실패해도 전체 배치를 중단하지 않습니다. 수집된 데이터는
    백엔드 중복 저장 방지 기준인 sourceUrl을 반드시 포함해야 합니다.
    """
    rss_sources = sources if sources is not None else load_rss_sources()
    result = CrawlResult(channel="rss")
    if not rss_sources:
        print("RSS 수집원이 설정되지 않아 RSS 수집을 건너뜁니다.")
        result.record_unit("empty")
        return result

    for source_config in rss_sources:
        feed_url = source_config.get("feedUrl", "").strip()
        source_name = source_config.get("source", "RSS").strip()
        category = source_config.get("category", "IT/과학").strip()
        discovered = 0
        valid = 0
        invalid = 0
        outcome = "failure"

        if not feed_url:
            result.record_unit("failure")
            print(
                f"event=crawl_unit_completed channel=rss source={source_name} category={category} "
                "outcome=failure discovered=0 valid=0 invalid=0"
            )
            continue

        try:
            response = request_with_retry(
                requests.get,
                feed_url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            # feedparser는 RSS 2.0과 Atom의 차이를 흡수해 entries 형태로 제공해줍니다.
            parsed_feed = feedparser.parse(response.content)

            if getattr(parsed_feed, "bozo", False):
                print(f"RSS 파싱 경고 [{source_name}]: {getattr(parsed_feed, 'bozo_exception', '')}")

            entries = parsed_feed.entries[:MAX_ENTRIES_PER_SOURCE]
            discovered = len(entries)
            for entry in entries:
                title = _clean_html(entry.get("title", ""))
                source_url = str(entry.get("link", "")).strip()
                content = _extract_content(entry)
                published_at = normalize_rss_published_at(entry)

                # 제목이나 URL이 없으면 화면 표시와 중복 저장 방지가 모두 어려우므로 제외합니다.
                if not title or not source_url:
                    invalid += 1
                    continue
                if not content or not published_at:
                    has_published_value = any(
                        entry.get(field)
                        for field in ("published_parsed", "updated_parsed", "published", "updated")
                    )
                    if not content:
                        reason = "content_missing"
                    elif has_published_value:
                        reason = "published_at_parse_failed"
                    else:
                        reason = "published_at_missing"
                    print(f"RSS 기사 제외 [{source_name}]: reason={reason}")
                    invalid += 1
                    continue

                result.articles.append({
                    "title": title,
                    "content": content,
                    "sourceUrl": source_url,
                    "source": source_name,
                    "category": category,
                    "publishedAt": published_at,
                })
                valid += 1
            if valid > 0:
                outcome = "partial_failure" if invalid > 0 else "success"
            elif invalid > 0:
                outcome = "partial_failure"
            else:
                outcome = "empty"

        except requests.RequestException as e:
            print(f"RSS 요청 실패 [{source_name}] {feed_url}: {e}")
        except Exception as e:
            print(f"RSS 처리 중 예외 발생 [{source_name}] {feed_url}: {e}")
        finally:
            result.record_unit(outcome, invalid)
            print(
                f"event=crawl_unit_completed channel=rss source={source_name} category={category} "
                f"outcome={outcome} discovered={discovered} valid={valid} invalid={invalid}"
            )

    print(f"RSS 수집 완료: {len(result.articles)}건")
    return result


if __name__ == "__main__":
    print("----- RSS 크롤러 단독 테스트 -----")
    result = crawl_rss()
    print(f"수집 결과: {result.articles}")
    print("--------------------------------")
