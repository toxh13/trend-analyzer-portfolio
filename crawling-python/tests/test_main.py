import unittest
from unittest.mock import Mock, patch

import main
from crawlers.article_delivery import DeliveryResult
from crawlers.batch_selection import BatchSelection
from crawlers.crawl_result import CrawlResult


class MainRunJobTest(unittest.TestCase):
    @patch("main.report_batch_started", return_value=False)
    @patch("main.build_started_payload")
    @patch("main.report_batch_completed", return_value=False)
    @patch("main.build_completed_payload")
    @patch("main.build_batch_summary")
    @patch("main.deliver_articles")
    @patch("main.select_articles_fairly")
    @patch("main.run_sources")
    @patch("main.uuid.uuid4")
    def test_reports_completed_batch_without_changing_summary_when_report_fails(
        self,
        uuid4,
        run_sources,
        select_articles_fairly,
        deliver_articles,
        build_batch_summary,
        build_completed_payload,
        report_batch_completed,
        build_started_payload,
        report_batch_started,
    ):
        run_id = Mock()
        run_id.__str__ = Mock(return_value="8ca068f2-a81c-409a-99e9-bdc04f194b8f")
        uuid4.return_value = run_id
        started_payload = {"runId": "8ca068f2-a81c-409a-99e9-bdc04f194b8f"}
        build_started_payload.return_value = started_payload
        crawl_result = CrawlResult(channel="naver", articles=[])
        crawl_result.record_unit("empty")
        run_sources.return_value = [crawl_result]
        select_articles_fairly.return_value = BatchSelection(
            articles=[],
            valid_input=0,
            duplicate_urls=0,
            eligible=0,
            dropped_by_limit=0,
        )
        deliver_articles.return_value = DeliveryResult(
            selected=0,
            preprocessing_failed=0,
            backend_acknowledged=0,
            http_failed=0,
            transport_failed=0,
        )
        summary = Mock(outcome="empty")
        summary.to_log_line.return_value = "event=crawl_batch_completed outcome=empty"
        build_batch_summary.return_value = summary
        payload = {"runId": "8ca068f2-a81c-409a-99e9-bdc04f194b8f"}
        build_completed_payload.return_value = payload

        returned = main.run_job()

        self.assertIs(returned, summary)
        uuid4.assert_called_once_with()
        payload_call = build_completed_payload.call_args.kwargs
        self.assertEqual(payload_call["run_id"], payload["runId"])
        self.assertIs(payload_call["summary"], summary)
        self.assertIs(payload_call["crawl_results"], run_sources.return_value)
        self.assertEqual(payload_call["started_at"].utcoffset().total_seconds(), 0)
        self.assertEqual(payload_call["completed_at"].utcoffset().total_seconds(), 0)

        delivery_session = deliver_articles.call_args.args[0]
        report_batch_started.assert_called_once_with(
            delivery_session,
            main.CRAWL_RUN_STARTED_ENDPOINT,
            started_payload,
        )
        report_batch_completed.assert_called_once_with(
            delivery_session,
            main.CRAWL_RUN_COMPLETED_ENDPOINT,
            payload,
        )
        self.assertEqual(delivery_session.headers["X-API-KEY"], main.CRAWLER_API_KEY or "")


if __name__ == "__main__":
    unittest.main()
