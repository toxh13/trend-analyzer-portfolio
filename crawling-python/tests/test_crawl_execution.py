import unittest
from unittest.mock import Mock

from crawlers.crawl_execution import run_sources
from crawlers.crawl_result import CrawlResult


class CrawlExecutionTest(unittest.TestCase):
    def test_runs_later_source_after_previous_source_raises(self):
        failed_crawler = Mock(side_effect=RuntimeError("source unavailable"))
        successful_result = CrawlResult(channel="daum", articles=[{"sourceUrl": "https://example.com/1"}])
        successful_result.record_unit("success")
        successful_crawler = Mock(return_value=successful_result)
        rss_result = CrawlResult(channel="rss")
        rss_result.record_unit("empty")
        rss_crawler = Mock(return_value=rss_result)

        results = run_sources([
            ("naver", failed_crawler),
            ("daum", successful_crawler),
            ("rss", rss_crawler),
        ])

        self.assertEqual(results[0].outcome, "failure")
        self.assertEqual(results[1].outcome, "success")
        successful_crawler.assert_called_once()
        rss_crawler.assert_called_once()


if __name__ == "__main__":
    unittest.main()
