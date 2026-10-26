-- 계산식: 상세 키워드마다 30일이 빠짐없이 있고, 오늘만 partial 이다
select keyword, count(*) as day_count, count(*) filter (where partial) as partial_count
from {{ ref('fct_keyword_daily') }}
group by 1
having count(*) <> 30 or count(*) filter (where partial) <> 1
