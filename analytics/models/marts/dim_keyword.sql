-- 상세 파일(keywords/<slug>.json)을 만드는 대표 키워드
-- 선정: 최근 30일([오늘-29일 00:00, as_of)) 기사 2건 이상이거나 목록(top·popular·surging)에 나온 키워드, 최대 3,000개
-- 정렬(detail_rank): 30일 기사 수 내림차순, 키워드 오름차순. 색인 정렬(index_rank)은 현재 mention 을 먼저 본다.
with counts_30d as (
    select
        metric_keyword as keyword,
        count(distinct source_url) as article_count_30d
    from {{ ref('int_article_keywords_canonical') }}
    where published_at >= {{ history_start() }}
      and published_at < {{ as_of() }}
      and metric_keyword <> ''
      and not is_blocked
    group by 1
),

listed as (
    select distinct keyword from {{ ref('fct_trend_lists') }}
),

chosen as (
    select
        c.keyword,
        c.article_count_30d,
        row_number() over (order by c.article_count_30d desc, c.keyword) as detail_rank
    from counts_30d as c
    left join listed as l
        on l.keyword = c.keyword
    where c.article_count_30d >= 2 or l.keyword is not null
    qualify detail_rank <= 3000
),

mentions as (
    select keyword, mention_count
    from {{ ref('fct_trend_merged') }}
    where scope = '__ALL__'
)

select
    c.keyword,
    {{ slug('c.keyword') }} as keyword_slug,
    c.detail_rank,
    c.article_count_30d,
    coalesce(m.mention_count, 0) as mention_count,
    row_number() over (
        order by coalesce(m.mention_count, 0) desc, c.article_count_30d desc, c.keyword
    ) as index_rank
from chosen as c
left join mentions as m
    on m.keyword = c.keyword
