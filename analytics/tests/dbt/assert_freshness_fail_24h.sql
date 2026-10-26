{{ config(severity=('error' if var('strict_freshness') else 'warn')) }}
-- 신선도(실패): 마지막 성공 실행이 24시간을 넘으면 실패.
-- 기본은 경고로 낮춘다. 수집이 멈춰도 publish 가 meta.freshness=down 을 배포해야 운영 현황·배지가 정지를 알릴 수 있기 때문이다.
-- build_site.py --strict-freshness 로 실행하면 실패로 처리한다.
select last_successful_run_at, freshness_seconds
from {{ ref('fct_pipeline_status') }}
where freshness_seconds is null or freshness_seconds > 24 * 3600
