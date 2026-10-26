-- v1 TrendService.getDashboardStatsWithin24Hours (전체 + 카테고리별)
-- analyzedArticles: 최근 24시간 발행 기사 수, trackedKeywords: 그 기사들의 고유 원본 키워드 수 (alias 적용 전)
-- rising/falling: 같은 범위 스냅샷을 대표 키워드로 합친 뒤 |velocity| 내림차순, mention 내림차순
with scopes as (
    select '__ALL__' as scope, cast(null as varchar) as category
    union all
    select category, category from {{ ref('dim_category') }}
),

window_articles as (
    select source_url, category
    from {{ ref('stg_articles') }}
    where published_at >= {{ as_of() }} - interval 24 hours
      and published_at < {{ as_of() }}
),

article_counts as (
    select
        sc.scope,
        count(distinct w.source_url) as analyzed_articles
    from scopes as sc
    left join window_articles as w
        on sc.category is null or w.category = sc.category
    group by 1
),

keyword_counts as (
    select
        sc.scope,
        count(distinct k.keyword) as tracked_keywords
    from scopes as sc
    left join window_articles as w
        on sc.category is null or w.category = sc.category
    left join {{ ref('int_article_keywords_stored') }} as k
        on k.source_url = w.source_url
    group by 1
),

rising as (
    select scope, keyword, mention_count, velocity_score
    from {{ ref('fct_trend_merged') }}
    where velocity_score > 0
    qualify row_number() over (
        partition by scope order by abs(velocity_score) desc, mention_count desc, keyword
    ) = 1
),

falling as (
    select scope, keyword, mention_count, velocity_score
    from {{ ref('fct_trend_merged') }}
    where velocity_score < 0
    qualify row_number() over (
        partition by scope order by abs(velocity_score) desc, mention_count desc, keyword
    ) = 1
)

select
    sc.scope,
    sc.category,
    a.analyzed_articles,
    k.tracked_keywords,
    r.keyword as rising_keyword,
    r.mention_count as rising_mention_count,
    r.velocity_score as rising_change_amount,
    f.keyword as falling_keyword,
    f.mention_count as falling_mention_count,
    f.velocity_score as falling_change_amount,
    24 as window_hours
from scopes as sc
inner join article_counts as a on a.scope = sc.scope
inner join keyword_counts as k on k.scope = sc.scope
left join rising as r on r.scope = sc.scope
left join falling as f on f.scope = sc.scope
