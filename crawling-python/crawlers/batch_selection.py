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
    # v2 파일 수집에서만 사용합니다. v1 HTTP 경로는 seen_urls를 넘기지 않으므로 항상 0입니다.
    previously_seen: int = 0


def select_articles_fairly(
    results: list[CrawlResult],
    limit: int,
    seen_urls: set[str] | None = None,
) -> BatchSelection:
    """URL 중복을 제거한 뒤 수집 채널×카테고리 버킷에서 한 건씩 순환 선택합니다.

    seen_urls를 넘기면 이전 배치에서 이미 수집한 URL을 선택 전에 제외합니다(v2).
    배치 안 중복 판정이 먼저이므로, 같은 URL이 두 번 나오면 첫 번째는 previously_seen,
    두 번째는 duplicate_urls로 셉니다.
    """
    if limit < 0:
        raise ValueError("limit must not be negative")

    previously_seen_urls = {str(url).strip() for url in seen_urls or ()}
    valid_input = sum(len(result.articles) for result in results)
    duplicate_urls = 0
    previously_seen = 0
    eligible = 0
    batch_urls: set[str] = set()
    buckets: OrderedDict[tuple[str, str], deque[dict]] = OrderedDict()

    for result in results:
        for article in result.articles:
            source_url = str(article["sourceUrl"]).strip()
            if source_url in batch_urls:
                duplicate_urls += 1
                continue
            batch_urls.add(source_url)

            if source_url in previously_seen_urls:
                previously_seen += 1
                continue

            eligible += 1
            bucket_key = (result.channel, str(article["category"]).strip())
            buckets.setdefault(bucket_key, deque()).append(article)

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
        previously_seen=previously_seen,
    )
