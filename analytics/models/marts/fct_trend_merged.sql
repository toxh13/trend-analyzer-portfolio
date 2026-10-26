-- 스냅샷을 조회 범위(scope)별로 대표 키워드끼리 합친 결과 (v1 TrendService.mergeAliases)
-- scope = '__ALL__' 은 전체, 나머지는 카테고리 이름.
-- category 는 v2 규칙: mention 이 가장 큰 카테고리, 같으면 이름 오름차순 (v1 은 DB 순서상 처음 행)
with snapshot as (
    select
        s.*,
        {{ resolve_keyword('s.keyword', 'm') }} as display_keyword
    from {{ ref('fct_trend_snapshot') }} as s
    left join {{ ref('int_keyword_alias_map') }} as m
        on m.normalized_alias = {{ normalize_keyword('s.keyword') }}
),

scoped as (
    select '__ALL__' as scope, * from snapshot
    union all
    select category as scope, * from snapshot
),

by_category as (
    select scope, display_keyword, category, sum(mention_count) as category_mention
    from scoped
    group by 1, 2, 3
),

chosen_category as (
    select scope, display_keyword, category
    from by_category
    qualify row_number() over (
        partition by scope, display_keyword
        order by category_mention desc, category
    ) = 1
)

select
    s.scope,
    s.display_keyword as keyword,
    c.category,
    sum(s.mention_count) as mention_count,
    sum(s.velocity_score) as velocity_score,
    {{ ordered_fsum('s.hotness_score', 's.category, s.keyword') }} as hotness_score
from scoped as s
inner join chosen_category as c
    on c.scope = s.scope and c.display_keyword = s.display_keyword
group by s.scope, s.display_keyword, c.category
