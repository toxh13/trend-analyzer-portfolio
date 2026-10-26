"""v2 공용 고정 데이터(raw-root)를 다시 만드는 스크립트입니다.

시나리오와 기대 동작은 fixtures/README.md 에 정리되어 있습니다.
기준 시각(as_of)은 2026-10-24T12:00:00 (Asia/Seoul) 입니다.

    python fixtures/build_raw_fixtures.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "raw-root" / "raw"

R1 = "11111111-1111-4111-8111-111111111111"
R2 = "22222222-2222-4222-8222-222222222222"
R3 = "33333333-3333-4333-8333-333333333333"
R4 = "44444444-4444-4444-8444-444444444444"

IT = "IT/과학"
ECO = "경제"


def kw(*pairs):
    return [{"keyword": k, "occurrenceCount": c} for k, c in pairs]


def article(run_id, crawled_at, channel, source, category, n, published_at, keywords, title=None):
    return {
        "schemaVersion": 1,
        "runId": run_id,
        "channel": channel,
        "source": source,
        "category": category,
        "title": title or f"고정 기사 {n}",
        "sourceUrl": f"https://news.example.com/{channel}/{n:03d}",
        "publishedAt": published_at,
        "crawledAt": crawled_at,
        "summary": f"고정 기사 {n}의 요약입니다.",
        "keywords": keywords,
    }


NAVER = ("naver", "네이버 뉴스")
DAUM = ("daum", "다음 뉴스")
RSS_SEMI = ("rss", "Google News RSS - 반도체")
RSS_FX = ("rss", "Google News RSS - 환율")

# R1: 2026-10-22 12:17 KST 시작. 대부분 48시간 창보다 오래된 기사 (일별 추이에만 반영)
R1_CRAWLED = "2026-10-22T03:20:00Z"
r1 = [
    article(R1, R1_CRAWLED, *NAVER, IT, 1, "2026-10-22T08:00:00", kw(("반도체", 1), ("클라우드", 2))),
    article(R1, R1_CRAWLED, *NAVER, IT, 2, "2026-10-22T09:30:00", kw(("AI", 2), ("ai", 1))),  # 같은 기사 안 대소문자 중복 → AI 3
    article(R1, R1_CRAWLED, *RSS_FX, ECO, 3, "2026-10-22T10:00:00", kw(("환율", 2), ("속보", 4))),  # 속보는 차단 키워드
    article(R1, R1_CRAWLED, *RSS_SEMI, IT, 4, "2026-10-22T12:05:00", kw(("반도체", 3))),  # previous 창
]

# R2: 2026-10-23 12:17 KST 시작. daum 채널 실패로 PARTIAL_FAILURE
R2_CRAWLED = "2026-10-23T03:20:00Z"
r2 = [
    article(R2, R2_CRAWLED, *NAVER, IT, 5, "2026-10-22T13:00:00", kw(("반도체", 5), ("보안", 1))),  # previous
    article(R2, R2_CRAWLED, *NAVER, IT, 6, "2026-10-22T18:00:00", kw(("AI", 1))),  # previous, alias
    article(R2, R2_CRAWLED, *RSS_FX, ECO, 7, "2026-10-22T20:00:00", kw(("환율", 1), ("증시", 1))),  # previous
    article(R2, R2_CRAWLED, *RSS_FX, ECO, 8, "2026-10-23T07:00:00", kw(("환율", 3))),  # previous
    article(R2, R2_CRAWLED, *RSS_FX, ECO, 9, "2026-10-23T09:00:00", kw(("환율", 1))),  # previous
    article(R2, R2_CRAWLED, *NAVER, IT, 10, "2026-10-23T12:10:00", kw(("반도체", 2), ("클라우드", 1))),  # current
]

# R3: 2026-10-24 09:17 KST 시작. current 창 기사 + 오래된 RSS 기사 + R2 와 URL 이 같은 기사
R3_CRAWLED = "2026-10-24T00:20:00Z"
r3 = [
    article(R3, R3_CRAWLED, *NAVER, IT, 11, "2026-10-23T14:00:00", kw(("반도체", 1), ("인공지능", 2))),
    article(R3, R3_CRAWLED, *NAVER, IT, 12, "2026-10-23T16:00:00", kw(("인공지능", 1), ("AI", 1))),  # alias 2개, 한 번만 셈
    article(R3, R3_CRAWLED, *DAUM, IT, 13, "2026-10-23T20:00:00", kw(("반도체", 4), ("인공지능", 3), ("클라우드", 1))),
    article(R3, R3_CRAWLED, *DAUM, ECO, 14, "2026-10-24T07:30:00", kw(("반도체", 1), ("AI", 2), ("증시", 2))),  # 경제 카테고리
    article(R3, R3_CRAWLED, *RSS_FX, ECO, 15, "2026-10-24T08:00:00", kw(("환율", 1))),
    article(R3, R3_CRAWLED, *RSS_SEMI, IT, 16, "2026-10-17T10:00:00", kw(("반도체", 2))),  # 7일 전, 일별 추이에만
    # R2 의 10번 기사와 같은 URL. 먼저 수집된 R2 행이 남아야 한다
    {**article(R3, R3_CRAWLED, *NAVER, IT, 10, "2026-10-23T12:10:00", kw(("반도체", 9))), "title": "다시 수집된 고정 기사 10"},
    article(R3, R3_CRAWLED, *NAVER, IT, 17, "2026-10-24T13:00:00", kw(("반도체", 1))),  # as_of 이후 발행 → 모든 집계 제외
]

CHANNELS_OK = [
    {"channel": "naver", "outcome": "SUCCESS", "validatedArticleCount": 0, "sourceInvalidCount": 0, "successfulUnits": 2, "partialUnits": 0, "emptyUnits": 0, "failedUnits": 0},
    {"channel": "daum", "outcome": "SUCCESS", "validatedArticleCount": 0, "sourceInvalidCount": 0, "successfulUnits": 2, "partialUnits": 0, "emptyUnits": 0, "failedUnits": 0},
    {"channel": "rss", "outcome": "SUCCESS", "validatedArticleCount": 0, "sourceInvalidCount": 0, "successfulUnits": 6, "partialUnits": 0, "emptyUnits": 0, "failedUnits": 0},
]


def channels(articles, overrides=None):
    result = [dict(c) for c in CHANNELS_OK]
    for c in result:
        c["validatedArticleCount"] = sum(a["channel"] == c["channel"] for a in articles)
    for name, values in (overrides or {}).items():
        next(c for c in result if c["channel"] == name).update(values)
    return result


def run(run_id, started, completed, outcome, articles, trigger="schedule", rejected=0, channel_overrides=None):
    written = len(articles)
    return {
        "schemaVersion": 1,
        "runId": run_id,
        "startedAt": started,
        "completedAt": completed,
        "outcome": outcome,
        "trigger": trigger,
        "crawlerOutputCount": written + rejected,
        "validationRejectedCount": rejected,
        "duplicateUrlCount": 0,
        "previouslySeenCount": 0,
        "eligibleCount": written,
        "selectedCount": written,
        "droppedByLimitCount": 0,
        "preprocessingFailedCount": 0,
        "writtenCount": written,
        "writeFailedCount": 0,
        "reconciliationOk": True,
        "durationMs": 61000,
        "channels": channels(articles, channel_overrides),
        "codeVersion": "fixture",
    }


RUNS = [
    ("2026-10-22", run(R1, "2026-10-22T03:17:00Z", "2026-10-22T03:20:30Z", "SUCCESS", r1), r1),
    ("2026-10-23", run(
        R2, "2026-10-23T03:17:00Z", "2026-10-23T03:20:30Z", "PARTIAL_FAILURE", r2, rejected=1,
        channel_overrides={"daum": {"outcome": "FAILURE", "successfulUnits": 0, "failedUnits": 2}},
    ), r2),
    # 00:17 KST 시작, 수집 결과 0건 → JSONL 파일을 만들지 않는다
    ("2026-10-24", run(
        R4, "2026-10-23T15:17:00Z", "2026-10-23T15:18:10Z", "EMPTY", [],
        channel_overrides={c: {"outcome": "EMPTY", "successfulUnits": 0, "emptyUnits": 2} for c in ("naver", "daum", "rss")},
    ), []),
    ("2026-10-24", run(R3, "2026-10-24T00:17:00Z", "2026-10-24T00:20:30Z", "SUCCESS", r3, trigger="workflow_dispatch"), r3),
]


def main():
    for dt, run_doc, articles in RUNS:
        run_dir = ROOT / "runs" / f"dt={dt}"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / f"{run_doc['runId']}.json").write_text(
            json.dumps(run_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if not articles:
            continue
        article_dir = ROOT / "articles" / f"dt={dt}"
        article_dir.mkdir(parents=True, exist_ok=True)
        (article_dir / f"{run_doc['runId']}.jsonl").write_text(
            "".join(json.dumps(a, ensure_ascii=False) + "\n" for a in articles), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
