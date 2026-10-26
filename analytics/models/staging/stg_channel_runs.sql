-- 실행 1회의 채널별 결과 (파일 안 순서 유지)
with items as (
    select
        run_id,
        unnest(cast(channels_json as json[])) as item,
        generate_subscripts(cast(channels_json as json[]), 1) as channel_order
    from {{ ref('stg_runs') }}
)

select
    run_id,
    channel_order,
    item ->> 'channel' as channel,
    item ->> 'outcome' as outcome,
    cast(item ->> 'validatedArticleCount' as bigint) as validated_article_count,
    cast(item ->> 'sourceInvalidCount' as bigint) as source_invalid_count,
    cast(item ->> 'successfulUnits' as bigint) as successful_units,
    cast(item ->> 'partialUnits' as bigint) as partial_units,
    cast(item ->> 'emptyUnits' as bigint) as empty_units,
    cast(item ->> 'failedUnits' as bigint) as failed_units
from items
