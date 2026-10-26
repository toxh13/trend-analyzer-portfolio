-- 저장된 원본 키워드에 대표 키워드와 차단 여부를 붙인다
-- (v1 KeywordAliasCacheService.resolveKeyword + TrendAnalysticService.resolveMetricKey)
select
    a.article_id,
    a.source_url,
    a.category,
    a.published_at,
    a.published_day,
    a.load_order,
    k.keyword as raw_keyword,
    k.weight,
    {{ resolve_keyword('k.keyword', 'm') }} as canonical_keyword,
    {{ py_strip(resolve_keyword('k.keyword', 'm')) }} as metric_keyword,
    (
        {{ normalize_for_compare('k.keyword') }} in (select blocked_key from {{ ref('stg_blocked_keywords') }})
        or {{ normalize_for_compare(resolve_keyword('k.keyword', 'm')) }} in (select blocked_key from {{ ref('stg_blocked_keywords') }})
    ) as is_blocked
from {{ ref('int_article_keywords_stored') }} as k
inner join {{ ref('stg_articles') }} as a
    on a.source_url = k.source_url
left join {{ ref('int_keyword_alias_map') }} as m
    on m.normalized_alias = {{ normalize_keyword('k.keyword') }}
