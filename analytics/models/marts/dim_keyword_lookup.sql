-- keywords/index.json 의 aliasToCanonical: normalize(대표 키워드 또는 alias) → 대표 키워드
-- 정규화 결과가 겹치면 상세 선정 순서(detail_rank)상 나중 키워드가 이긴다 (기준 구현의 dict 덮어쓰기와 같음)
select
    {{ normalize_keyword('s.search_keyword') }} as normalized_keyword,
    arg_max(s.keyword, k.detail_rank) as keyword
from {{ ref('dim_keyword_search') }} as s
inner join {{ ref('dim_keyword') }} as k
    on k.keyword = s.keyword
group by 1
