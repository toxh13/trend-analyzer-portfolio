"""v1 Java 테스트 케이스를 작은 고정 입력으로 옮겨 analytics/tests/parity/<case>/ 를 다시 만듭니다.

    python analytics/tests/parity/build_cases.py

각 케이스 디렉터리
- raw-root/raw/articles/dt=*/<runId>.jsonl : Java 테스트의 기사·근거 행을 원천 기사로 옮긴 것
- seeds/keyword_aliases.csv, seeds/blocked_keywords.csv : Java mock 의 alias·차단 키워드
- expected.json : Java 단언(assert)에서 가져온 기대값과 출처

Java 테스트는 저장소(repository)를 mock 해서 스냅샷 행이나 집계 행을 직접 넣습니다. v2 는 원천 기사에서 시작하므로
같은 스냅샷·집계 행이 나오는 기사를 만들어 넣습니다. 계산식으로 만들 수 없는 mock 값(예: hotness 95.5)은
단언이 확인하는 성질(순위·변화 방향·합산)이 그대로 남도록 바꾸고 expected.json 의 "adapted" 에 이유를 적습니다.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_ID = "00000000-0000-4000-8000-000000000001"
AS_OF = "2026-07-18T15:30:00"  # Java 테스트 고정 시계 2026-07-18T06:30:00Z (서울 15:30)
JAVA_TEST_ROOT = "backend-spring/src/test/java/com/example/backendspring/service"

CASES: list[dict] = []


def case(name: str, java: str, as_of: str = AS_OF, aliases=(), blocked=(), adapted: str | None = None):
    spec = {"name": name, "java": java, "asOf": as_of, "aliases": list(aliases), "blocked": list(blocked),
            "articles": [], "checks": [], "snapshot": None, "adapted": adapted}
    CASES.append(spec)
    return spec


def art(spec, published_at, category, keywords, *, url=None, title=None, summary=None, source="테스트 언론사"):
    n = len(spec["articles"]) + 1
    spec["articles"].append({
        "schemaVersion": 1,
        "runId": RUN_ID,
        "channel": "naver",
        "source": source,
        "category": category,
        "title": title or f"{spec['name']} 기사 {n}",
        "sourceUrl": url or f"https://parity.example.com/{spec['name']}/{n:03d}",
        "publishedAt": published_at,
        "crawledAt": "2026-07-20T01:00:00Z",
        "summary": summary or f"{spec['name']} 기사 {n} 요약",
        "keywords": [{"keyword": k, "occurrenceCount": c} for k, c in keywords],
    })


def check(spec, file, path=(), **expect):
    spec["checks"].append({"file": file, "path": list(path), **expect})


def minutes(base_hour_minute: str, day: str, offset: int) -> str:
    hour, minute = map(int, base_hour_minute.split(":"))
    total = hour * 60 + minute + offset
    return f"{day}T{total // 60:02d}:{total % 60:02d}:00"


# ---------------------------------------------------------------- TrendAnalysticServiceTest

c = case(
    "analytic_canonical_article_grain",
    "TrendAnalysticServiceTest.analyzeAndUpdateTrendsUsesCanonicalArticleGrainAndNonOverlappingWindows",
    aliases=[("AI", "인공지능")],
)
art(c, "2026-07-18T14:00:00", "IT", [("AI", 1), ("인공지능", 1)])  # 같은 기사의 alias 두 개 → 1건
art(c, "2026-07-18T13:00:00", "경제", [("AI", 1)])
art(c, "2026-07-17T14:00:00", "IT", [("AI", 1)])  # previous 창
c["snapshot"] = [
    {"keyword": "인공지능", "category": "IT", "mention_count": 1, "velocity_score": 0, "hotness_score": 0.4},
    {"keyword": "인공지능", "category": "경제", "mention_count": 1, "velocity_score": 1, "hotness_score": 1.0},
]

c = case(
    "analytic_previous_only_keyword",
    "TrendAnalysticServiceTest.analyzeAndUpdateTrendsKeepsFallingKeywordAndReplacesStaleSnapshot",
)
art(c, "2026-07-17T14:00:00", "IT", [("레거시", 1)])
c["snapshot"] = [
    {"keyword": "레거시", "category": "IT", "mention_count": 0, "velocity_score": -1, "hotness_score": -0.6},
]

c = case(
    "analytic_decrease_minus_four",
    "TrendAnalysticServiceTest.analyzeAndUpdateTrendsStoresActualArticleCountDecrease",
)
for article_id in range(1, 12):
    art(c, minutes("14:00", "2026-07-17", article_id), "경제", [("미국", 1)])
for article_id in range(12, 19):
    art(c, minutes("14:00", "2026-07-18", article_id), "경제", [("미국", 1)])
c["snapshot"] = [
    {"keyword": "미국", "category": "경제", "mention_count": 7, "velocity_score": -4, "hotness_score": 0.4},
]

c = case(
    "analytic_blocked_raw_and_canonical",
    "TrendAnalysticServiceTest.analyzeAndUpdateTrendsExcludesBlockedRawAndCanonicalKeywords",
    aliases=[("AI", "인공지능")],
    blocked=["광고", "인공지능"],
)
art(c, "2026-07-18T14:00:00", "IT", [("광고", 1), ("AI", 1)])
c["snapshot"] = []
check(c, "trends/all.json", length=0)

c = case(
    "analytic_half_open_windows",
    "TrendAnalysticServiceTest.analyzeAndUpdateTrendsUsesHalfOpenWindowBoundaries",
)
art(c, "2026-07-16T15:30:00", "IT", [("LLM", 1)])  # previous 시작 (포함)
art(c, "2026-07-17T15:30:00", "IT", [("LLM", 1)])  # current 시작 (포함)
art(c, "2026-07-18T15:30:00", "IT", [("LLM", 1)])  # as_of (제외)
c["snapshot"] = [
    {"keyword": "LLM", "category": "IT", "mention_count": 1, "velocity_score": 0, "hotness_score": 0.4},
]

# ---------------------------------------------------------------- TrendServiceTest: 추이

c = case(
    "history_seoul_calendar_window",
    "TrendServiceTest.getKeyword7DaysHistoryUsesSeoulCalendarWindow",
)
art(c, "2026-07-16T10:00:00", "IT", [("LLM", 5)])  # Java row {2026-07-16, 101, 5}
art(c, "2026-07-18T09:00:00", "IT", [("LLM", 1)])  # Java row {2026-07-18, 102, 1}
art(c, "2026-07-18T16:00:00", "IT", [("LLM", 1)])  # 조회 끝(now) 이후 → 제외 (v1 endDateTime = nowInSeoul)
LLM = "{keyword:LLM}"
check(c, f"keywords/{LLM}.json", ["daily", 23, "day"], equals="2026-07-12")  # 7일 창의 첫날
check(c, f"keywords/{LLM}.json", ["daily", {"day": "2026-07-16"}, "articleCount"], equals=1)
check(c, f"keywords/{LLM}.json", ["daily", {"day": "2026-07-16"}, "weightedScore"], equals=1.16)
check(c, f"keywords/{LLM}.json", ["daily", {"day": "2026-07-17"}, "articleCount"], equals=0)
check(c, f"keywords/{LLM}.json", ["daily", {"day": "2026-07-17"}, "weightedScore"], equals=0.0)
check(c, f"keywords/{LLM}.json", ["daily", 29, "day"], equals="2026-07-18")
check(c, f"keywords/{LLM}.json", ["daily", {"day": "2026-07-18"}, "articleCount"], equals=1)
check(c, f"keywords/{LLM}.json", ["today"], equals="2026-07-18")  # partial = (day == today)

c = case(
    "history_article_count_and_weight",
    "TrendServiceTest.getKeywordHistorySeparatesArticleCountAndWeightedScore",
    aliases=[("AI", "인공지능")],
)
art(c, "2026-07-18T09:00:00", "IT", [("AI", 3), ("인공지능", 2)])  # 묶음 weight 합 5 (Java row 201, 5)
art(c, "2026-07-18T10:00:00", "IT", [("인공지능", 1)])  # Java row 202, 1
check(c, "keywords/{keyword:인공지능}.json", ["daily", {"day": "2026-07-18"}, "articleCount"], equals=2)
check(c, "keywords/{keyword:인공지능}.json", ["daily", {"day": "2026-07-18"}, "weightedScore"], equals=2.16)

c = case(
    "compare_same_canonical_rejected",
    "TrendServiceTest.compareKeywordHistoryRejectsSameCanonicalKeyword, "
    "TrendEvidenceServiceTest.getHistoryEvidenceRejectsSameCanonicalKeyword",
    aliases=[("AI", "인공지능")],
    adapted="거부 자체(400)는 static 어댑터(작업 C)가 한다. 여기서는 판단 근거인 aliasToCanonical 이 "
            "'AI' 와 ' 인공지능 ' 을 같은 대표 키워드로 해석하는지 확인한다.",
)
art(c, "2026-07-18T09:00:00", "IT", [("AI", 1)])
art(c, "2026-07-18T10:00:00", "IT", [("인공지능", 1)])
check(c, "keywords/index.json", ["aliasToCanonical", "ai"], equals="인공지능")  # normalize("AI")
check(c, "keywords/index.json", ["aliasToCanonical", "인공지능"], equals="인공지능")  # normalize(" 인공지능 ")

c = case(
    "compare_shared_window",
    "TrendServiceTest.compareKeywordHistorySharesOneWindow",
    aliases=[("AI", "인공지능")],
)
art(c, "2026-07-17T09:00:00", "IT", [("AI", 1)])
art(c, "2026-07-18T09:00:00", "IT", [("인공지능", 1)])
art(c, "2026-07-16T09:00:00", "IT", [("반도체", 1)])
art(c, "2026-07-18T11:00:00", "IT", [("반도체", 1)])
for keyword in ("인공지능", "반도체"):
    file = f"keywords/{{keyword:{keyword}}}.json"
    check(c, file, ["timezone"], equals="Asia/Seoul")
    check(c, file, ["today"], equals="2026-07-18")
    check(c, file, ["daily"], length=30)
    check(c, file, ["daily", 23, "day"], equals="2026-07-12")
check(c, "keywords/index.json", ["aliasToCanonical", "ai"], equals="인공지능")

# ---------------------------------------------------------------- TrendServiceTest: 목록·통계

c = case(
    "top20_rank_and_change",
    "TrendServiceTest.getTop20TrendTest",
    adapted="mock hotness(95.5, 88.0)는 계산식으로 만들 수 없어 같은 순위·변화 방향이 나오는 기사 수로 바꿨다 "
            "(AI cur 3/prev 1, Crypto cur 1/prev 2).",
)
for hour in (10, 11, 12):
    art(c, f"2026-07-18T{hour}:00:00", "TECH", [("AI", 1)])
art(c, "2026-07-17T10:00:00", "TECH", [("AI", 1)])
art(c, "2026-07-18T10:00:00", "FINANCE", [("Crypto", 1)])
art(c, "2026-07-17T10:00:00", "FINANCE", [("Crypto", 1)])
art(c, "2026-07-17T11:00:00", "FINANCE", [("Crypto", 1)])
check(c, "trends/all.json", length=2)
check(c, "trends/all.json", [0, "rank"], equals=1)
check(c, "trends/all.json", [0, "keyword"], equals="AI")
check(c, "trends/all.json", [0, "changeType"], equals="up")
check(c, "trends/all.json", [0, "changeValue"], equals=2)
check(c, "trends/all.json", [1, "rank"], equals=2)
check(c, "trends/all.json", [1, "keyword"], equals="Crypto")
check(c, "trends/all.json", [1, "changeType"], equals="down")
check(c, "trends/all.json", [1, "changeValue"], equals=1)

c = case(
    "category_top20",
    "TrendServiceTest.getTop20CategoryTrendTest",
    adapted="mock hotness 대신 AI(cur 3/prev 1, 2.4) > Docker(cur 4/prev 5, 1.0) > Spring(cur 1/prev 1, 0.4) 로 "
            "같은 순서와 up/down/same 을 만든다.",
)
for hour in (9, 10, 11):
    art(c, f"2026-07-18T{hour:02d}:00:00", "TECH", [("AI", 1)])
art(c, "2026-07-17T09:00:00", "TECH", [("AI", 1)])
for hour in (9, 10, 11, 12):
    art(c, f"2026-07-18T{hour:02d}:30:00", "TECH", [("Docker", 1)])
for hour in (9, 10, 11, 12, 13):
    art(c, f"2026-07-17T{hour:02d}:30:00", "TECH", [("Docker", 1)])
art(c, "2026-07-18T08:00:00", "TECH", [("Spring", 1)])
art(c, "2026-07-17T08:00:00", "TECH", [("Spring", 1)])
TECH = "trends/category/{category:TECH}.json"
check(c, TECH, length=3)
check(c, TECH, [0, "rank"], equals=1)
check(c, TECH, [0, "keyword"], equals="AI")
check(c, TECH, [0, "changeType"], equals="up")
check(c, TECH, [1, "rank"], equals=2)
check(c, TECH, [1, "changeType"], equals="down")
check(c, TECH, [2, "rank"], equals=3)
check(c, TECH, [2, "changeType"], equals="same")

c = case(
    "articles_alias_bundle",
    "TrendServiceTest.getArticlesContainingKeywordTest",
    aliases=[("AI", "인공지능"), ("Artificial Intelligence", "인공지능")],
    adapted="Java 는 두 기사 모두 LocalDateTime.now() 라 mock 반환 순서로 정렬을 확인한다. "
            "여기서는 'AI 플랫폼 출시' 를 더 늦게 발행해 같은 순서가 정렬로 나오게 했다.",
)
art(c, "2026-07-18T10:00:00", "IT", [("AI", 1)], title="AI 플랫폼 출시", url="https://test1.com/news/1", source="네이버")
art(c, "2026-07-18T09:00:00", "TECH", [("인공지능", 1)], title="인공지능 투자 확대", url="https://test2.com/news/2",
    source="다음")
AI_FILE = "keywords/{keyword:인공지능}.json"
check(c, AI_FILE, ["searchKeywords"], equals=["AI", "Artificial Intelligence", "인공지능"])
check(c, AI_FILE, ["articles"], length=2)
check(c, AI_FILE, ["articles", 0, "title"], equals="AI 플랫폼 출시")
check(c, AI_FILE, ["articles", 1, "title"], equals="인공지능 투자 확대")

c = case(
    "merge_aliases_sum",
    "TrendServiceTest.getTop20TrendMergesAliases",
    aliases=[("AI", "인공지능"), ("Artificial Intelligence", "인공지능")],
    adapted="mock score 30.0(10.0 + 20.0)은 계산식 값이 아니다. 같은 기사 수(AI cur 5/prev 3, "
            "Artificial Intelligence cur 7/prev 4)에서 계산식 합 12×0.4 + 5×0.6 = 7.8 을 기대값으로 쓴다.",
)
for i in range(5):
    art(c, minutes("09:00", "2026-07-18", i), "TECH", [("AI", 1)])
for i in range(3):
    art(c, minutes("09:00", "2026-07-17", i), "TECH", [("AI", 1)])
for i in range(7):
    art(c, minutes("10:00", "2026-07-18", i), "TECH", [("Artificial Intelligence", 1)])
for i in range(4):
    art(c, minutes("10:00", "2026-07-17", i), "TECH", [("Artificial Intelligence", 1)])
check(c, "trends/all.json", length=1)
check(c, "trends/all.json", [0, "keyword"], equals="인공지능")
check(c, "trends/all.json", [0, "mention_count"], equals=12)
check(c, "trends/all.json", [0, "changeValue"], equals=5)
check(c, "trends/all.json", [0, "score"], approx=7.8)

c = case(
    "surging_canonical_snapshot",
    "TrendServiceTest.getTopSurgingTrendsUsesCanonicalSnapshot",
    aliases=[("AI", "인공지능")],
    adapted="mock 클라우드(mention 2, velocity 3)는 previous 가 음수여야 해서 만들 수 없다. "
            "mention 3/previous 0 으로 바꿔도 단언(순서 클라우드 → 인공지능, 인공지능 mention 7·changeValue 1)은 같다.",
)
for i in range(3):
    art(c, minutes("09:00", "2026-07-18", i), "IT", [("AI", 1)])
art(c, "2026-07-17T09:00:00", "IT", [("AI", 1)])
for i in range(4):
    art(c, minutes("10:00", "2026-07-18", i), "경제", [("인공지능", 1)])
for i in range(5):
    art(c, minutes("10:00", "2026-07-17", i), "경제", [("인공지능", 1)])
for i in range(3):
    art(c, minutes("11:00", "2026-07-18", i), "IT", [("클라우드", 1)])
check(c, "trends/surging/all.json", length=2)
check(c, "trends/surging/all.json", [0, "keyword"], equals="클라우드")
check(c, "trends/surging/all.json", [1, "keyword"], equals="인공지능")
check(c, "trends/surging/all.json", [1, "mention_count"], equals=7)
check(c, "trends/surging/all.json", [1, "changeValue"], equals=1)

c = case(
    "popular_excludes_previous_only",
    "TrendServiceTest.getTopMentionedTrendsExcludesPreviousOnlyMetrics",
)
art(c, "2026-07-18T09:00:00", "IT", [("LLM", 1)])
art(c, "2026-07-18T10:00:00", "IT", [("LLM", 1)])
art(c, "2026-07-17T10:00:00", "IT", [("LLM", 1)])
for i in range(3):
    art(c, minutes("11:00", "2026-07-17", i), "IT", [("레거시", 1)])
check(c, "trends/popular.json", length=1)
check(c, "trends/popular.json", [0, "keyword"], equals="LLM")

c = case(
    "dashboard_stats_window",
    "TrendServiceTest.getDashboardStatsUsesKstClockAndMetricSnapshot",
    adapted="Java 는 기사 수 6·키워드 수 2 를 mock 으로 넣는다. 같은 값이 나오도록 current 창 기사 6건"
            "(LLM 5, 블록체인 1)을 만들고, 창 시작(포함)·끝(제외) 경계 기사를 더했다.",
)
art(c, "2026-07-17T15:30:00", "IT", [("LLM", 1)])  # 창 시작 = as_of-24h (포함)
for hour in (9, 10, 11, 12):
    art(c, f"2026-07-18T{hour:02d}:00:00", "IT", [("LLM", 1)])
art(c, "2026-07-17T09:00:00", "IT", [("LLM", 1)])
art(c, "2026-07-17T10:00:00", "IT", [("LLM", 1)])
art(c, "2026-07-18T13:00:00", "IT", [("블록체인", 1)])
for i in range(5):
    art(c, minutes("08:00", "2026-07-17", i), "IT", [("블록체인", 1)])
art(c, "2026-07-18T15:30:00", "IT", [("기타", 1)])  # 창 끝 = as_of (제외)
check(c, "stats/all.json", ["analyzedArticles"], equals=6)
check(c, "stats/all.json", ["trackedKeywords"], equals=2)
check(c, "stats/all.json", ["risingKeyword", "keyword"], equals="LLM")
check(c, "stats/all.json", ["risingKeyword", "changeAmount"], equals=3)
check(c, "stats/all.json", ["fallingKeyword", "keyword"], equals="블록체인")
check(c, "stats/all.json", ["fallingKeyword", "changeAmount"], equals=-4)
check(c, "stats/all.json", ["windowHours"], equals=24)

# ---------------------------------------------------------------- TrendEvidenceServiceTest

c = case(
    "evidence_seoul_half_open_alias",
    "TrendEvidenceServiceTest.getHistoryEvidenceUsesSeoulHalfOpenWindowAliasesAndLimit",
    as_of="2026-07-20T10:00:00",
    aliases=[("AI", "인공지능"), ("세미컨덕터", "반도체")],
    adapted="Java 는 날짜 7/19 근거를 limit 2 로 조회한다. 정적 파일은 날짜별 최신 5건을 담고 화면이 limit 만큼 자른다. "
            "날짜 경계(7/18 23:59, 7/20 00:00) 기사를 더해 반개구간을 확인한다.",
)
art(c, "2026-07-19T23:59:00", "IT/과학", [("AI", 1)], title="최신 기사", summary="최신 요약", url="https://example.com/2")
art(c, "2026-07-19T00:00:00", "IT/과학", [("인공지능", 1)], title="이전 기사", summary="이전 요약",
    url="https://example.com/1")
art(c, "2026-07-20T00:00:00", "IT/과학", [("AI", 1)], title="다음 날 기사")
art(c, "2026-07-18T23:59:00", "IT/과학", [("인공지능", 1)], title="전날 기사")
art(c, "2026-07-18T09:00:00", "IT/과학", [("반도체", 1)])
art(c, "2026-07-18T10:00:00", "IT/과학", [("세미컨덕터", 1)])
AI_EVIDENCE = "keywords/{keyword:인공지능}.json"
check(c, AI_EVIDENCE, ["searchKeywords"], equals=["AI", "인공지능"])
check(c, AI_EVIDENCE, ["evidenceByDay", "2026-07-19"], length=2)
check(c, AI_EVIDENCE, ["evidenceByDay", "2026-07-19", 0, "title"], equals="최신 기사")
check(c, AI_EVIDENCE, ["evidenceByDay", "2026-07-19", 1, "title"], equals="이전 기사")
check(c, AI_EVIDENCE, ["evidenceByDay", "2026-07-19", 0, "summary"], equals="최신 요약")
check(c, AI_EVIDENCE, ["evidenceByDay", "2026-07-19", 0, "source"], equals="테스트 언론사")
check(c, AI_EVIDENCE, ["evidenceByDay", "2026-07-19", 0, "publishedAt"], equals="2026-07-19T23:59:00+09:00")
check(c, AI_EVIDENCE, ["evidenceByDay", "2026-07-19", 0, "sourceUrl"], equals="https://example.com/2")
check(c, "keywords/{keyword:반도체}.json", ["searchKeywords"], equals=["반도체", "세미컨덕터"])
check(c, "keywords/{keyword:반도체}.json", ["evidenceByDay", "2026-07-19"], absent=True)

# ---------------------------------------------------------------- Java 코드 규칙 (테스트 없음)

c = case(
    "daily_weight_half_up",
    "TrendService.roundToThreeDecimals (코드: Math.round(value * 1000.0) / 1000.0)",
    adapted="Java 테스트에는 없는 규칙이라 v1 코드에서 기대값을 계산했다. occurrence 16 기사 3건 → "
            "3 × 1.1875 = 3.5625 → Math.round → 3.563 (Python round 는 3.562).",
)
for hour in (9, 10, 11):
    art(c, f"2026-07-18T{hour:02d}:00:00", "IT", [("LLM", 16)])
check(c, "keywords/{keyword:LLM}.json", ["daily", {"day": "2026-07-18"}, "weightedScore"], equals=3.563)


# ---------------------------------------------------------------- 쓰기


def java_location(name: str) -> str:
    """'TrendServiceTest.method' → 'backend-spring/.../TrendServiceTest.java#method'."""
    if "Test." not in name:
        return name
    cls, method = name.split(".", 1)
    return f"{JAVA_TEST_ROOT}/{cls}.java#{method}"


def write_case(spec: dict) -> None:
    root = HERE / spec["name"]
    if root.exists():
        shutil.rmtree(root)
    seeds = root / "seeds"
    seeds.mkdir(parents=True)
    with (seeds / "keyword_aliases.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["alias", "canonical_keyword", "approved_at", "note"])
        for alias, canonical in spec["aliases"]:
            writer.writerow([alias, canonical, "2026-07-01", "parity"])
    with (seeds / "blocked_keywords.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["keyword", "reason"])
        for keyword in spec["blocked"]:
            writer.writerow([keyword, "parity"])

    articles = root / "raw-root" / "raw" / "articles" / f"dt={spec['asOf'][:10]}"
    articles.mkdir(parents=True)
    (articles / f"{RUN_ID}.jsonl").write_text(
        "".join(json.dumps(a, ensure_ascii=False) + "\n" for a in spec["articles"]), encoding="utf-8"
    )

    expected = {
        "java": [java_location(name.strip()) for name in spec["java"].split(",")],
        "asOf": spec["asOf"],
        "adapted": spec["adapted"],
        "snapshot": spec["snapshot"],
        "checks": spec["checks"],
    }
    (root / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    for spec in CASES:
        write_case(spec)
    print(f"wrote {len(CASES)} parity cases to {HERE}")


if __name__ == "__main__":
    main()
