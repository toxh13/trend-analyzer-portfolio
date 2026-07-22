import unittest
from unittest.mock import Mock, patch

import requests

from crawlers.http_retry import request_with_retry


class HttpRetryTest(unittest.TestCase):
    @patch("crawlers.http_retry.time.sleep")
    def test_retries_timeout_once_and_returns_second_response(self, mock_sleep):
        success = Mock(status_code=200)
        request_callable = Mock(side_effect=[requests.Timeout("timeout"), success])

        response = request_with_retry(request_callable, "https://example.com")

        self.assertIs(response, success)
        self.assertEqual(request_callable.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("crawlers.http_retry.time.sleep")
    def test_retries_retryable_server_status(self, mock_sleep):
        failure = Mock(status_code=503)
        success = Mock(status_code=200)
        request_callable = Mock(side_effect=[failure, success])

        response = request_with_retry(request_callable, "https://example.com")

        self.assertIs(response, success)
        self.assertEqual(request_callable.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("crawlers.http_retry.time.sleep")
    def test_retries_rate_limit_status(self, mock_sleep):
        rate_limited = Mock(status_code=429)
        success = Mock(status_code=200)
        request_callable = Mock(side_effect=[rate_limited, success])

        response = request_with_retry(request_callable, "https://example.com")

        self.assertIs(response, success)
        self.assertEqual(request_callable.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("crawlers.http_retry.time.sleep")
    def test_does_not_retry_non_retryable_client_status(self, mock_sleep):
        bad_request = Mock(status_code=400)
        request_callable = Mock(return_value=bad_request)

        response = request_with_retry(request_callable, "https://example.com")

        self.assertIs(response, bad_request)
        request_callable.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("crawlers.http_retry.time.sleep")
    def test_does_not_retry_http_error_with_not_found_response(self, mock_sleep):
        not_found = Mock(status_code=404)
        error = requests.HTTPError("not found", response=not_found)
        request_callable = Mock(side_effect=error)

        with self.assertRaises(requests.HTTPError):
            request_with_retry(request_callable, "https://example.com")

        request_callable.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("crawlers.http_retry.time.sleep")
    def test_stops_after_max_attempts_are_exhausted(self, mock_sleep):
        unavailable = Mock(status_code=503)
        request_callable = Mock(return_value=unavailable)

        response = request_with_retry(request_callable, "https://example.com")

        self.assertIs(response, unavailable)
        self.assertEqual(request_callable.call_count, 2)
        mock_sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
