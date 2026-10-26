import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from crawlers.article_delivery import preprocess_article, summarize_content
from crawlers.crawl_result import CrawlResult
from crawlers.raw_output import (
    RawRunCounts,
    build_article_record,
    format_utc,
    seoul_date,
    write_text_atomic,
)


def payload(**overrides) -> dict:
    base = {
        "title": "기사",
        "sourceUrl": "https://example.com/1",
        "source": "네이버 뉴스",
        "category": "IT/과학",
        "publishedAt": "2026-10-24T09:00:00",
        "summary": "요약",
        "keywords": [{"keyword": "반도체", "occurrenceCount": 2}],
    }
    base.update(overrides)
    return base


class SummaryTest(unittest.TestCase):
    def test_summary_boundary_matches_v1(self):
        self.assertEqual(summarize_content("a" * 149), "a" * 149)
        self.assertEqual(summarize_content("a" * 150), "a" * 150)
        self.assertEqual(summarize_content("a" * 151), "a" * 150 + "...")

    def test_preprocess_does_not_mutate_original_article(self):
        article = {"title": "기사", "content": "본문"}

        result = preprocess_article(article, lambda content: [{"keyword": "본문", "occurrenceCount": 1}])

        self.assertEqual(article, {"title": "기사", "content": "본문"})
        self.assertEqual(
            result,
            {"title": "기사", "keywords": [{"keyword": "본문", "occurrenceCount": 1}], "summary": "본문"},
        )


class ArticleRecordTest(unittest.TestCase):
    def test_builds_contract_record_with_stripped_url(self):
        record = build_article_record(
            payload(sourceUrl=" https://example.com/1 "), "run-1", "naver", "2026-10-24T00:00:00Z"
        )

        self.assertEqual(record["sourceUrl"], "https://example.com/1")
        self.assertEqual(record["schemaVersion"], 1)
        self.assertEqual(record["channel"], "naver")
        self.assertNotIn("content", record)

    def test_rejects_values_that_break_contract(self):
        for overrides in (
            {"publishedAt": "2026-10-24 09:00"},
            {"sourceUrl": "javascript:alert(1)"},
            {"title": "가" * 1001},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                build_article_record(payload(**overrides), "run-1", "naver", "2026-10-24T00:00:00Z")


class RawRunCountsTest(unittest.TestCase):
    def test_previously_seen_is_part_of_reconciliation(self):
        counts = RawRunCounts(
            received=5, validation_rejected=1, valid_input=4, duplicate_urls=1, previously_seen=1,
            eligible=2, selected=2, written=2,
        )
        self.assertTrue(counts.reconciliation_ok)

        counts.previously_seen = 0
        self.assertFalse(counts.reconciliation_ok)
        self.assertEqual(counts.outcome(), "FAILURE")

    def test_all_seen_without_failures_is_empty(self):
        result = CrawlResult(channel="naver")
        result.record_unit("success")
        counts = RawRunCounts(received=3, valid_input=3, previously_seen=3, channels=[result])

        self.assertEqual(counts.outcome(), "EMPTY")


class TimeAndFileTest(unittest.TestCase):
    def test_dt_uses_seoul_date_of_batch_start(self):
        self.assertEqual(seoul_date(datetime(2026, 10, 23, 15, 30, tzinfo=timezone.utc)).isoformat(), "2026-10-24")
        self.assertEqual(seoul_date(datetime(2026, 10, 23, 14, 59, tzinfo=timezone.utc)).isoformat(), "2026-10-23")

    def test_format_utc_uses_z_suffix(self):
        seoul = timezone(timedelta(hours=9))
        self.assertEqual(format_utc(datetime(2026, 10, 24, 9, 0, 1, 500, tzinfo=seoul)), "2026-10-24T00:00:01Z")
        with self.assertRaises(ValueError):
            format_utc(datetime(2026, 10, 24))

    def test_atomic_write_leaves_no_partial_file_on_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "raw" / "runs" / "run.json"

            with patch("crawlers.raw_output.os.replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    write_text_atomic(target, "{}")

            self.assertEqual(list(target.parent.iterdir()), [])

            write_text_atomic(target, "{}\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "{}\n")
            self.assertEqual([path.name for path in target.parent.iterdir()], ["run.json"])


if __name__ == "__main__":
    unittest.main()
