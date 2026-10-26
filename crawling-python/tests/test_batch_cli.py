import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import batch_cli

CRAWLER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CRAWLER_ROOT.parent
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SOURCE_FIXTURE = FIXTURE_DIR / "source_fixture.json"
SEEN_URLS = FIXTURE_DIR / "seen_urls.txt"


def stub_extractor(content: str):
    return [{"keyword": "테스트", "occurrenceCount": 1}]


def article(number: int, category: str = "IT/과학", content: str = "본문", channel: str = "naver") -> dict:
    return {
        "title": f"기사 {number}",
        "content": content,
        "sourceUrl": f"https://example.com/{channel}/{number}",
        "source": "네이버 뉴스",
        "category": category,
        "publishedAt": "2026-10-24T09:00:00",
    }


class BatchCliTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.output_dir = self.root / "out"

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_fixture(self, fixture: dict) -> Path:
        path = self.root / "fixture.json"
        path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
        return path

    def run_cli(self, *extra_args, extractor=stub_extractor):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = batch_cli.main(
                ["--output-dir", str(self.output_dir), "--code-version", "test", *map(str, extra_args)],
                keyword_extractor=extractor,
            )
        last_line = stdout.getvalue().strip().splitlines()[-1]
        return exit_code, last_line

    def run_files(self):
        return sorted(self.output_dir.glob("raw/runs/dt=*/*.json"))

    def article_files(self):
        return sorted(self.output_dir.glob("raw/articles/dt=*/*.jsonl"))

    def read_run(self) -> dict:
        (run_file,) = self.run_files()
        return json.loads(run_file.read_text(encoding="utf-8"))

    def read_articles(self) -> list[dict]:
        return [
            json.loads(line)
            for path in self.article_files()
            for line in path.read_text(encoding="utf-8").splitlines()
        ]

    def assert_contract_valid(self):
        completed = subprocess.run(
            [sys.executable, str(REPO_ROOT / "contracts" / "validate.py"), "--raw-root", str(self.output_dir)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def assert_reconciles(self, run: dict):
        self.assertTrue(run["reconciliationOk"])
        valid_input = run["crawlerOutputCount"] - run["validationRejectedCount"]
        self.assertEqual(valid_input, run["duplicateUrlCount"] + run["previouslySeenCount"] + run["eligibleCount"])
        self.assertEqual(run["eligibleCount"], run["selectedCount"] + run["droppedByLimitCount"])
        self.assertEqual(
            run["selectedCount"],
            run["preprocessingFailedCount"] + run["writtenCount"] + run["writeFailedCount"],
        )

    def test_source_fixture_output_satisfies_contract_and_reconciles(self):
        exit_code, last_line = self.run_cli("--source-fixture", SOURCE_FIXTURE, "--seen-urls", SEEN_URLS)

        self.assertEqual(exit_code, 0)
        self.assert_contract_valid()
        run = self.read_run()
        self.assertEqual(last_line, str(self.run_files()[0]))
        self.assertEqual(run["outcome"], "PARTIAL_FAILURE")
        self.assertEqual(run["trigger"], "local")
        self.assertEqual(run["codeVersion"], "test")
        self.assertEqual(
            {key: run[key] for key in (
                "crawlerOutputCount", "validationRejectedCount", "duplicateUrlCount", "previouslySeenCount",
                "eligibleCount", "selectedCount", "droppedByLimitCount", "writtenCount",
            )},
            {
                "crawlerOutputCount": 8,
                "validationRejectedCount": 1,
                "duplicateUrlCount": 1,
                "previouslySeenCount": 1,
                "eligibleCount": 5,
                "selectedCount": 5,
                "droppedByLimitCount": 0,
                "writtenCount": 5,
            },
        )
        self.assert_reconciles(run)
        self.assertEqual(
            [(channel["channel"], channel["outcome"], channel["failedUnits"]) for channel in run["channels"]],
            [("naver", "SUCCESS", 0), ("daum", "FAILURE", 2), ("rss", "SUCCESS", 0)],
        )

        articles = self.read_articles()
        urls = [item["sourceUrl"] for item in articles]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertNotIn("https://news.example.com/naver/103", urls)  # seen URL
        self.assertNotIn("예시 기사 101 (RSS 중복)", [item["title"] for item in articles])  # 배치 안 중복은 먼저 온 것만
        self.assertEqual({item["runId"] for item in articles}, {run["runId"]})
        self.assertEqual(
            {(item["channel"], item["source"]) for item in articles},
            {("naver", "네이버 뉴스"), ("rss", "Google News RSS - 반도체"), ("rss", "Google News RSS - 환율")},
        )
        self.assertTrue(all("content" not in item for item in articles))

    def test_seen_urls_are_excluded_before_limit(self):
        fixture = self.write_fixture({"naver": [article(number) for number in range(1, 6)]})
        seen = self.root / "seen.txt"
        seen.write_text("https://example.com/naver/1\n\nhttps://example.com/naver/2\n", encoding="utf-8")

        exit_code, _ = self.run_cli("--source-fixture", fixture, "--seen-urls", seen, "--max-articles", 2)

        self.assertEqual(exit_code, 0)
        run = self.read_run()
        self.assertEqual(run["previouslySeenCount"], 2)
        self.assertEqual(run["eligibleCount"], 3)
        self.assertEqual(run["selectedCount"], 2)
        self.assertEqual(run["droppedByLimitCount"], 1)
        self.assertEqual(run["outcome"], "SUCCESS")
        self.assert_reconciles(run)
        # 한도 2건이 이미 본 기사가 아니라 신규 기사로 채워집니다.
        self.assertEqual(
            [item["sourceUrl"] for item in self.read_articles()],
            ["https://example.com/naver/3", "https://example.com/naver/4"],
        )

    def test_empty_run_writes_only_run_json(self):
        fixture = self.write_fixture({"naver": [], "daum": [], "rss": []})

        exit_code, last_line = self.run_cli("--source-fixture", fixture, "--trigger", "schedule")

        self.assertEqual(exit_code, 0)
        self.assertEqual(self.article_files(), [])
        run = self.read_run()
        self.assertEqual(run["outcome"], "EMPTY")
        self.assertEqual(run["trigger"], "schedule")
        self.assertEqual(run["writtenCount"], 0)
        self.assertTrue(run["reconciliationOk"])
        self.assertEqual(last_line, str(self.run_files()[0]))
        self.assert_contract_valid()

    def test_failed_channel_is_isolated_as_partial_failure(self):
        fixture = self.write_fixture({
            "naver": [article(1)],
            "daum": {"raise": "daum unavailable"},
            "rss": [article(2, channel="rss")],
        })

        exit_code, _ = self.run_cli("--source-fixture", fixture)

        self.assertEqual(exit_code, 0)
        run = self.read_run()
        self.assertEqual(run["outcome"], "PARTIAL_FAILURE")
        self.assertEqual(run["writtenCount"], 2)
        daum = run["channels"][1]
        self.assertEqual((daum["channel"], daum["outcome"], daum["failedUnits"]), ("daum", "FAILURE", 1))
        self.assert_contract_valid()

    def test_unreadable_input_leaves_failure_run_and_exit_code_1(self):
        broken = self.root / "broken.json"
        broken.write_text("{not json", encoding="utf-8")

        exit_code, last_line = self.run_cli("--source-fixture", broken)

        self.assertEqual(exit_code, 1)
        run = self.read_run()
        self.assertEqual(run["outcome"], "FAILURE")
        self.assertEqual(run["channels"], [])
        self.assertEqual(last_line, str(self.run_files()[0]))
        self.assertEqual(self.article_files(), [])
        self.assert_contract_valid()

    def test_exception_after_crawling_keeps_counts_collected_so_far(self):
        fixture = self.write_fixture({"naver": [article(1), article(2)]})

        with patch("batch_cli.select_articles_fairly", side_effect=RuntimeError("selection bug")):
            exit_code, _ = self.run_cli("--source-fixture", fixture)

        self.assertEqual(exit_code, 1)
        run = self.read_run()
        self.assertEqual(run["outcome"], "FAILURE")
        self.assertEqual(run["crawlerOutputCount"], 2)
        self.assertEqual(run["channels"][0]["channel"], "naver")
        # 선택 단계 이후 수량을 모르므로 대사식이 맞지 않는다는 사실도 그대로 남깁니다.
        self.assertFalse(run["reconciliationOk"])
        self.assertEqual(self.article_files(), [])
        self.assert_contract_valid()

    def test_preprocessing_failure_is_counted_and_not_written(self):
        fixture = self.write_fixture({"naver": [article(1, content="정상"), article(2, content="실패")]})

        def extractor(content):
            if content == "실패":
                raise RuntimeError("NLP failed")
            return stub_extractor(content)

        exit_code, _ = self.run_cli("--source-fixture", fixture, extractor=extractor)

        self.assertEqual(exit_code, 0)
        run = self.read_run()
        self.assertEqual(run["preprocessingFailedCount"], 1)
        self.assertEqual(run["writtenCount"], 1)
        self.assertEqual(run["outcome"], "PARTIAL_FAILURE")
        self.assert_reconciles(run)

    def test_all_selected_articles_failing_is_failure(self):
        fixture = self.write_fixture({"naver": [article(1)]})

        def extractor(content):
            raise RuntimeError("NLP failed")

        exit_code, _ = self.run_cli("--source-fixture", fixture, extractor=extractor)

        self.assertEqual(exit_code, 1)
        self.assertEqual(self.read_run()["outcome"], "FAILURE")
        self.assertEqual(self.article_files(), [])

    def test_summary_is_cut_at_150_characters(self):
        fixture = self.write_fixture({"naver": [
            article(1, content="가" * 150),
            article(2, content="나" * 151),
        ]})

        self.run_cli("--source-fixture", fixture)

        summaries = [item["summary"] for item in self.read_articles()]
        self.assertEqual(summaries, ["가" * 150, "나" * 150 + "..."])

    def test_unwritable_output_dir_exits_1_without_path(self):
        fixture = self.write_fixture({"naver": [article(1)]})
        blocker = self.root / "file"
        blocker.write_text("", encoding="utf-8")
        self.output_dir = blocker / "out"

        exit_code, last_line = self.run_cli("--source-fixture", fixture)

        self.assertEqual(exit_code, 1)
        self.assertIn("event=crawl_run_file_failed", last_line)

    def test_defaults_come_from_environment(self):
        with patch.dict("os.environ", {"MAX_NEWS_PER_BATCH": "7", "GITHUB_SHA": "abc123"}):
            args = batch_cli.parse_args(["--output-dir", "out"])

        self.assertEqual(args.max_articles, 7)
        self.assertEqual(args.code_version, "abc123")
        self.assertEqual(args.trigger, "local")
        self.assertIsNone(args.seen_urls)


class LazyKonlpyImportTest(unittest.TestCase):
    def test_batch_cli_import_does_not_load_konlpy(self):
        completed = subprocess.run(
            [sys.executable, "-c", "import sys, batch_cli, nlp.keyword_extractor; print('konlpy' in sys.modules)"],
            cwd=CRAWLER_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
