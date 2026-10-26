-- 정적 JSON 목록 파일의 행 (v1 TrendService 목록 API)
-- top     : hotness 내림차순 Top20 (getTop20Trend / getTop20CategoryTrend)
-- popular : mention 내림차순, hotness 내림차순, 최대 50 (getTopMentionedTrends, 전체만)
-- surging : velocity 내림차순, mention 내림차순, 최대 50, velocity > 0 (getTopSurgingTrends)
-- 동점은 키워드 오름차순으로 결정적으로 정한다 (v1 은 HashMap 순서).
with listed as (
    select
        'top' as list_type,
        scope,
        keyword,
        category,
        mention_count,
        velocity_score,
        hotness_score,
        row_number() over (
            partition by scope
            order by hotness_score desc, mention_count desc, keyword
        ) as list_rank
    from {{ ref('fct_trend_merged') }}
    where mention_count > 0

    union all

    select
        'popular',
        scope,
        keyword,
        category,
        mention_count,
        velocity_score,
        hotness_score,
        row_number() over (
            partition by scope
            order by mention_count desc, hotness_score desc, keyword
        )
    from {{ ref('fct_trend_merged') }}
    where mention_count > 0 and scope = '__ALL__'

    union all

    select
        'surging',
        scope,
        keyword,
        category,
        mention_count,
        velocity_score,
        hotness_score,
        row_number() over (
            partition by scope
            order by velocity_score desc, mention_count desc, keyword
        )
    from {{ ref('fct_trend_merged') }}
    where mention_count > 0 and velocity_score > 0
)

select
    list_type,
    scope,
    list_rank,
    keyword,
    category,
    mention_count,
    velocity_score,
    hotness_score,
    -- score 는 소수 넷째 자리 반올림 (v1 Java float 오차 제거)
    round(hotness_score, 4) as score,
    case
        when velocity_score > 0 then 'up'
        when velocity_score < 0 then 'down'
        else 'same'
    end as change_type,
    abs(velocity_score) as change_value
from listed
where list_rank <= case when list_type = 'top' then 20 else 50 end
