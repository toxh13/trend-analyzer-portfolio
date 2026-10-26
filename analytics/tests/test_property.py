"""속성 테스트: 무작위 원천 데이터에서 기준 구현과 dbt 결과(정적 JSON 전체)가 같은지 비교한다.

생성기는 v1 규칙의 경계를 일부러 자주 건드린다.
- alias 표기 변형(AI, ai, A.I., ' AI '), 대표 키워드끼리의 연쇄 alias, 차단 키워드(원본·대표)
- 기사 안 대소문자 중복, 공백뿐인 키워드, 반복 언급(occurrence 16 → 반올림 중간값)
- 24시간 창 경계 정각, as_of 이후 발행, 30일 밖 기사, 다른 실행의 같은 URL, 앞뒤 공백 카테고리
- 0건 실행, 실패 실행, as_of 이후에 시작한 실행

케이스 수는 PROPERTY_CASES 환경 변수로 바꾼다 (기본 150). 실패하면 seed 를 메시지에 남긴다.
"""

from __future__ import annotations

import csv
import json
import os
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tests.helpers import GENERATED_AT, diff_sites, load_reference
from tests.replay import CompiledProject

import export_site

CASES = int(os.environ.get("PROPERTY_CASES", "150"))

KEYWORDS = [
    "AI", "ai", " AI ", "A.I.", "인공지능", "Artificial Intelligence", "artificial-intelligence",
    "반도체", "세미컨덕터", "Cloud", "cloud", "클라우드", " 클라우드", "LLM", "llm",
    "환율", "증시", "보안", "속보", "광고", "  ", "생성형 AI", "생성형AI", "로봇", "배터리",
]
ALIAS_CANDIDATES = [
    ("AI", "인공지능"), ("A.I.", "인공지능"), ("Artificial Intelligence", "인공지능"),
    ("세미컨덕터", "반도체"), ("Cloud", "클라우드"), ("생성형 AI", "생성형AI"),
    ("인공지능", "AI 기술"),  # 대표 키워드가 다시 alias 인 연쇄 (v1 은 한 단계만 해석)
    ("llm", "LLM"),
]
BLOCKED_CANDIDATES = ["속보", "광고", "인공지능", "AI 기술", " 보안 ", "cloud"]
CATEGORIES = ["IT/과학", "경제", " 경제 ", "사회", "세계"]
CHANNELS = [("naver", "네이버 뉴스"), ("daum", "다음 뉴스"), ("rss", "Google News RSS - 반도체")]
OUTCOMES = ["SUCCESS", "PARTIAL_FAILURE", "EMPTY", "FAILURE"]
RUN_OUTCOMES = ["SUCCESS"] * 4 + ["PARTIAL_FAILURE"] * 2 + ["EMPTY", "FAILURE"]


def fmt_local(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def fmt_utc(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def random_published(rng: random.Random, as_of: datetime) -> datetime:
    roll = rng.random()
    if roll < 0.15:  # 창 경계 정각
        return as_of - timedelta(hours=rng.choice([0, 24, 48]))
    if roll < 0.7:  # 두 창 안
        return as_of - timedelta(minutes=rng.randint(1, 48 * 60 + 30))
    if roll < 0.95:  # 30일 추이
        return as_of - timedelta(days=rng.randint(2, 34), minutes=rng.randint(0, 1439))
    return as_of + timedelta(minutes=rng.randint(1, 600))  # as_of 이후


def random_keywords(rng: random.Random) -> list[dict]:
    picked = rng.sample(KEYWORDS, rng.choice([0, 1, 2, 3, 4, 5, 5]))
    return [
        {"keyword": keyword, "occurrenceCount": rng.choice([1, 1, 1, 2, 3, 5, 16])}
        for keyword in picked
    ]


def make_case(rng: random.Random, root: Path) -> str:
    as_of = datetime(2026, 10, 24, rng.randint(0, 23), rng.choice([0, 30, rng.randint(0, 59)]), rng.choice([0, 0, 17]))
    as_of_utc = as_of - timedelta(hours=9)

    seeds = root / "seeds"
    seeds.mkdir(parents=True)
    with (seeds / "keyword_aliases.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["alias", "canonical_keyword", "approved_at", "note"])
        for alias, canonical in rng.sample(ALIAS_CANDIDATES, rng.randint(0, len(ALIAS_CANDIDATES))):
            writer.writerow([alias, canonical, "2026-10-01", "property"])
    with (seeds / "blocked_keywords.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["keyword", "reason"])
        for keyword in rng.sample(BLOCKED_CANDIDATES, rng.randint(0, 3)):
            writer.writerow([keyword, "property"])

    url_count = 0 if rng.random() < 0.02 else rng.randint(5, 60)  # 가끔 기사 없는 실행만 있는 경우
    urls = [f"https://news.example.com/p/{n:04d}" for n in range(url_count)]
    for run_index in range(rng.choice([0] + [1, 2, 3, 4, 5, 6] * 5)):  # 가끔 실행이 하나도 없는 첫 배포
        run_id = str(uuid.UUID(int=rng.getrandbits(128), version=4))
        started = as_of_utc - timedelta(hours=rng.randint(-3, 60), minutes=rng.randint(0, 59))
        crawled = started + timedelta(minutes=rng.randint(1, 5))
        completed = crawled + timedelta(seconds=rng.randint(0, 120))
        outcome = rng.choice(RUN_OUTCOMES)
        lines = []
        if outcome not in ("EMPTY", "FAILURE") and urls:
            for url in rng.sample(urls, rng.randint(1, min(len(urls), 25))):
                channel, source = rng.choice(CHANNELS)
                lines.append({
                    "schemaVersion": 1, "runId": run_id, "channel": channel, "source": source,
                    "category": rng.choice(CATEGORIES), "title": f"{url} 제목 {run_index}",
                    "sourceUrl": url, "publishedAt": fmt_local(random_published(rng, as_of)),
                    "crawledAt": fmt_utc(crawled), "summary": f"{url} 요약 {run_index}",
                    "keywords": random_keywords(rng),
                })
        day = (started + timedelta(hours=9)).date().isoformat()
        if lines:
            path = root / "raw-root" / "raw" / "articles" / f"dt={day}" / f"{run_id}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines), encoding="utf-8")
        written = len(lines)
        run = {
            "schemaVersion": 1, "runId": run_id, "startedAt": fmt_utc(started), "completedAt": fmt_utc(completed),
            "outcome": outcome, "trigger": rng.choice(["schedule", "workflow_dispatch", "backfill", "local"]),
            "crawlerOutputCount": written, "validationRejectedCount": 0, "duplicateUrlCount": 0,
            "previouslySeenCount": 0, "eligibleCount": written, "selectedCount": written,
            "droppedByLimitCount": 0, "preprocessingFailedCount": 0, "writtenCount": written,
            "writeFailedCount": 0, "reconciliationOk": True, "durationMs": rng.randint(0, 90000),
            "channels": [
                {"channel": channel, "outcome": rng.choice(OUTCOMES), "validatedArticleCount": rng.randint(0, 9),
                 "sourceInvalidCount": 0, "successfulUnits": 1, "partialUnits": 0, "emptyUnits": 0,
                 "failedUnits": 0}
                for channel, _ in rng.sample(CHANNELS, rng.randint(0, 3))
            ],
            "codeVersion": "property",
        }
        path = root / "raw-root" / "raw" / "runs" / f"dt={day}" / f"{run_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
    (root / "raw-root").mkdir(exist_ok=True)
    return fmt_local(as_of)


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    return CompiledProject(tmp_path_factory.mktemp("compiled"))


@pytest.fixture(scope="module")
def reference():
    return load_reference()


def test_random_raw_data_matches_reference(project, reference, tmp_path):
    failures = []
    for seed in range(CASES):
        rng = random.Random(seed)
        root = tmp_path / f"case-{seed}"
        as_of = make_case(rng, root)
        raw_root, seeds = root / "raw-root", root / "seeds"

        expected = reference.build_site(raw_root, seeds, reference.parse_local(as_of), GENERATED_AT, "property")
        connection, failed_tests = project.run(raw_root, seeds, as_of)
        try:
            actual = export_site.build_files_from_connection(connection, GENERATED_AT, "property")
        finally:
            connection.close()

        problems = diff_sites(actual, expected)
        if failed_tests:
            problems.append(f"품질 테스트가 정상 데이터를 거부: {failed_tests}")
        if problems:
            failures.append(f"seed={seed} as_of={as_of}\n" + "\n".join(problems[:5]))
        if len(failures) >= 3:
            break
    assert failures == [], "\n\n".join(failures)


def test_generator_covers_edge_cases(tmp_path):
    """생성기가 실제로 경계 사례를 만들어 내는지 확인한다 (생성기가 망가져 빈 비교만 하는 것을 막기 위함)."""
    seen = {"duplicate_url": False, "boundary": False, "future": False, "occurrence16": False, "blank": False}
    cases_with_articles = 0
    for seed in range(CASES):
        root = tmp_path / f"case-{seed}"
        as_of = datetime.fromisoformat(make_case(random.Random(seed), root))
        urls = []
        for path in root.glob("raw-root/raw/articles/dt=*/*.jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                doc = json.loads(line)
                urls.append(doc["sourceUrl"])
                published = datetime.fromisoformat(doc["publishedAt"])
                seen["boundary"] |= published in (as_of, as_of - timedelta(hours=24), as_of - timedelta(hours=48))
                seen["future"] |= published > as_of
                seen["occurrence16"] |= any(k["occurrenceCount"] == 16 for k in doc["keywords"])
                seen["blank"] |= any(not k["keyword"].strip() for k in doc["keywords"])
        seen["duplicate_url"] |= len(urls) != len(set(urls))
        cases_with_articles += bool(urls)
    assert all(seen.values()), seen
    assert cases_with_articles >= CASES * 0.8, cases_with_articles
