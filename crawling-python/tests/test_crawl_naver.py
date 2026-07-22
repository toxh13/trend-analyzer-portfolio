import unittest
from unittest.mock import Mock, patch

import requests

from crawlers.crawl_naver import MAX_DETAIL_ATTEMPTS_PER_CATEGORY, crawl_naver


class NaverCrawlerValidationTest(unittest.TestCase):
    def _list_response(self):
        response = Mock(status_code=200)
        response.text = '<a class="sa_text_title" href="https://example.com/naver/1"><strong>기사 제목</strong></a>'
        return response

    @patch("crawlers.crawl_naver.requests.get")
    def test_returns_article_with_real_content_and_published_time(self, mock_get):
        detail_response = Mock(status_code=200)
        detail_response.text = (
            '<div id="dic_area">정상 기사 본문</div>'
            '<span class="_ARTICLE_DATE_TIME" data-date-time="2026-07-19 12:00:00"></span>'
        )
        mock_get.side_effect = [self._list_response(), detail_response] * 2

        result = crawl_naver()

        self.assertEqual(len(result.articles), 2)
        self.assertTrue(all(article["publishedAt"] == "2026-07-19T12:00:00" for article in result.articles))
        self.assertTrue(all(article["content"] == "정상 기사 본문" for article in result.articles))

    @patch("crawlers.crawl_naver.requests.get")
    def test_excludes_article_when_published_time_is_invalid(self, mock_get):
        detail_response = Mock(status_code=200)
        detail_response.text = (
            '<div id="dic_area">정상 기사 본문</div>'
            '<span class="_ARTICLE_DATE_TIME" data-date-time="잘못된 날짜"></span>'
        )
        mock_get.side_effect = [self._list_response(), detail_response] * 2

        self.assertEqual(crawl_naver().articles, [])

    @patch("crawlers.crawl_naver.requests.get")
    def test_excludes_article_when_content_is_missing(self, mock_get):
        detail_response = Mock(status_code=200)
        detail_response.text = (
            '<span class="_ARTICLE_DATE_TIME" data-date-time="2026-07-19 12:00:00"></span>'
        )
        mock_get.side_effect = [self._list_response(), detail_response] * 2

        self.assertEqual(crawl_naver().articles, [])

    @patch("crawlers.http_retry.time.sleep")
    @patch("crawlers.crawl_naver.requests.get")
    def test_continues_next_category_after_one_category_fails(self, mock_get, mock_sleep):
        detail_response = Mock(status_code=200)
        detail_response.text = (
            '<div id="dic_area">정상 기사 본문</div>'
            '<span class="_ARTICLE_DATE_TIME" data-date-time="2026-07-19 12:00:00"></span>'
        )
        mock_get.side_effect = [
            requests.Timeout("timeout"),
            requests.Timeout("timeout"),
            self._list_response(),
            detail_response,
        ]

        result = crawl_naver()

        self.assertEqual(result.outcome, "partial_failure")
        self.assertEqual(result.failed_units, 1)
        self.assertEqual(result.successful_units, 1)
        self.assertEqual(len(result.articles), 1)
        self.assertEqual(mock_sleep.call_count, 1)

    @patch("crawlers.http_retry.time.sleep")
    @patch("crawlers.crawl_naver.requests.get")
    def test_retries_detail_request_without_dropping_article(self, mock_get, mock_sleep):
        detail_response = Mock(status_code=200)
        detail_response.text = (
            '<div id="dic_area">정상 기사 본문</div>'
            '<span class="_ARTICLE_DATE_TIME" data-date-time="2026-07-19 12:00:00"></span>'
        )
        mock_get.side_effect = [
            self._list_response(),
            requests.Timeout("timeout"),
            detail_response,
            self._list_response(),
            detail_response,
        ]

        result = crawl_naver()

        self.assertEqual(len(result.articles), 2)
        self.assertEqual(result.outcome, "success")
        mock_sleep.assert_called_once()

    @patch("crawlers.crawl_naver.requests.get")
    def test_limits_detail_requests_when_all_articles_are_invalid(self, mock_get):
        list_response = Mock(status_code=200)
        list_response.text = "".join(
            f'<a class="sa_text_title" href="https://example.com/naver/{number}">기사 {number}</a>'
            for number in range(30)
        )
        invalid_detail = Mock(status_code=200)
        invalid_detail.text = "<html></html>"
        one_category_calls = [list_response] + [invalid_detail] * MAX_DETAIL_ATTEMPTS_PER_CATEGORY
        mock_get.side_effect = one_category_calls * 2

        result = crawl_naver()

        self.assertEqual(result.articles, [])
        self.assertEqual(result.partial_units, 2)
        self.assertEqual(
            mock_get.call_count,
            2 + (MAX_DETAIL_ATTEMPTS_PER_CATEGORY * 2),
        )

    @patch("crawlers.crawl_naver.requests.get")
    def test_treats_empty_html_selector_as_failure(self, mock_get):
        empty_response = Mock(status_code=200, text="<html></html>")
        mock_get.side_effect = [empty_response, empty_response]

        result = crawl_naver()

        self.assertEqual(result.outcome, "failure")
        self.assertEqual(result.failed_units, 2)


if __name__ == "__main__":
    unittest.main()
