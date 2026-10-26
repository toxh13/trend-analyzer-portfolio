-- 대표 키워드별 관련 기사 (as_of 이전 발행분)
-- v1 getArticlesContainingKeyword(최신 100건) + findEvidenceByKeywordsWithinWindow(날짜별 최신 5건)
-- occurrence = 검색 키워드 묶음에 속한 원본 키워드 weight 합 (v1 findDailyKeywordEvidence 의 SUM(k.weight))
with matching as (
    select
        s.keyword,
        a.article_id,
        a.source_url,
        a.title,
        a.summary,
        a.source,
        a.published_at,
        a.published_day,
        a.load_order,
        sum(k.weight) as occurrence
    from {{ ref('dim_keyword_search') }} as s
    inner join {{ ref('int_article_keywords_stored') }} as k
        on k.keyword = s.search_keyword
    inner join {{ ref('stg_articles') }} as a
        on a.source_url = k.source_url
    where a.published_at < {{ as_of() }}
    group by all
)

select
    *,
    row_number() over (
        partition by keyword order by published_at desc, article_id desc
    ) as newest_rank,
    row_number() over (
        partition by keyword, published_day order by published_at desc, article_id desc
    ) as day_rank,
    published_at >= {{ history_start() }} as in_history_window
from matching
