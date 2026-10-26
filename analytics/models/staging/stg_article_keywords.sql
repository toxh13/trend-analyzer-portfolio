-- 수집기가 추출한 원본 키워드 항목 (기사 안 순서 유지). v1 저장 규칙은 int_article_keywords_stored 에서 적용한다.
with items as (
    select
        source_url,
        unnest(cast(keywords_json as json[])) as item,
        generate_subscripts(cast(keywords_json as json[]), 1) as item_order
    from {{ ref('stg_articles') }}
)

select
    source_url,
    item_order,
    json_extract_string(item, '$.keyword') as keyword,
    coalesce(try_cast(json_extract_string(item, '$.occurrenceCount') as bigint), 0) as occurrence_count
from items
