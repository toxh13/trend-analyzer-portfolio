{{ config(severity='warn') }}
-- 신선도(경고): 마지막 성공 실행이 as_of 기준 6시간 이내여야 한다. 성공 실행이 없어도 경고
select last_successful_run_at, freshness_seconds
from {{ ref('fct_pipeline_status') }}
where freshness_seconds is null or freshness_seconds > 6 * 3600
