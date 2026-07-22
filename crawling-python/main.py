import os
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request

from article_validation import find_invalid_article_reason
from crawlers.article_delivery import deliver_articles
from crawlers.batch_observability import build_batch_summary
from crawlers.batch_reporting import (
    build_completed_payload,
    build_started_payload,
    report_batch_completed,
    report_batch_started,
)
from crawlers.batch_selection import select_articles_fairly
from crawlers.crawl_execution import run_sources
from crawlers.crawl_daum import crawl_daum
from crawlers.crawl_naver import crawl_naver
from nlp.keyword_extractor import keyword_extractor
from nlp.keyword_merge_recommender import recommend_keyword_merges

# 크롤링 서비스의 진입점입니다.
# - 네이버/다음/RSS 크롤러를 주기적으로 실행합니다.
# - 수집한 기사에서 키워드와 요약을 만든 뒤 Spring 백엔드로 전송합니다.
# - 백엔드가 내부 호출로 사용할 키워드 병합 추천 API도 함께 제공합니다.

# 백엔드 연동과 배치 실행 주기는 환경변수로 조정합니다.
# Docker/로컬 실행 환경마다 주소와 API 키가 달라질 수 있으므로 코드에 고정하지 않습니다.
BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "http://localhost:8080")
CRAWLING_ENDPOINT = f"{BACKEND_API_URL}/api/v1/crawling"
CRAWL_RUN_STARTED_ENDPOINT = f"{BACKEND_API_URL}/api/v1/crawling/runs"
CRAWL_RUN_COMPLETED_ENDPOINT = f"{BACKEND_API_URL}/api/v1/crawling/runs/completed"
CRAWLER_API_KEY = os.environ.get("CRAWLER_API_KEY")
MAX_NEWS_PER_BATCH = int(os.environ.get("MAX_NEWS_PER_BATCH", "50"))
CRAWLER_INTERVAL_SECONDS = int(os.environ.get("CRAWLER_INTERVAL_SECONDS", "10800"))
START_CRAWLER_LOOP = os.environ.get("START_CRAWLER_LOOP", "true").lower() == "true"

# Flask 앱은 배치 크롤러와 내부 API 엔드포인트를 동시에 담당합니다.
app = Flask(__name__)


def crawl_rss_channel():
    """RSS 의존성 import도 채널 실행 경계 안에서 처리합니다."""
    from crawlers.crawl_rss import crawl_rss
    return crawl_rss()


def run_job():
    """한 번의 크롤링 배치를 실행하고, 수집 결과를 백엔드 API로 전송합니다."""
    run_id = str(uuid.uuid4())
    batch_started_at = datetime.now(timezone.utc)
    started_at = time.perf_counter()
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] crawler batch started")

    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "X-API-KEY": CRAWLER_API_KEY or "",
    })
    report_batch_started(
        session,
        CRAWL_RUN_STARTED_ENDPOINT,
        build_started_payload(run_id, batch_started_at),
    )

    # 채널 하나의 예상하지 못한 실패가 뒤 채널 실행을 막지 않게 각각 격리합니다.
    crawl_results = run_sources([
        ("naver", crawl_naver),
        ("daum", crawl_daum),
        ("rss", crawl_rss_channel),
    ])

    # 크롤러 구현 실수나 외부 응답 변경이 있어도 오류 데이터가 NLP와 저장 단계로 넘어가지 않게 막습니다.
    invalid_reasons = Counter()
    received = sum(len(result.articles) for result in crawl_results)
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

    print(
        f"event=crawl_validation_completed received={received} "
        f"valid={sum(len(result.articles) for result in crawl_results)} "
        f"invalid={sum(invalid_reasons.values())} "
        f"reasons={dict(invalid_reasons)}"
    )

    # 배치 전체 URL 중복을 먼저 제거하고 수집 채널×카테고리별로 순환 선택합니다.
    selection = select_articles_fairly(crawl_results, MAX_NEWS_PER_BATCH)
    all_news = selection.articles
    print(
        f"event=crawl_batch_selected valid_input={selection.valid_input} "
        f"duplicate_urls={selection.duplicate_urls} eligible={selection.eligible} "
        f"selected={len(all_news)} dropped_by_limit={selection.dropped_by_limit}"
    )

    print(
        "crawl result: "
        + ", ".join(f"{result.channel}={len(result.articles)}" for result in crawl_results)
        + f", sending={len(all_news)}"
    )

    delivery = deliver_articles(session, CRAWLING_ENDPOINT, all_news, keyword_extractor)
    summary = build_batch_summary(
        crawl_results=crawl_results,
        received=received,
        invalid=sum(invalid_reasons.values()),
        selection=selection,
        delivery=delivery,
        duration_ms=int((time.perf_counter() - started_at) * 1000),
    )
    print(summary.to_log_line())
    completed_payload = build_completed_payload(
        run_id=run_id,
        started_at=batch_started_at,
        completed_at=datetime.now(timezone.utc),
        summary=summary,
        crawl_results=crawl_results,
    )
    report_batch_completed(session, CRAWL_RUN_COMPLETED_ENDPOINT, completed_payload)
    return summary


def crawler_loop():
    """서비스가 실행되는 동안 정해진 간격으로 크롤링 배치를 반복합니다."""
    while True:
        try:
            run_job()
        except Exception as exc:
            print(f"crawler batch failed: {exc}")

        print(f"waiting {CRAWLER_INTERVAL_SECONDS} seconds until next crawler batch")
        time.sleep(CRAWLER_INTERVAL_SECONDS)


def require_internal_api_key():
    """내부 API 호출에 X-API-KEY가 설정되어 있으면 같은 키인지 확인합니다."""
    expected_api_key = CRAWLER_API_KEY
    if not expected_api_key:
        return True

    return request.headers.get("X-API-KEY") == expected_api_key


@app.post("/internal/keyword-merge-suggestions/recommend")
def recommend_keyword_merge_suggestions():
    """백엔드가 후보 키워드와 선택된 대표 키워드 1개를 보내면 병합 추천 결과를 반환합니다."""
    if not require_internal_api_key():
        return jsonify({"error": "unauthorized"}), 401

    # 백엔드 DTO 필드명에 맞춰 입력값을 읽고, 누락된 값은 안전한 기본값으로 보정합니다.
    payload = request.get_json(silent=True) or {}
    candidate_keywords = payload.get("candidateKeywords") or []
    selected_target_group = payload.get("selectedTargetGroup")
    threshold = float(payload.get("threshold", 0.85))
    top_k = int(payload.get("topK", 3))

    if not selected_target_group:
        return jsonify({"error": "selectedTargetGroup is required"}), 400

    if "id" not in selected_target_group or "canonicalKeyword" not in selected_target_group:
        return jsonify({"error": "selectedTargetGroup must include id and canonicalKeyword"}), 400

    try:
        result = recommend_keyword_merges(
            candidate_keywords=candidate_keywords,
            selected_target_group=selected_target_group,
            threshold=threshold,
            top_k=top_k,
        )
        return jsonify(result)
    except Exception as exc:
        print(f"keyword recommendation failed: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.get("/health")
def health():
    """컨테이너와 로드밸런서가 서비스 생존 여부를 확인하는 헬스체크입니다."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print(f"crawler service starting. backend={BACKEND_API_URL}")

    # Flask API 서버와 크롤링 루프를 같이 띄우기 위해 배치 루프는 백그라운드 스레드로 실행합니다.
    if START_CRAWLER_LOOP:
        threading.Thread(target=crawler_loop, daemon=True).start()

    app.run(host="0.0.0.0", port=5000)
