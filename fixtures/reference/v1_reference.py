"""v1 Spring 집계 로직을 Python으로 직역한 기준 구현(동등성 오라클)입니다.

용도
- dbt 모델(analytics/)과 export_site.py 결과가 v1과 같은지 비교하는 정답지
- fixtures/site/data/ 고정 정적 JSON 생성 (프론트 static 어댑터 개발용)

운영 경로에서는 쓰지 않습니다. 성능보다 v1 코드와의 대응 관계가 읽히는 것을 우선합니다.
각 함수 docstring에 대응하는 v1 위치를 적었습니다.

    python fixtures/reference/v1_reference.py \
        --raw-root fixtures/raw-root --seeds fixtures/seeds \
        --as-of 2026-10-24T12:00:00 --generated-at 2026-10-24T03:00:00Z \
        --code-version fixture --out fixtures/site/data

v1과 일부러 다르게 한 점 (docs/v2/DESIGN.md 5.1)
- 카테고리를 넘어 합산한 목록 행의 category: mention 최대 → 이름 오름차순 (v1은 DB 순서상 처음 행)
- 정렬 동점: 키워드 오름차순으로 결정적 처리 (v1은 HashMap 순서)
- 기사 목록·근거 기사는 as_of 이전 발행분만, 기사 목록은 최신 100건
- score(hotness)는 소수 넷째 자리 반올림 (v1 Java float 오차 제거)

일별 weightedScore 반올림은 v1 과 같은 half-up(Math.round) 입니다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")
WINDOW = timedelta(hours=24)
HISTORY_DAYS = 30
TOP_LIMIT = 20
LIST_FILE_LIMIT = 50
ARTICLE_LIMIT = 100
EVIDENCE_LIMIT = 5
KEYWORD_FILE_LIMIT = 3000
REPEATED_MENTION_BONUS_LIMIT = 0.2


# ---------------------------------------------------------------- 정규화 · alias


def normalize_keyword(value: str | None) -> str:
    """v1 KeywordNormalizer.normalize: trim → 소문자 → 공백 제거 → '.' 제거 → '-' 제거."""
    if value is None:
        return ""
    return "".join(value.strip().lower().split()).replace(".", "").replace("-", "")


def normalize_for_compare(value: str | None) -> str:
    """v1 CrawlingService/TrendAnalysticService.normalizeForCompare: trim → 소문자."""
    return "" if value is None else value.strip().lower()


def slug(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def article_id(source_url: str) -> str:
    return "article-" + slug(source_url)


@dataclass
class Aliases:
    alias_map: dict[str, str] = field(default_factory=dict)
    canonical_map: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    @classmethod
    def load(cls, path: Path) -> "Aliases":
        """v1 KeywordAliasCacheService.reload (승인된 alias 만 시드에 있다고 본다)."""
        aliases = cls()
        with path.open(encoding="utf-8") as file:
            for row in csv.DictReader(file):
                alias, canonical = row["alias"], row["canonical_keyword"]
                aliases.alias_map[normalize_keyword(alias)] = canonical
                aliases.canonical_map[normalize_keyword(canonical)].update({canonical, alias})
        return aliases

    def resolve(self, raw: str) -> str:
        """v1 resolveKeyword."""
        return self.alias_map.get(normalize_keyword(raw), raw)

    def search_keywords(self, keyword: str) -> set[str]:
        """v1 resolveSearchKeywords."""
        canonical = self.alias_map.get(normalize_keyword(keyword), keyword)
        result = set(self.canonical_map.get(normalize_keyword(canonical), set()))
        result.update({keyword, canonical})
        return {value for value in result if value and value.strip()}

    def aliases_of(self, canonical: str) -> list[str]:
        return sorted(self.search_keywords(canonical) - {canonical})


def load_blocked(path: Path) -> set[str]:
    with path.open(encoding="utf-8") as file:
        return {normalize_for_compare(row["keyword"]) for row in csv.DictReader(file)}


# ---------------------------------------------------------------- 원천 적재


@dataclass
class Article:
    id: str
    title: str
    summary: str
    source_url: str
    source: str
    category: str
    published_at: datetime  # 서울 로컬, naive
    keywords: dict[str, int]  # 저장된 원본 키워드 → weight


def parse_local(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def store_keywords(raw_keywords: list[dict], blocked: set[str]) -> dict[str, int]:
    """v1 CrawlingService.saveCrawledData 의 키워드 저장 규칙.

    - normalizeForCompare 기준으로 같은 키워드를 합치고 첫 표기를 유지, 횟수는 max(1, n) 합산
    - 차단 키워드 제외, weight = max(1, n)
    """
    unique: dict[str, tuple[str, int]] = {}
    for item in raw_keywords:
        keyword = item.get("keyword")
        if keyword is None:
            continue
        key = normalize_for_compare(keyword)
        count = max(1, int(item.get("occurrenceCount") or 0))
        if key in unique:
            first, existing = unique[key]
            unique[key] = (first, max(1, existing) + count)
        else:
            unique[key] = (keyword, count)

    stored: dict[str, int] = {}
    for keyword, count in unique.values():
        text = keyword.strip()
        if not text or normalize_for_compare(text) in blocked:
            continue
        stored[text] = max(1, count)
    return stored


def load_articles(raw_root: Path, blocked: set[str]) -> list[Article]:
    """sourceUrl 기준 최초 수집 행만 남긴다 (v1 existsBySourceUrl 스킵 + unique 제약)."""
    rows = []
    for path in sorted((raw_root / "raw" / "articles").glob("dt=*/*.jsonl")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            if line.strip():
                doc = json.loads(line)
                rows.append((parse_utc(doc["crawledAt"]), doc["runId"], line_no, doc))
    rows.sort(key=lambda row: row[:3])

    seen: set[str] = set()
    articles = []
    for _, _, _, doc in rows:
        url = doc["sourceUrl"]
        if url in seen:
            continue
        seen.add(url)
        articles.append(Article(
            id=article_id(url),
            title=doc["title"],
            summary=doc["summary"],
            source_url=url,
            source=doc["source"],
            category=doc["category"].strip(),
            published_at=parse_local(doc["publishedAt"]),
            keywords=store_keywords(doc["keywords"], blocked),
        ))
    return articles


def load_runs(raw_root: Path) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((raw_root / "raw" / "runs").glob("dt=*/*.json"))
    ]


# ---------------------------------------------------------------- 스냅샷 (TrendAnalysticService)


@dataclass(frozen=True)
class MetricRow:
    keyword: str
    category: str
    mention: int
    velocity: int

    @property
    def hotness(self) -> float:
        return self.mention * 0.4 + self.velocity * 0.6


def build_snapshot(articles, aliases: Aliases, blocked: set[str], as_of: datetime) -> list[MetricRow]:
    """v1 TrendAnalysticService.analyzeAndReplaceSnapshot."""
    current_start = as_of - WINDOW
    previous_start = current_start - WINDOW
    unique: set[tuple[str, str, str, str]] = set()
    for article in articles:
        published = article.published_at
        if published < previous_start or not published < as_of:
            continue
        window = "PREVIOUS" if published < current_start else "CURRENT"
        for raw in article.keywords:
            canonical = aliases.resolve(raw)
            if not canonical or not canonical.strip() or not article.category:
                continue
            if normalize_for_compare(raw) in blocked or normalize_for_compare(canonical) in blocked:
                continue
            unique.add((article.id, canonical.strip(), article.category, window))

    counts: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for _, keyword, category, window in unique:
        counts[(keyword, category)][0 if window == "CURRENT" else 1] += 1

    return [
        MetricRow(keyword, category, current, current - previous)
        for (keyword, category), (current, previous) in sorted(counts.items(), key=lambda item: (item[0][1], item[0][0]))
    ]


# ---------------------------------------------------------------- 목록 API (TrendService)


@dataclass
class Merged:
    keyword: str
    mention: int = 0
    velocity: int = 0
    hotness: float = 0.0
    mention_by_category: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def category(self) -> str:
        return sorted(self.mention_by_category.items(), key=lambda item: (-item[1], item[0]))[0][0]


def merge_aliases(rows: list[MetricRow], aliases: Aliases) -> list[Merged]:
    """v1 TrendService.mergeAliases (category 결정 규칙만 v2 방식)."""
    merged: dict[str, Merged] = {}
    for row in rows:
        display = aliases.resolve(row.keyword)
        summary = merged.setdefault(display, Merged(display))
        summary.mention += row.mention
        summary.velocity += row.velocity
        summary.hotness += row.hotness
        summary.mention_by_category[row.category] += row.mention
    return list(merged.values())


def to_dto(items: list[Merged]) -> list[dict]:
    """v1 convertSummariesToDtoList → TrendingResponseDto."""
    result = []
    for rank, item in enumerate(items, start=1):
        change = "up" if item.velocity > 0 else "down" if item.velocity < 0 else "same"
        result.append({
            "id": f"keyword-{item.keyword}",
            "keyword": item.keyword,
            "category": item.category,
            "score": round(item.hotness, 4),
            "mention_count": item.mention,
            "rank": rank,
            "changeType": change,
            "changeValue": abs(int(item.velocity)),
        })
    return result


def top_by_hotness(rows, aliases, limit=TOP_LIMIT):
    """v1 getTop20Trend / getTop20CategoryTrend."""
    items = [m for m in merge_aliases(rows, aliases) if m.mention > 0]
    items.sort(key=lambda m: (-m.hotness, -m.mention, m.keyword))
    return to_dto(items[:limit])


def popular(rows, aliases, limit=LIST_FILE_LIMIT):
    """v1 getTopMentionedTrends: mention 내림차순, hotness 내림차순."""
    items = [m for m in merge_aliases(rows, aliases) if m.mention > 0]
    items.sort(key=lambda m: (-m.mention, -m.hotness, m.keyword))
    return to_dto(items[:limit])


def surging(rows, aliases, limit=LIST_FILE_LIMIT):
    """v1 getTopSurgingTrends: velocity 내림차순, mention 내림차순."""
    items = [m for m in merge_aliases(rows, aliases) if m.mention > 0 and m.velocity > 0]
    items.sort(key=lambda m: (-m.velocity, -m.mention, m.keyword))
    return to_dto(items[:limit])


def top_changed(merged: list[Merged], rising: bool):
    """v1 findTopChangedKeyword: |velocity| 내림차순, mention 내림차순."""
    candidates = [m for m in merged if (m.velocity > 0 if rising else m.velocity < 0)]
    if not candidates:
        return None
    best = sorted(candidates, key=lambda m: (-abs(m.velocity), -m.mention, m.keyword))[0]
    return {"keyword": best.keyword, "mentionCount": best.mention, "changeAmount": int(best.velocity)}


def stats(articles, rows, aliases, as_of, category=None):
    """v1 getDashboardStatsWithin24Hours."""
    start = as_of - WINDOW
    in_window = [
        a for a in articles
        if start <= a.published_at < as_of and (category is None or a.category == category)
    ]
    tracked = {keyword for a in in_window for keyword in a.keywords}
    scoped = [r for r in rows if category is None or r.category == category]
    merged = merge_aliases(scoped, aliases)
    return {
        "analyzedArticles": len(in_window),
        "trackedKeywords": len(tracked),
        "risingKeyword": top_changed(merged, True),
        "fallingKeyword": top_changed(merged, False),
        "windowHours": 24,
    }


def categories(articles, rows):
    """v1 CategoryService.getAvailableCategories (TreeMap → 이름 오름차순)."""
    names = sorted({a.category for a in articles if a.category})
    counts = defaultdict(int)
    for row in rows:
        counts[row.category] += 1
    return [{"id": n, "label": n, "trendCount": counts[n], "slug": slug(n)} for n in names]


# ---------------------------------------------------------------- 키워드 상세 (history / articles / evidence)


def article_weight(occurrence: int) -> float:
    """v1 calculateArticleWeight."""
    return 1.0 + REPEATED_MENTION_BONUS_LIMIT * (1.0 - (1.0 / occurrence))


def round_three_decimals(value: float) -> float:
    """v1 roundToThreeDecimals: Math.round(value * 1000.0) / 1000.0 (half-up).

    Python round() 는 half-even 이라 3.5625 처럼 정확히 중간인 값에서 Java 와 결과가 달라진다.
    """
    return math.floor(value * 1000.0 + 0.5) / 1000.0


def to_offset(published: datetime) -> str:
    return published.replace(tzinfo=SEOUL).isoformat()


def keyword_detail(keyword, articles, aliases, as_of, generated_at):
    """v1 buildKeywordHistory(30일) + getArticlesContainingKeyword + findEvidenceByKeywordsWithinWindow."""
    search = aliases.search_keywords(keyword)
    today = as_of.date()
    start_day = today - timedelta(days=HISTORY_DAYS - 1)
    start = datetime.combine(start_day, datetime.min.time())

    matching = []
    for article in articles:
        occurrence = sum(weight for raw, weight in article.keywords.items() if raw in search)
        if occurrence and article.published_at < as_of:
            matching.append((article, occurrence))

    daily = {start_day + timedelta(days=i): [0, 0.0] for i in range(HISTORY_DAYS)}
    for article, occurrence in matching:
        if article.published_at >= start:
            bucket = daily[article.published_at.date()]
            bucket[0] += 1
            bucket[1] += article_weight(max(1, occurrence))

    newest = sorted(matching, key=lambda pair: (pair[0].published_at, pair[0].id), reverse=True)
    evidence: dict[str, list[dict]] = {}
    for article, _ in newest:
        day = article.published_at.date()
        if day < start_day:
            continue
        bucket = evidence.setdefault(day.isoformat(), [])
        if len(bucket) < EVIDENCE_LIMIT:
            bucket.append({
                "id": article.id,
                "title": article.title,
                "summary": article.summary,
                "source": article.source,
                "publishedAt": to_offset(article.published_at),
                "sourceUrl": article.source_url,
            })

    return {
        "schemaVersion": 1,
        "keyword": keyword,
        "slug": slug(keyword),
        "aliases": aliases.aliases_of(keyword),
        "searchKeywords": sorted(search),
        "timezone": "Asia/Seoul",
        "today": today.isoformat(),
        "generatedAt": generated_at,
        "daily": [
            {"day": day.isoformat(), "articleCount": count, "weightedScore": round_three_decimals(score)}
            for day, (count, score) in sorted(daily.items())
        ],
        "articles": [
            {
                "id": article.id,
                "title": article.title,
                "source": article.source,
                "date": article.published_at.strftime("%Y-%m-%dT%H:%M:%S"),
                "url": article.source_url,
            }
            for article, _ in newest[:ARTICLE_LIMIT]
        ],
        "evidenceByDay": dict(sorted(evidence.items())),
    }


def select_detail_keywords(articles, aliases, blocked, as_of, listed: set[str]):
    """30일 기사 2건 이상이거나 목록에 나온 대표 키워드 (최대 3,000개)."""
    start = datetime.combine(as_of.date() - timedelta(days=HISTORY_DAYS - 1), datetime.min.time())
    count_by_keyword: dict[str, set[str]] = defaultdict(set)
    for article in articles:
        if start <= article.published_at < as_of:
            for raw in article.keywords:
                canonical = aliases.resolve(raw).strip()
                if canonical and normalize_for_compare(canonical) not in blocked:
                    count_by_keyword[canonical].add(article.id)
    chosen = [k for k, ids in count_by_keyword.items() if len(ids) >= 2 or k in listed]
    chosen.sort(key=lambda k: (-len(count_by_keyword[k]), k))
    return chosen[:KEYWORD_FILE_LIMIT], {k: len(v) for k, v in count_by_keyword.items()}


# ---------------------------------------------------------------- 메타 · 실행 이력


def freshness(last_success: datetime | None, as_of_utc: datetime):
    if last_success is None:
        return "down", None
    hours = round((as_of_utc - last_success).total_seconds() / 3600, 2)
    return ("ok" if hours <= 6 else "stale" if hours <= 24 else "down"), hours


def build_site(raw_root: Path, seeds: Path, as_of: datetime, generated_at: str, code_version: str) -> dict[str, object]:
    aliases = Aliases.load(seeds / "keyword_aliases.csv")
    blocked = load_blocked(seeds / "blocked_keywords.csv")
    articles = load_articles(raw_root, blocked)
    as_of_utc = as_of.replace(tzinfo=SEOUL).astimezone(timezone.utc)
    runs = [r for r in load_runs(raw_root) if parse_utc(r["startedAt"]) <= as_of_utc]
    rows = build_snapshot(articles, aliases, blocked, as_of)

    files: dict[str, object] = {}
    cats = categories(articles, rows)
    files["categories.json"] = cats
    files["trends/all.json"] = top_by_hotness(rows, aliases)
    files["trends/popular.json"] = popular(rows, aliases)
    files["trends/surging/all.json"] = surging(rows, aliases)
    files["stats/all.json"] = stats(articles, rows, aliases, as_of)
    for cat in cats:
        scoped = [r for r in rows if r.category == cat["id"]]
        files[f"trends/category/{cat['slug']}.json"] = top_by_hotness(scoped, aliases)
        files[f"trends/surging/{cat['slug']}.json"] = surging(scoped, aliases)
        files[f"stats/{cat['slug']}.json"] = stats(articles, rows, aliases, as_of, cat["id"])

    listed = {
        item["keyword"]
        for name, value in files.items() if name.startswith("trends/")
        for item in value
    }
    chosen, article_counts = select_detail_keywords(articles, aliases, blocked, as_of, listed)
    mention_by_keyword = {m.keyword: m.mention for m in merge_aliases(rows, aliases)}
    index_items = []
    alias_to_canonical: dict[str, str] = {}
    for keyword in chosen:
        files[f"keywords/{slug(keyword)}.json"] = keyword_detail(keyword, articles, aliases, as_of, generated_at)
        index_items.append({
            "keyword": keyword,
            "slug": slug(keyword),
            "aliases": aliases.aliases_of(keyword),
            "mentionCount": mention_by_keyword.get(keyword, 0),
            "articleCount30d": article_counts.get(keyword, 0),
        })
        for variant in [keyword, *aliases.aliases_of(keyword)]:
            alias_to_canonical[normalize_keyword(variant)] = keyword
    index_items.sort(key=lambda item: (-item["mentionCount"], -item["articleCount30d"], item["keyword"]))
    files["keywords/index.json"] = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "keywords": index_items,
        "aliasToCanonical": dict(sorted(alias_to_canonical.items())),
    }

    runs_desc = sorted(runs, key=lambda r: r["startedAt"], reverse=True)
    files["runs/recent.json"] = {
        "generatedAt": generated_at,
        "runs": [
            {
                **{k: r[k] for k in (
                    "runId", "startedAt", "completedAt", "outcome", "trigger", "selectedCount", "writtenCount",
                    "previouslySeenCount", "validationRejectedCount", "reconciliationOk", "durationMs",
                )},
                "channels": [
                    {k: c[k] for k in ("channel", "outcome", "validatedArticleCount")} for c in r["channels"]
                ],
            }
            for r in runs_desc[:50]
        ],
    }

    completed = sorted(runs, key=lambda r: r["completedAt"])
    last = completed[-1] if completed else None
    successes = [r for r in completed if r["outcome"] in ("SUCCESS", "PARTIAL_FAILURE")]
    last_success = parse_utc(successes[-1]["completedAt"]) if successes else None
    state, hours = freshness(last_success, as_of_utc)
    window_start = datetime.combine(as_of.date() - timedelta(days=HISTORY_DAYS - 1), datetime.min.time())
    files["meta.json"] = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "asOf": as_of.strftime("%Y-%m-%dT%H:%M:%S"),
        "timezone": "Asia/Seoul",
        "lastRun": None if last is None else {k: last[k] for k in ("runId", "completedAt", "outcome")},
        "lastSuccessfulRunAt": successes[-1]["completedAt"] if successes else None,
        "freshness": state,
        "freshnessHours": hours,
        "counts": {
            "articles30d": sum(window_start <= a.published_at < as_of for a in articles),
            "keywords30d": len(article_counts),
            "runs7d": sum(parse_utc(r["startedAt"]) >= as_of_utc - timedelta(days=7) for r in runs),
        },
        "codeVersion": code_version,
    }
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--seeds", type=Path, required=True)
    parser.add_argument("--as-of", required=True, help="Asia/Seoul 로컬 YYYY-MM-DDTHH:MM:SS")
    parser.add_argument("--generated-at", required=True, help="UTC ...Z")
    parser.add_argument("--code-version", default="local")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    files = build_site(args.raw_root, args.seeds, parse_local(args.as_of), args.generated_at, args.code_version)
    for name, value in files.items():
        path = args.out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(files)} files to {args.out}")


if __name__ == "__main__":
    main()
