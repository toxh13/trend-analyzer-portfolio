-- v1 CategoryService.getAvailableCategories: 기사에 나온 카테고리 이름 오름차순 + 스냅샷 행 수
select
    a.category,
    {{ slug('a.category') }} as category_slug,
    coalesce(s.trend_count, 0) as trend_count
from (
    select distinct category
    from {{ ref('stg_articles') }}
    where category <> ''
) as a
left join (
    select category, count(*) as trend_count
    from {{ ref('fct_trend_snapshot') }}
    group by 1
) as s
    on s.category = a.category
