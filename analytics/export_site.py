"""dbt marts(DuckDB) → contracts/site 형태의 정적 JSON.

계산은 모두 dbt 모델에서 끝내고, 이 스크립트는 행을 Spring DTO 필드명의 JSON 으로 옮기기만 합니다.
예외는 신선도 시간 반올림 하나입니다(Python round 와 같은 결과를 내기 위해 여기서 계산).

    python analytics/export_site.py --duckdb target/trend.duckdb --out site-data \
        --generated-at 2026-10-24T03:00:00Z --code-version local

출력 규칙: UTF-8, ensure_ascii=False, 들여쓰기 없음, 행 순서는 SQL ORDER BY 로 결정적.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ALL_SCOPE = "__ALL__"
FRESH_OK_HOURS = 6
FRESH_STALE_HOURS = 24
RUNS_LIMIT = 50


def utc_now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Marts:
    def __init__(self, connection: duckdb.DuckDBPyConnection):
        self.connection = connection

    def rows(self, sql: str, params: list | None = None) -> list[dict]:
        cursor = self.connection.execute(sql, params or [])
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


# ---------------------------------------------------------------- 목록 · 통계 · 카테고리


def trend_list(marts: Marts, list_type: str, scope: str) -> list[dict]:
    """v1 TrendingResponseDto 목록."""
    return [
        {
            "id": f"keyword-{row['keyword']}",
            "keyword": row["keyword"],
            "category": row["category"],
            "score": row["score"],
            "mention_count": row["mention_count"],
            "rank": row["list_rank"],
            "changeType": row["change_type"],
            "changeValue": row["change_value"],
        }
        for row in marts.rows(
            """
            select * from fct_trend_lists
            where list_type = ? and scope = ?
            order by list_rank
            """,
            [list_type, scope],
        )
    ]


def stats_document(row: dict) -> dict:
    """v1 TrendStatsResponseDto."""

    def keyword(prefix: str):
        if row[f"{prefix}_keyword"] is None:
            return None
        return {
            "keyword": row[f"{prefix}_keyword"],
            "mentionCount": row[f"{prefix}_mention_count"],
            "changeAmount": row[f"{prefix}_change_amount"],
        }

    return {
        "analyzedArticles": row["analyzed_articles"],
        "trackedKeywords": row["tracked_keywords"],
        "risingKeyword": keyword("rising"),
        "fallingKeyword": keyword("falling"),
        "windowHours": row["window_hours"],
    }


def build_lists(marts: Marts, files: dict[str, object]) -> list[dict]:
    categories = marts.rows("select * from dim_category order by category")
    files["categories.json"] = [
        {"id": c["category"], "label": c["category"], "trendCount": c["trend_count"], "slug": c["category_slug"]}
        for c in categories
    ]
    files["trends/all.json"] = trend_list(marts, "top", ALL_SCOPE)
    files["trends/popular.json"] = trend_list(marts, "popular", ALL_SCOPE)
    files["trends/surging/all.json"] = trend_list(marts, "surging", ALL_SCOPE)

    stats = {row["scope"]: row for row in marts.rows("select * from fct_dashboard_stats")}
    files["stats/all.json"] = stats_document(stats[ALL_SCOPE])
    for category in categories:
        name, slug = category["category"], category["category_slug"]
        files[f"trends/category/{slug}.json"] = trend_list(marts, "top", name)
        files[f"trends/surging/{slug}.json"] = trend_list(marts, "surging", name)
        files[f"stats/{slug}.json"] = stats_document(stats[name])
    return categories


# ---------------------------------------------------------------- 키워드 상세 · 색인


def offset_text(published_at: datetime) -> str:
    """v1 ArticleEvidenceDto.publishedAt (서울 OffsetDateTime 직렬화)."""
    return published_at.strftime("%Y-%m-%dT%H:%M:%S") + "+09:00"


def build_keywords(marts: Marts, files: dict[str, object], as_of_day: str, generated_at: str) -> None:
    keywords = marts.rows("select * from dim_keyword order by detail_rank")
    search = {}
    for row in marts.rows("select keyword, search_keyword, is_alias from dim_keyword_search order by keyword, search_keyword"):
        entry = search.setdefault(row["keyword"], {"search": [], "aliases": []})
        entry["search"].append(row["search_keyword"])
        if row["is_alias"]:
            entry["aliases"].append(row["search_keyword"])

    daily: dict[str, list[dict]] = {}
    for row in marts.rows("select * from fct_keyword_daily order by keyword, day"):
        daily.setdefault(row["keyword"], []).append({
            "day": row["day"].isoformat(),
            "articleCount": row["article_count"],
            "weightedScore": row["weighted_score"],
        })

    articles: dict[str, list[dict]] = {}
    evidence: dict[str, dict[str, list[dict]]] = {}
    for row in marts.rows(
        """
        select * from fct_keyword_articles
        where newest_rank <= 100 or (in_history_window and day_rank <= 5)
        order by keyword, newest_rank
        """
    ):
        keyword = row["keyword"]
        if row["newest_rank"] <= 100:
            articles.setdefault(keyword, []).append({
                "id": row["article_id"],
                "title": row["title"],
                "source": row["source"],
                "date": row["published_at"].strftime("%Y-%m-%dT%H:%M:%S"),
                "url": row["source_url"],
            })
        if row["in_history_window"] and row["day_rank"] <= 5:
            evidence.setdefault(keyword, {}).setdefault(row["published_day"].isoformat(), []).append({
                "id": row["article_id"],
                "title": row["title"],
                "summary": row["summary"],
                "source": row["source"],
                "publishedAt": offset_text(row["published_at"]),
                "sourceUrl": row["source_url"],
            })

    for row in keywords:
        keyword = row["keyword"]
        entry = search.get(keyword, {"search": [keyword], "aliases": []})
        files[f"keywords/{row['keyword_slug']}.json"] = {
            "schemaVersion": 1,
            "keyword": keyword,
            "slug": row["keyword_slug"],
            "aliases": entry["aliases"],
            "searchKeywords": entry["search"],
            "timezone": "Asia/Seoul",
            "today": as_of_day,
            "generatedAt": generated_at,
            "daily": daily.get(keyword, []),
            "articles": articles.get(keyword, []),
            "evidenceByDay": dict(sorted(evidence.get(keyword, {}).items())),
        }

    index_rows = sorted(keywords, key=lambda row: row["index_rank"])
    files["keywords/index.json"] = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "keywords": [
            {
                "keyword": row["keyword"],
                "slug": row["keyword_slug"],
                "aliases": search.get(row["keyword"], {"aliases": []})["aliases"],
                "mentionCount": row["mention_count"],
                "articleCount30d": row["article_count_30d"],
            }
            for row in index_rows
        ],
        "aliasToCanonical": {
            row["normalized_keyword"]: row["keyword"]
            for row in marts.rows("select * from dim_keyword_lookup order by normalized_keyword")
        },
    }


# ---------------------------------------------------------------- 실행 이력 · 메타


def build_runs(marts: Marts, files: dict[str, object], generated_at: str) -> None:
    runs = marts.rows(
        f"""
        select * from fct_ingest_runs
        order by started_at_text desc, file_path
        limit {RUNS_LIMIT}
        """
    )
    files["runs/recent.json"] = {
        "generatedAt": generated_at,
        "runs": [
            {
                "runId": r["run_id"],
                "startedAt": r["started_at_text"],
                "completedAt": r["completed_at_text"],
                "outcome": r["outcome"],
                "trigger": r["trigger"],
                "selectedCount": r["selected_count"],
                "writtenCount": r["written_count"],
                "previouslySeenCount": r["previously_seen_count"],
                "validationRejectedCount": r["validation_rejected_count"],
                "reconciliationOk": r["reconciliation_ok"],
                "durationMs": r["duration_ms"],
                "channels": [dict(channel) for channel in r["channels"]],
            }
            for r in runs
        ],
    }


def freshness(seconds: float | None) -> tuple[str, float | None]:
    """ok: 6시간 이내, stale: 6~24시간, down: 24시간 초과 또는 성공 실행 없음."""
    if seconds is None:
        return "down", None
    hours = round(seconds / 3600, 2)
    state = "ok" if hours <= FRESH_OK_HOURS else "stale" if hours <= FRESH_STALE_HOURS else "down"
    return state, hours


def build_meta(marts: Marts, files: dict[str, object], generated_at: str, code_version: str) -> dict:
    status = marts.rows("select * from fct_pipeline_status")[0]
    state, hours = freshness(status["freshness_seconds"])
    last_run = None
    if status["last_run_id"] is not None:
        last_run = {
            "runId": status["last_run_id"],
            "completedAt": status["last_run_completed_at"],
            "outcome": status["last_run_outcome"],
        }
    meta = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "asOf": status["as_of_text"],
        "timezone": "Asia/Seoul",
        "lastRun": last_run,
        "lastSuccessfulRunAt": status["last_successful_run_at"],
        "freshness": state,
        "freshnessHours": hours,
        "counts": {
            "articles30d": status["articles_30d"],
            "keywords30d": status["keywords_30d"],
            "runs7d": status["runs_7d"],
        },
        "codeVersion": code_version,
    }
    files["meta.json"] = meta
    return meta


# ---------------------------------------------------------------- 진입점


def build_files_from_connection(
    connection: duckdb.DuckDBPyConnection, generated_at: str, code_version: str
) -> dict[str, object]:
    marts = Marts(connection)
    files: dict[str, object] = {}
    build_lists(marts, files)
    meta = build_meta(marts, files, generated_at, code_version)
    build_keywords(marts, files, meta["asOf"][:10], generated_at)
    build_runs(marts, files, generated_at)
    return files


def build_files(duckdb_path: Path, generated_at: str, code_version: str) -> dict[str, object]:
    # dbt-duckdb 가 같은 프로세스에서 연 연결과 설정이 같아야 하므로 read_only 를 쓰지 않는다
    connection = duckdb.connect(str(duckdb_path))
    try:
        return build_files_from_connection(connection, generated_at, code_version)
    finally:
        connection.close()


def check_out_dir(out: Path) -> None:
    """엉뚱한 디렉터리를 지우지 않도록, 비어 있지 않은 out 은 이전 산출물(meta.json 이 있음)일 때만 허용한다."""
    if out.exists() and (not out.is_dir() or (any(out.iterdir()) and not (out / "meta.json").is_file())):
        raise RuntimeError(f"{out} 는 비어 있지 않고 정적 JSON 산출물도 아닙니다. 다른 --out 을 지정하세요.")


def write_files(files: dict[str, object], out: Path) -> None:
    """out 을 비우고 다시 쓴다. 이전 실행의 키워드 파일이 남아 계약 밖 파일이 되는 것을 막는다."""
    check_out_dir(out)
    if out.exists():
        shutil.rmtree(out)
    for name in sorted(files):
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(files[name], ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--duckdb", type=Path, required=True, help="dbt build 가 만든 DuckDB 파일")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--generated-at", default=None, help="UTC ...Z, 기본 현재 시각")
    parser.add_argument("--code-version", default="local")
    args = parser.parse_args()

    files = build_files(args.duckdb, args.generated_at or utc_now_text(), args.code_version)
    try:
        write_files(files, args.out)
    except RuntimeError as error:
        print(error)
        return 1
    print(f"wrote {len(files)} files to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
