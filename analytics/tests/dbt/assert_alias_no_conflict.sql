-- 스키마: 같은 정규화 alias 가 서로 다른 대표 키워드를 가리키면 안 된다
-- (AI, A.I. 처럼 정규화가 같아도 대표 키워드가 같으면 허용)
select normalized_alias, count(distinct canonical_keyword) as canonical_count
from {{ ref('stg_keyword_aliases') }}
group by 1
having count(distinct canonical_keyword) > 1
