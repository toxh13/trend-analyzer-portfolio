from collections import OrderedDict, deque
from dataclasses import dataclass

from crawlers.crawl_result import CrawlResult


@dataclass(frozen=True)
class BatchSelection:
    articles: list[dict]
    valid_input: int
    duplicate_urls: int
    eligible: int
    dropped_by_limit: int


def select_articles_fairly(results: list[CrawlResult], limit: int) -> BatchSelection:
    """URL 중복을 제거한 뒤 수집 채널×카테고리 버킷에서 한 건씩 순환 선택합니다."""
    if limit < 0:
        raise ValueError("limit must not be negative")

    valid_input = sum(len(result.articles) for result in results)
    duplicate_urls = 0
    seen_urls: set[str] = set()
    buckets: OrderedDict[tuple[str, str], deque[dict]] = OrderedDict()

    for result in results:
        for article in result.articles:
            source_url = str(article["sourceUrl"]).strip()
            if source_url in seen_urls:
                duplicate_urls += 1
                continue
            seen_urls.add(source_url)

            bucket_key = (result.channel, str(article["category"]).strip())
            buckets.setdefault(bucket_key, deque()).append(article)

    eligible = len(seen_urls)
    selected: list[dict] = []
    while buckets and len(selected) < limit:
        for bucket_key in list(buckets.keys()):
            if len(selected) >= limit:
                break
            bucket = buckets[bucket_key]
            selected.append(bucket.popleft())
            if not bucket:
                del buckets[bucket_key]

    return BatchSelection(
        articles=selected,
        valid_input=valid_input,
        duplicate_urls=duplicate_urls,
        eligible=eligible,
        dropped_by_limit=eligible - len(selected),
    )
