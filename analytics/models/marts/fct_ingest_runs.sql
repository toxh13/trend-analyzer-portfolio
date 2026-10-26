-- as_of 시점까지 시작한 수집 실행 (운영 현황 화면, 신선도)
select
    r.*,
    coalesce(c.channels, []) as channels
from {{ ref('stg_runs') }} as r
left join (
    select
        run_id,
        list(
            {'channel': channel, 'outcome': outcome, 'validatedArticleCount': validated_article_count}
            order by channel_order
        ) as channels
    from {{ ref('stg_channel_runs') }}
    group by 1
) as c
    on c.run_id = r.run_id
where r.started_at <= {{ as_of_utc() }}
