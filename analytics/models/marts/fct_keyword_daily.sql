-- 대표 키워드 × 서울 날짜 30일 추이 (v1 TrendService.buildKeywordHistory, days=30)
-- articleCount = 고유 기사 수, weightedScore = Σ(1 + 0.2 × (1 − 1/max(1, occurrence))) 를 Java 와 같이 half-up 반올림
-- 합산은 기사 순회 순서(load_order)대로 해서 기준 구현과 같은 부동소수점 값을 만든다.
with days as (
    select cast(day as date) as day
    from range(
        {{ history_start() }},
        cast(cast({{ as_of() }} as date) + interval 1 day as timestamp),
        interval 1 day
    ) as t(day)
),

per_day as (
    select
        keyword,
        published_day as day,
        count(*) as article_count,
        {{ ordered_fsum(
            '1.0::double + 0.2::double * (1.0::double - (1.0::double / greatest(1, occurrence)::double))',
            'load_order'
        ) }} as weighted_sum
    from {{ ref('fct_keyword_articles') }}
    where in_history_window
    group by 1, 2
)

select
    k.keyword,
    d.day,
    coalesce(p.article_count, 0) as article_count,
    coalesce({{ java_round3('p.weighted_sum') }}, 0.0::double) as weighted_score,
    d.day = cast({{ as_of() }} as date) as partial
from {{ ref('dim_keyword') }} as k
cross join days as d
left join per_day as p
    on p.keyword = k.keyword and p.day = d.day
