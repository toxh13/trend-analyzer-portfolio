-- 스키마: 앞뒤 공백을 지운 카테고리가 빈 값인 기사가 없어야 한다 (빈 카테고리는 v1 스냅샷에서 조용히 빠진다)
select source_url, run_id
from {{ ref('stg_articles') }}
where category = ''
