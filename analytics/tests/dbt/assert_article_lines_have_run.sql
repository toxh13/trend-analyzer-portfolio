{{ config(severity='warn') }}
-- 대사: 기사 줄의 runId 에 해당하는 run JSON 이 있어야 한다 (수집기가 run JSON 쓰기 전에 죽은 경우 경고)
select distinct l.run_id
from {{ ref('stg_article_lines') }} as l
left join {{ ref('stg_runs') }} as r
    on r.run_id = l.run_id
where r.run_id is null
