import unittest

from crawlers.batch_selection import select_articles_fairly
from crawlers.crawl_result import CrawlResult


def article(source: str, category: str, number: int, url: str | None = None) -> dict:
    return {
        "title": f"기사 {number}",
        "content": "본문",
        "sourceUrl": url or f"https://example.com/{source}/{category}/{number}",
        "source": source,
        "category": category,
        "publishedAt": "2026-07-19T12:00:00",
    }


class BatchSelectionTest(unittest.TestCase):
    def test_removes_duplicate_url_before_applying_limit(self):
        naver = CrawlResult(channel="naver", articles=[article("naver", "IT", 1)])
        daum = CrawlResult(
            channel="daum",
            articles=[article("daum", "경제", 2, url="https://example.com/naver/IT/1")],
        )

        selection = select_articles_fairly([naver, daum], limit=50)

        self.assertEqual(len(selection.articles), 1)
        self.assertEqual(selection.valid_input, 2)
        self.assertEqual(selection.duplicate_urls, 1)
        self.assertEqual(selection.eligible, 1)

    def test_round_robin_prevents_first_bucket_from_owning_limit(self):
        naver = CrawlResult(
            channel="naver",
            articles=[article("naver", "IT", number) for number in range(1, 6)],
        )
        daum = CrawlResult(channel="daum", articles=[article("daum", "IT", 1)])
        rss = CrawlResult(channel="rss", articles=[article("rss", "경제", 1)])

        selection = select_articles_fairly([naver, daum, rss], limit=3)

        self.assertEqual(
            [(item["source"], item["category"]) for item in selection.articles],
            [("naver", "IT"), ("daum", "IT"), ("rss", "경제")],
        )
        self.assertEqual(selection.eligible, 7)
        self.assertEqual(selection.dropped_by_limit, 4)

    def test_reconciles_selected_and_dropped_counts(self):
        result = CrawlResult(
            channel="naver",
            articles=[article("naver", "IT", number) for number in range(4)],
        )

        selection = select_articles_fairly([result], limit=2)

        self.assertEqual(selection.eligible, len(selection.articles) + selection.dropped_by_limit)

    def test_groups_different_rss_feed_names_into_same_channel_category_bucket(self):
        rss = CrawlResult(
            channel="rss",
            articles=[
                article("Google RSS - AI", "IT", 1),
                article("Google RSS - 반도체", "IT", 2),
            ],
        )
        naver = CrawlResult(channel="naver", articles=[article("naver", "IT", 1)])

        selection = select_articles_fairly([rss, naver], limit=2)

        self.assertEqual(
            [item["source"] for item in selection.articles],
            ["Google RSS - AI", "naver"],
        )

    def test_removes_duplicates_before_filling_fifty_article_limit(self):
        duplicate_url = "https://example.com/duplicate"
        duplicates = [article("naver", "IT", number, url=duplicate_url) for number in range(10)]
        unique_articles = [article("naver", "IT", number) for number in range(100, 150)]
        result = CrawlResult(channel="naver", articles=duplicates + unique_articles)

        selection = select_articles_fairly([result], limit=50)

        self.assertEqual(len(selection.articles), 50)
        self.assertEqual(len({item["sourceUrl"] for item in selection.articles}), 50)
        self.assertEqual(selection.valid_input, 60)
        self.assertEqual(selection.duplicate_urls, 9)
        self.assertEqual(selection.eligible, 51)
        self.assertEqual(selection.dropped_by_limit, 1)

    def test_small_channel_category_buckets_are_not_starved(self):
        naver = CrawlResult(
            channel="naver",
            articles=[article("naver", "IT", number) for number in range(60)],
        )
        daum = CrawlResult(
            channel="daum",
            articles=[article("daum", "IT", number) for number in range(3)],
        )
        rss = CrawlResult(
            channel="rss",
            articles=[article("rss", "경제", number) for number in range(2)],
        )

        selection = select_articles_fairly([naver, daum, rss], limit=50)
        selected_sources = [item["source"] for item in selection.articles]

        self.assertEqual(selected_sources.count("naver"), 45)
        self.assertEqual(selected_sources.count("daum"), 3)
        self.assertEqual(selected_sources.count("rss"), 2)
        self.assertEqual(selection.valid_input, selection.duplicate_urls + selection.eligible)
        self.assertEqual(selection.eligible, len(selection.articles) + selection.dropped_by_limit)


if __name__ == "__main__":
    unittest.main()
