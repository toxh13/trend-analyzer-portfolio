import unittest

from crawlers.article_delivery import DeliveryResult
from crawlers.batch_observability import build_batch_summary
from crawlers.batch_selection import BatchSelection
from crawlers.crawl_result import CrawlResult


class BatchObservabilityTest(unittest.TestCase):
    def test_reconciles_all_pipeline_counts(self):
        result = CrawlResult(channel="naver")
        result.record_unit("success")
        selection = BatchSelection(
            articles=[{"sourceUrl": "https://example.com/1"}],
            valid_input=3,
            duplicate_urls=1,
            eligible=2,
            dropped_by_limit=1,
        )

        summary = build_batch_summary(
            crawl_results=[result],
            received=3,
            invalid=0,
            selection=selection,
            delivery=DeliveryResult(
                selected=1,
                preprocessing_failed=0,
                backend_acknowledged=1,
                http_failed=0,
                transport_failed=0,
            ),
            duration_ms=25,
        )

        self.assertTrue(summary.reconciliation_ok)
        self.assertEqual(summary.outcome, "success")
        self.assertIn("reconciliation_ok=true", summary.to_log_line())

    def test_marks_count_mismatch_as_failure(self):
        selection = BatchSelection(
            articles=[],
            valid_input=2,
            duplicate_urls=0,
            eligible=1,
            dropped_by_limit=0,
        )

        summary = build_batch_summary(
            crawl_results=[],
            received=2,
            invalid=0,
            selection=selection,
            delivery=DeliveryResult(
                selected=0,
                preprocessing_failed=0,
                backend_acknowledged=0,
                http_failed=0,
                transport_failed=0,
            ),
            duration_ms=1,
        )

        self.assertFalse(summary.reconciliation_ok)
        self.assertEqual(summary.outcome, "failure")

    def test_marks_all_validation_rejected_as_partial_failure(self):
        result = CrawlResult(channel="naver")
        result.record_unit("success")
        summary = build_batch_summary(
            crawl_results=[result],
            received=3,
            invalid=3,
            selection=BatchSelection(
                articles=[], valid_input=0, duplicate_urls=0, eligible=0, dropped_by_limit=0
            ),
            delivery=DeliveryResult(
                selected=0, preprocessing_failed=0, backend_acknowledged=0,
                http_failed=0, transport_failed=0,
            ),
            duration_ms=1,
        )

        self.assertTrue(summary.reconciliation_ok)
        self.assertEqual(summary.outcome, "partial_failure")


if __name__ == "__main__":
    unittest.main()
