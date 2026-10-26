-- v1 TrendAnalysticService.analyzeAndReplaceSnapshot
-- grain: 대표 키워드 × 카테고리. current = [as_of-24h, as_of), previous = [as_of-48h, as_of-24h)
-- 같은 기사에 같은 대표 키워드가 여러 번(alias 포함) 있어도 고유 기사 1건으로 센다.
with evidence as (
    select distinct
        source_url,
        metric_keyword as keyword,
        category,
        case
            when published_at < {{ as_of() }} - interval 24 hours then 'PREVIOUS'
            else 'CURRENT'
        end as window_type
    from {{ ref('int_article_keywords_canonical') }}
    where published_at >= {{ as_of() }} - interval 48 hours
      and published_at < {{ as_of() }}
      and metric_keyword <> ''
      and category <> ''
      and not is_blocked
),

counts as (
    select
        keyword,
        category,
        count(*) filter (where window_type = 'CURRENT') as current_count,
        count(*) filter (where window_type = 'PREVIOUS') as previous_count
    from evidence
    group by 1, 2
)

select
    keyword,
    category,
    current_count as mention_count,
    previous_count,
    current_count - previous_count as velocity_score,
    current_count::double * 0.4::double + (current_count - previous_count)::double * 0.6::double as hotness_score
from counts
