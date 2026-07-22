import unittest
from unittest.mock import Mock, patch

import requests

from crawlers.crawl_daum import crawl_daum


class DaumCrawlerValidationTest(unittest.TestCase):
    def _list_response(self):
        response = Mock(status_code=200)
        response.text = '<a class="item_newsheadline2" href="https://example.com/daum/1">기사 제목</a>'
        return response

    @patch("crawlers.crawl_daum.requests.get")
    def test_returns_article_with_real_content_and_published_time(self, mock_get):
        detail_response = Mock(status_code=200)
        detail_response.text = (
            '<div class="article_view">정상 기사 본문</div>'
            '<span class="num_date">2026. 07. 19. 12:00</span>'
        )
        mock_get.side_effect = [self._list_response(), detail_response] * 2

        result = crawl_daum()

        self.assertEqual(len(result.articles), 2)
        self.assertTrue(all(article["publishedAt"] == "2026-07-19T12:00:00" for article in result.articles))
        self.assertTrue(all(article["content"] == "정상 기사 본문" for article in result.articles))

    @patch("crawlers.crawl_daum.requests.get")
    def test_excludes_article_when_published_time_is_invalid(self, mock_get):
        detail_response = Mock(status_code=200)
        detail_response.text = (
            '<div class="article_view">정상 기사 본문</div>'
            '<span class="num_date">잘못된 날짜</span>'
        )
        mock_get.side_effect = [self._list_response(), detail_response] * 2

        self.assertEqual(crawl_daum().articles, [])

    @patch("crawlers.crawl_daum.requests.get")
    def test_excludes_article_when_content_is_missing(self, mock_get):
        detail_response = Mock(status_code=200)
        detail_response.text = '<span class="num_date">2026. 07. 19. 12:00</span>'
        mock_get.side_effect = [self._list_response(), detail_response] * 2

        self.assertEqual(crawl_daum().articles, [])

    @patch("crawlers.http_retry.time.sleep")
    @patch("crawlers.crawl_daum.requests.get")
    def test_retries_detail_request_without_dropping_article(self, mock_get, mock_sleep):
        detail_response = Mock(status_code=200)
        detail_response.text = (
            '<div class="article_view">정상 기사 본문</div>'
            '<span class="num_date">2026. 07. 19. 12:00</span>'
        )
        mock_get.side_effect = [
            self._list_response(),
            requests.Timeout("timeout"),
            detail_response,
            self._list_response(),
            detail_response,
        ]

        result = crawl_daum()

        self.assertEqual(len(result.articles), 2)
        self.assertEqual(result.outcome, "success")
        mock_sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
