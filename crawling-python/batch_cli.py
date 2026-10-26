import argparse
import json
import os
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from article_validation import find_invalid_article_reason
from crawlers.article_delivery import preprocess_article
from crawlers.batch_selection import select_articles_fairly
from crawlers.crawl_execution import run_sources
from crawlers.raw_output import (
    RawRunCounts,
    articles_path,
    build_article_record,
    build_run_payload,
    format_utc,
    load_seen_urls,
    run_path,
    seoul_date,
    write_text_atomic,
)

# v2 수집 배치의 1회 실행 진입점입니다.
# - v1 main.run_job()과 같은 수집 → 검증 → 중복 제거 → 순환 선택 → 키워드·요약 흐름을 탑니다.
# - 결과는 Spring API 대신 contracts/raw 형식 파일로 씁니다. GitHub Actions가 이 파일을 data 브랜치에 커밋합니다.
# - v2에서는 이미 수집한 URL(--seen-urls)을 선택 전에 제외해 한도를 신규 기사로 채웁니다.
#
#   python batch_cli.py --output-dir ../out [--seen-urls state/seen_urls.txt] [--source-fixture tests/fixtures/source_fixture.json]
#
# 종료 코드는 outcome이 FAILURE일 때만 1이고, 마지막 줄에 run JSON 경로를 출력합니다.

TRIGGERS = ("schedule", "workflow_dispatch", "backfill", "local")


def crawl_naver_channel():
    from crawlers.crawl_naver import crawl_naver
    return crawl_naver()


def crawl_daum_channel():
    from crawlers.crawl_daum import crawl_daum
    return crawl_daum()


def crawl_rss_channel():
    """RSS 의존성 import도 채널 실행 경계 안에서 처리합니다."""
    from crawlers.crawl_rss import crawl_rss
    return crawl_rss()


LIVE_SOURCES = [
    ("naver", crawl_naver_channel),
    ("daum", crawl_daum_channel),
    ("rss", crawl_rss_channel),
]


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="뉴스를 1회 수집해 contracts/raw 형식 파일로 씁니다.")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="raw/articles/dt=*/<runId>.jsonl, raw/runs/dt=*/<runId>.json 을 만들 디렉터리")
    parser.add_argument("--seen-urls", type=Path,
                        help="이미 수집한 URL 목록(한 줄에 하나). 없으면 제외 단계를 생략합니다")
    parser.add_argument("--max-articles", type=int,
                        default=int(os.environ.get("MAX_NEWS_PER_BATCH", "50")),
                        help="배치당 최대 기사 수 (기본 MAX_NEWS_PER_BATCH 또는 50)")
    parser.add_argument("--trigger", choices=TRIGGERS, default="local")
    parser.add_argument("--code-version", default=os.environ.get("GITHUB_SHA") or "local")
    parser.add_argument("--source-fixture", type=Path,
                        help='네트워크 대신 {"naver":[...],"daum":[...],"rss":[...]} 기사를 사용합니다')
    return parser.parse_args(argv)


def run_batch(args: argparse.Namespace, keyword_extractor=None) -> tuple[dict, Path]:
    """배치를 한 번 실행하고 (run JSON 내용, run JSON 경로)를 반환합니다.

    중간에 예외가 나도 그 시점까지 센 수량으로 FAILURE run JSON을 남깁니다.
    """
    run_id = str(uuid.uuid4())
    batch_started_at = datetime.now(timezone.utc)
    started_at = time.perf_counter()
    dt = seoul_date(batch_started_at)
    counts = RawRunCounts()
    failed = False
    print(f"event=crawl_batch_started run_id={run_id} trigger={args.trigger} dt={dt.isoformat()}")

    try:
        _collect_and_write(args, run_id, dt, counts, keyword_extractor)
    except Exception as exc:
        failed = True
        print(f"event=crawl_batch_failed run_id={run_id} error={type(exc).__name__}: {exc}")

    completed_at = datetime.now(timezone.utc)
    payload = build_run_payload(
        run_id=run_id,
        started_at=batch_started_at,
        completed_at=completed_at,
        outcome=counts.outcome(failed=failed),
        trigger=args.trigger,
        counts=counts,
        duration_ms=int((time.perf_counter() - started_at) * 1000),
        code_version=args.code_version,
    )
    path = run_path(args.output_dir, dt, run_id)
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(
        f"event=crawl_batch_completed outcome={payload['outcome']} "
        f"received={counts.received} rejected={counts.validation_rejected} "
        f"duplicate_urls={counts.duplicate_urls} previously_seen={counts.previously_seen} "
        f"eligible={counts.eligible} selected={counts.selected} dropped_by_limit={counts.dropped_by_limit} "
        f"preprocessing_failed={counts.preprocessing_failed} written={counts.written} "
        f"write_failed={counts.write_failed} reconciliation_ok={str(counts.reconciliation_ok).lower()} "
        f"duration_ms={payload['durationMs']}"
    )
    return payload, path


def _collect_and_write(args, run_id: str, dt, counts: RawRunCounts, keyword_extractor) -> None:
    if keyword_extractor is None:
        from nlp.keyword_extractor import keyword_extractor

    # 입력 파일 오류는 수집 전에 드러나게 먼저 읽습니다.
    seen_urls = load_seen_urls(args.seen_urls) if args.seen_urls else None
    if args.source_fixture:
        from crawlers.source_fixture import load_source_fixture
        source_specs = load_source_fixture(args.source_fixture)
    else:
        source_specs = LIVE_SOURCES

    # 채널 하나의 예상하지 못한 실패가 뒤 채널 실행을 막지 않게 각각 격리합니다.
    crawl_results = run_sources(source_specs)
    counts.channels = crawl_results
    counts.received = sum(len(result.articles) for result in crawl_results)

    # 오류 데이터가 NLP와 파일 쓰기 단계로 넘어가지 않게 막습니다(v1과 같은 규칙).
    invalid_reasons = Counter()
    for result in crawl_results:
        valid_articles = []
        for news in result.articles:
            invalid_reason = find_invalid_article_reason(news)
            if invalid_reason:
                invalid_reasons[invalid_reason] += 1
                print(
                    f"event=crawl_article_skipped reason={invalid_reason} "
                    f"source={news.get('source', 'unknown')} category={news.get('category', 'unknown')}"
                )
                continue
            valid_articles.append(news)
        result.articles = valid_articles
    counts.validation_rejected = sum(invalid_reasons.values())
    print(
        f"event=crawl_validation_completed received={counts.received} "
        f"valid={counts.received - counts.validation_rejected} "
        f"invalid={counts.validation_rejected} reasons={dict(invalid_reasons)}"
    )

    # 선택 결과에는 채널 정보가 없으므로, 같은 dict 객체를 기준으로 채널을 기억해 둡니다.
    channel_by_article = {id(article): result.channel for result in crawl_results for article in result.articles}

    selection = select_articles_fairly(crawl_results, args.max_articles, seen_urls=seen_urls)
    counts.valid_input = selection.valid_input
    counts.duplicate_urls = selection.duplicate_urls
    counts.previously_seen = selection.previously_seen
    counts.eligible = selection.eligible
    counts.selected = len(selection.articles)
    counts.dropped_by_limit = selection.dropped_by_limit
    print(
        f"event=crawl_batch_selected valid_input={selection.valid_input} "
        f"duplicate_urls={selection.duplicate_urls} previously_seen={selection.previously_seen} "
        f"eligible={selection.eligible} selected={counts.selected} "
        f"dropped_by_limit={selection.dropped_by_limit}"
    )

    crawled_at = format_utc(datetime.now(timezone.utc))
    lines = []
    for article in selection.articles:
        try:
            payload = preprocess_article(article, keyword_extractor)
            record = build_article_record(payload, run_id, channel_by_article[id(article)], crawled_at)
        except Exception as exc:
            counts.preprocessing_failed += 1
            print(f"article preprocessing failed: {exc}")
            continue

        try:
            lines.append(json.dumps(record, ensure_ascii=False))
        except (TypeError, ValueError) as exc:
            counts.write_failed += 1
            print(f"article serialization failed: {exc}")

    # 0건이면 JSONL을 만들지 않습니다. 파일은 통째로 쓰고 rename하므로 일부만 기록되는 경우는 없습니다.
    if not lines:
        return
    try:
        write_text_atomic(articles_path(args.output_dir, dt, run_id), "\n".join(lines) + "\n")
    except OSError as exc:
        counts.write_failed += len(lines)
        print(f"article file write failed: {exc}")
        return
    counts.written = len(lines)


def main(argv=None, keyword_extractor=None) -> int:
    args = parse_args(argv)
    try:
        payload, path = run_batch(args, keyword_extractor=keyword_extractor)
    except Exception as exc:
        # run JSON조차 쓰지 못한 경우입니다. 경로를 출력할 수 없으므로 실패로 끝냅니다.
        print(f"event=crawl_run_file_failed error={type(exc).__name__}: {exc}")
        return 1
    print(path)
    return 1 if payload["outcome"] == "FAILURE" else 0


if __name__ == "__main__":
    sys.exit(main())
