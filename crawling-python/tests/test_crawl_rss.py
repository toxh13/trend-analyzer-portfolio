import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from crawlers.article_fields import normalize_rss_published_at
from crawlers.crawl_rss import crawl_rss


class RssDatetimeTest(unittest.TestCase):
    def test_converts_feedparser_utc_struct_time_to_seoul(self):
        entry = {
            "published_parsed": time.struct_time((2026, 7, 17, 15, 30, 0, 4, 198, 0)),
        }

        self.assertEqual(normalize_rss_published_at(entry), "2026-07-18T00:30:00")

    def test_does_not_replace_missing_published_time_with_current_time(self):
        self.assertIsNone(normalize_rss_published_at({}))

    @patch("crawlers.crawl_rss.feedparser.parse")
    @patch("crawlers.crawl_rss.requests.get")
    def test_keeps_entry_with_summary_and_published_time(self, mock_get, mock_parse):
        response = Mock()
        response.content = b"rss"
        response.raise_for_status.return_value = None
        mock_get.return_value = response
        mock_parse.return_value = SimpleNamespace(
            bozo=False,
            entries=[{
                "title": "기사 제목",
                "link": "https://example.com/rss/1",
                "summary": "정상 기사 요약",
                "published_parsed": time.struct_time((2026, 7, 19, 3, 0, 0, 6, 200, 0)),
            }],
        )

        result = crawl_rss([{
            "source": "테스트 RSS",
            "feedUrl": "https://example.com/feed.xml",
            "category": "IT/과학",
        }])

        self.assertEqual(len(result.articles), 1)
        self.assertEqual(result.articles[0]["content"], "정상 기사 요약")
        self.assertEqual(result.articles[0]["publishedAt"], "2026-07-19T12:00:00")

    @patch("crawlers.crawl_rss.feedparser.parse")
    @patch("crawlers.crawl_rss.requests.get")
    def test_excludes_entry_without_published_time(self, mock_get, mock_parse):
        response = Mock()
        response.content = b"rss"
        response.raise_for_status.return_value = None
        mock_get.return_value = response
        mock_parse.return_value = SimpleNamespace(
            bozo=False,
            entries=[{
                "title": "기사 제목",
                "link": "https://example.com/rss/1",
                "summary": "정상 기사 요약",
            }],
        )

        result = crawl_rss([{
            "source": "테스트 RSS",
            "feedUrl": "https://example.com/feed.xml",
            "category": "IT/과학",
        }])

        self.assertEqual(result.articles, [])

    @patch("crawlers.crawl_rss.feedparser.parse")
    @patch("crawlers.crawl_rss.requests.get")
    def test_excludes_entry_with_title_only(self, mock_get, mock_parse):
        response = Mock()
        response.content = b"rss"
        response.raise_for_status.return_value = None
        mock_get.return_value = response
        mock_parse.return_value = SimpleNamespace(
            bozo=False,
            entries=[{
                "title": "기사 제목",
                "link": "https://example.com/rss/1",
                "published_parsed": time.struct_time((2026, 7, 19, 3, 0, 0, 6, 200, 0)),
            }],
        )

        result = crawl_rss([{
            "source": "테스트 RSS",
            "feedUrl": "https://example.com/feed.xml",
            "category": "IT/과학",
        }])

        self.assertEqual(result.articles, [])

    @patch("crawlers.http_retry.time.sleep")
    @patch("crawlers.crawl_rss.feedparser.parse")
    @patch("crawlers.crawl_rss.requests.get")
    def test_retries_feed_request_without_dropping_entry(self, mock_get, mock_parse, mock_sleep):
        response = Mock(status_code=200)
        response.content = b"rss"
        response.raise_for_status.return_value = None
        mock_get.side_effect = [requests.Timeout("timeout"), response]
        mock_parse.return_value = SimpleNamespace(
            bozo=False,
            entries=[{
                "title": "기사 제목",
                "link": "https://example.com/rss/1",
                "summary": "정상 기사 요약",
                "published_parsed": time.struct_time((2026, 7, 19, 3, 0, 0, 6, 200, 0)),
            }],
        )

        result = crawl_rss([{
            "source": "테스트 RSS",
            "feedUrl": "https://example.com/feed.xml",
            "category": "IT/과학",
        }])

        self.assertEqual(len(result.articles), 1)
        self.assertEqual(result.outcome, "success")
        mock_sleep.assert_called_once()

    @patch("crawlers.http_retry.time.sleep")
    @patch("crawlers.crawl_rss.feedparser.parse")
    @patch("crawlers.crawl_rss.requests.get")
    def test_continues_next_feed_after_previous_feed_fails(self, mock_get, mock_parse, mock_sleep):
        response = Mock(status_code=200)
        response.content = b"rss"
        response.raise_for_status.return_value = None
        mock_get.side_effect = [
            requests.Timeout("timeout"),
            requests.Timeout("timeout"),
            response,
        ]
        mock_parse.return_value = SimpleNamespace(
            bozo=False,
            entries=[{
                "title": "기사 제목",
                "link": "https://example.com/rss/2",
                "summary": "정상 기사 요약",
                "published_parsed": time.struct_time((2026, 7, 19, 3, 0, 0, 6, 200, 0)),
            }],
        )

        result = crawl_rss([
            {
                "source": "실패 RSS",
                "feedUrl": "https://example.com/fail.xml",
                "category": "IT/과학",
            },
            {
                "source": "정상 RSS",
                "feedUrl": "https://example.com/success.xml",
                "category": "경제",
            },
        ])

        self.assertEqual(len(result.articles), 1)
        self.assertEqual(result.failed_units, 1)
        self.assertEqual(result.successful_units, 1)
        self.assertEqual(result.outcome, "partial_failure")
        mock_sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
