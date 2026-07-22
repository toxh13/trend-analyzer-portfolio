import unittest
from unittest.mock import Mock

import requests

from crawlers.article_delivery import deliver_articles
from crawlers.batch_observability import build_batch_summary
from crawlers.batch_selection import select_articles_fairly
from crawlers.crawl_execution import run_sources
from crawlers.crawl_result import CrawlResult


class PipelineFaultDrillTest(unittest.TestCase):
    def test_continues_through_source_and_delivery_failures(self):
        failed_crawler = Mock(side_effect=RuntimeError("source unavailable"))

        def article(number: int, content: str) -> dict:
            return {
                "title": f"검증 기사 {number}",
                "content": content,
                "sourceUrl": f"https://example.com/{number}",
                "source": "다음 뉴스",
                "category": "IT/과학",
                "publishedAt": "2026-07-19T10:00:00",
            }

        healthy_result = CrawlResult(channel="daum", articles=[
            article(1, "전처리 실패"),
            article(2, "HTTP 오류"),
            article(3, "연결 실패"),
            article(4, "정상 전송"),
        ])
        healthy_result.record_unit("success")

        crawl_results = run_sources([
            ("naver", failed_crawler),
            ("daum", Mock(return_value=healthy_result)),
        ])
        selection = select_articles_fairly(crawl_results, limit=50)
        session = Mock()
        session.post.side_effect = [
            Mock(status_code=500, text="서버 오류"),
            requests.ConnectionError("connection failed"),
            Mock(status_code=200, text="데이터 적재 완료"),
        ]

        def extract_keywords(content: str):
            if content == "전처리 실패":
                raise RuntimeError("NLP failed")
            return [{"keyword": "검증", "occurrenceCount": 1}]

        delivery = deliver_articles(
            session,
            "http://backend/api/v1/crawling",
            selection.articles,
            keyword_extractor=extract_keywords,
        )
        summary = build_batch_summary(
            crawl_results=crawl_results,
            received=4,
            invalid=0,
            selection=selection,
            delivery=delivery,
            duration_ms=10,
        )

        self.assertEqual(session.post.call_count, 3)
        self.assertEqual(delivery.preprocessing_failed, 1)
        self.assertEqual(delivery.http_failed, 1)
        self.assertEqual(delivery.transport_failed, 1)
        self.assertEqual(delivery.backend_acknowledged, 1)
        self.assertIn("content", healthy_result.articles[3])
        acknowledged_payload = session.post.call_args_list[2].kwargs["json"]
        self.assertNotIn("content", acknowledged_payload)
        self.assertEqual(acknowledged_payload["summary"], "정상 전송")
        self.assertEqual(summary.failed_channels, 1)
        self.assertEqual(summary.failed_units, 1)
        self.assertEqual(summary.outcome, "partial_failure")
        self.assertTrue(summary.reconciliation_ok)


if __name__ == "__main__":
    unittest.main()
