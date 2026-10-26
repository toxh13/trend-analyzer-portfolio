-- 배포본 메타데이터 1행: 마지막 실행, 마지막 성공 실행, 신선도 계산 입력, 건수
-- 마지막 실행은 completedAt 문자열 기준 (같으면 파일 경로가 뒤인 것). SUCCESS·PARTIAL_FAILURE 를 성공으로 본다.
with last_run as (
    select run_id, completed_at_text, outcome
    from {{ ref('fct_ingest_runs') }}
    order by completed_at_text desc, file_path desc
    limit 1
),

last_success as (
    select completed_at_text, completed_at
    from {{ ref('fct_ingest_runs') }}
    where outcome in ('SUCCESS', 'PARTIAL_FAILURE')
    order by completed_at_text desc, file_path desc
    limit 1
)

select
    '{{ var("as_of") }}' as as_of_text,
    {{ as_of_utc() }} as as_of_utc,
    (select run_id from last_run) as last_run_id,
    (select completed_at_text from last_run) as last_run_completed_at,
    (select outcome from last_run) as last_run_outcome,
    (select completed_at_text from last_success) as last_successful_run_at,
    -- 초 단위 경과 시간 (마이크로초 정수 차이 / 1e6). 시간 단위 반올림은 export 에서 한다
    (epoch_us({{ as_of_utc() }}) - epoch_us((select completed_at from last_success)))::double
        / 1000000.0::double as freshness_seconds,
    (
        select count(*) from {{ ref('stg_articles') }}
        where published_at >= {{ history_start() }} and published_at < {{ as_of() }}
    ) as articles_30d,
    (
        select count(distinct metric_keyword) from {{ ref('int_article_keywords_canonical') }}
        where published_at >= {{ history_start() }} and published_at < {{ as_of() }}
          and metric_keyword <> '' and not is_blocked
    ) as keywords_30d,
    (
        select count(*) from {{ ref('fct_ingest_runs') }}
        where started_at >= {{ as_of_utc() }} - interval 7 days
    ) as runs_7d
