-- 기사 1건 = 1행. sourceUrl 기준으로 가장 먼저 수집된 행만 남긴다
-- (v1 existsBySourceUrl 스킵 + unique 제약 → 최초 insert 승리).
-- load_order 는 기준 구현의 기사 순회 순서(crawledAt, runId, 줄 번호)이며 부동소수점 합산 순서에 쓴다.
with ranked as (
    select
        *,
        row_number() over (
            partition by source_url
            order by crawled_at, run_id, line_no
        ) as url_rank
    from {{ ref('stg_article_lines') }}
)

select
    'article-' || {{ slug('source_url') }} as article_id,
    source_url,
    run_id,
    channel,
    source,
    {{ py_strip('raw_category') }} as category,
    title,
    summary,
    published_at,
    cast(published_at as date) as published_day,
    crawled_at,
    keywords_json,
    row_number() over (order by crawled_at, run_id, line_no) as load_order
from ranked
where url_rank = 1
