"""파싱된 항목의 품질 검사. 기록용 숫자만 만든다(수집을 막지 않는다).

항목을 임시 JSONL로 쓰고 DuckDB가 읽어 SQL로 셈한다.
"""

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

import duckdb

from trend_pipeline.article_key import ArticleKey
from trend_pipeline.parse import FeedItem


@dataclass(frozen=True)
class QualityReport:
    item_count: int  # 검사한 항목 수
    missing_required: int  # 필수 필드(제목·링크·발행 시각·기사 번호)가 NULL이거나 빈 문자열인 항목 수
    duplicate_keys: int  # 같은 (source, source_article_id)가 여러 번 나와 남는 항목 수


# 필수 필드. 이 중 하나라도 NULL이거나 공백뿐이면 누락으로 센다
_REQUIRED = ("title", "link", "published_at", "source_article_id")
# 공백뿐인 문자열(빈 문자열 포함). DuckDB trim()은 탭·줄바꿈을 못 떼서 정규식을 쓴다.
# \s는 ASCII 공백만 잡으므로 전각 공백(U+3000)과 NBSP(U+00A0)를 따로 넣는다
_BLANK = r"^[\s\x{3000}\x{a0}]*$"
_MISSING = "\n           OR ".join(f"{c} IS NULL OR regexp_matches({c}, '{_BLANK}')" for c in _REQUIRED)

# 읽는 열의 형식을 직접 적는다. 형식을 추정하게 두면 값에 따라 열 형식이 바뀐다
_SQL = f"""
SELECT
    COUNT(*) AS item_count,
    COUNT(*) FILTER (
        WHERE {_MISSING}
    ) AS missing_required,
    COUNT(*) - COUNT(DISTINCT (source, source_article_id)) AS duplicate_keys
FROM read_json(
    ?,
    format = 'newline_delimited',
    columns = {{
        source: 'VARCHAR',
        source_article_id: 'VARCHAR',
        title: 'VARCHAR',
        link: 'VARCHAR',
        published_at: 'VARCHAR'
    }}
)
"""


def _row(key: ArticleKey, item: FeedItem) -> dict[str, str | None]:
    published_at = item.published_at
    return {
        "source": key.source,
        "source_article_id": key.source_article_id,
        "title": item.title,
        "link": item.link,
        # 시각이 비어 있는 항목도 센다(예외로 죽지 않고 missing_required에 잡힌다)
        "published_at": published_at.isoformat() if published_at is not None else None,
    }


def check_items(items: list[tuple[ArticleKey, FeedItem]]) -> QualityReport:
    """항목 목록의 개수, 필수 필드 누락 수, 중복 키 수를 센다."""
    if not items:
        return QualityReport(0, 0, 0)

    # 윈도우는 열려 있는 NamedTemporaryFile을 다시 열 수 없어서 임시 디렉터리를 쓴다
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "items.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for key, item in items:
                # 제목 안의 줄바꿈은 JSON이 이스케이프하므로 한 항목이 한 줄로 남는다
                f.write(json.dumps(_row(key, item), ensure_ascii=False) + "\n")

        con = duckdb.connect()  # 인메모리
        try:
            row = con.execute(_SQL, [str(path)]).fetchone()
        finally:
            con.close()  # 닫아야 윈도우에서 임시 디렉터리를 지울 수 있다

    assert row is not None  # 집계 쿼리는 항상 한 행을 돌려준다
    return QualityReport(item_count=row[0], missing_required=row[1], duplicate_keys=row[2])
