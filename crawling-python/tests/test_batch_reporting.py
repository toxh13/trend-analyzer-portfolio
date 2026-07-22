import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import requests

from crawlers.batch_observability import BatchRunSummary
from crawlers.batch_reporting import (
    REPORT_TIMEOUT_SECONDS,
    build_started_payload,
    build_completed_payload,
    report_batch_started,
    report_batch_completed,
)
from crawlers.crawl_result import CrawlResult


class BatchReportingTest(unittest.TestCase):
    def setUp(self):
        self.summary = BatchRunSummary(
            received=5,
            valid_input=4,
            invalid=1,
            duplicate_urls=1,
            eligible=3,
            selected=2,
            dropped_by_limit=1,
            preprocessing_failed=0,
            backend_acknowledged=1,
            http_failed=1,
            transport_failed=0,
            channels_total=1,
            successful_channels=0,
            partial_channels=1,
            empty_channels=0,
            failed_channels=0,
            successful_units=1,
            partial_units=0,
            empty_units=0,
            failed_units=1,
            duration_ms=1250,
        )
        self.channel = CrawlResult(
            channel="naver",
            articles=[{"sourceUrl": "one"}, {"sourceUrl": "two"}],
            successful_units=1,
            failed_units=1,
            invalid_articles=3,
        )

    def test_builds_payload_without_merging_source_and_validation_invalid_counts(self):
        payload = build_completed_payload(
            run_id="b36bc1c3-3480-4f46-8169-979b1307188e",
            started_at=datetime(2026, 7, 20, 9, 0, tzinfo=timezone(timedelta(hours=9))),
            completed_at=datetime(2026, 7, 20, 0, 0, 2, tzinfo=timezone.utc),
            summary=self.summary,
            crawl_results=[self.channel],
        )

        self.assertEqual(payload["runId"], "b36bc1c3-3480-4f46-8169-979b1307188e")
        self.assertEqual(payload["startedAt"], "2026-07-20T00:00:00+00:00")
        self.assertEqual(payload["completedAt"], "2026-07-20T00:00:02+00:00")
        self.assertEqual(payload["outcome"], "PARTIAL_FAILURE")
        self.assertEqual(payload["crawlerOutputCount"], 5)
        self.assertEqual(payload["validationRejectedCount"], 1)
        self.assertEqual(payload["durationMs"], 1250)
        self.assertNotIn("sourceInvalidCount", payload)

        channel = payload["channels"][0]
        self.assertEqual(channel["outcome"], "PARTIAL_FAILURE")
        self.assertEqual(channel["validatedArticleCount"], 2)
        self.assertEqual(channel["sourceInvalidCount"], 3)
        self.assertEqual(channel["successfulUnits"], 1)
        self.assertEqual(channel["failedUnits"], 1)

    def test_rejects_naive_timestamps(self):
        with self.assertRaises(ValueError):
            build_completed_payload(
                run_id="run-id",
                started_at=datetime(2026, 7, 20, 0, 0),
                completed_at=datetime(2026, 7, 20, 0, 1, tzinfo=timezone.utc),
                summary=self.summary,
                crawl_results=[self.channel],
            )

    def test_builds_started_payload_in_utc(self):
        payload = build_started_payload(
            "b36bc1c3-3480-4f46-8169-979b1307188e",
            datetime(2026, 7, 20, 9, 0, tzinfo=timezone(timedelta(hours=9))),
        )

        self.assertEqual(payload, {
            "runId": "b36bc1c3-3480-4f46-8169-979b1307188e",
            "startedAt": "2026-07-20T00:00:00+00:00",
        })

    def test_reports_with_existing_session_and_short_timeout(self):
        session = Mock()
        session.post.return_value = Mock(status_code=200)
        payload = {"runId": "run-id"}

        result = report_batch_completed(session, "http://backend/runs/completed", payload)

        self.assertTrue(result)
        session.post.assert_called_once_with(
            "http://backend/runs/completed",
            json=payload,
            timeout=REPORT_TIMEOUT_SECONDS,
        )
        self.assertLessEqual(REPORT_TIMEOUT_SECONDS, 5)

    def test_timeout_is_not_propagated_and_is_retried_once(self):
        session = Mock()
        session.post.side_effect = requests.Timeout("timed out")

        result = report_batch_completed(session, "http://backend/runs/completed", {"runId": "run-id"})

        self.assertFalse(result)
        self.assertEqual(session.post.call_count, 2)

    def test_server_error_is_not_propagated_and_is_retried_once(self):
        session = Mock()
        session.post.return_value = Mock(status_code=500)

        result = report_batch_completed(session, "http://backend/runs/completed", {"runId": "run-id"})

        self.assertFalse(result)
        self.assertEqual(session.post.call_count, 2)

    def test_started_report_uses_same_isolated_retry(self):
        session = Mock()
        session.post.side_effect = [requests.Timeout("timed out"), Mock(status_code=200)]

        result = report_batch_started(session, "http://backend/runs", {"runId": "run-id"})

        self.assertTrue(result)
        self.assertEqual(session.post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
