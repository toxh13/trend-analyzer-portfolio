-- 대표 키워드별 검색 키워드 묶음 (v1 KeywordAliasCacheService.resolveSearchKeywords)
-- = canonicalKeywordMap[normalize(대표)] ∪ {입력, 대표}. 상세 화면의 기사·추이·근거는 이 묶음으로 찾는다.
with resolved as (
    select
        k.keyword,
        {{ resolve_keyword('k.keyword', 'm') }} as canonical_keyword
    from {{ ref('dim_keyword') }} as k
    left join {{ ref('int_keyword_alias_map') }} as m
        on m.normalized_alias = {{ normalize_keyword('k.keyword') }}
),

candidates as (
    select keyword, keyword as search_keyword from resolved
    union
    select keyword, canonical_keyword from resolved
    union
    select r.keyword, a.canonical_keyword
    from resolved as r
    inner join {{ ref('stg_keyword_aliases') }} as a
        on a.normalized_canonical = {{ normalize_keyword('r.canonical_keyword') }}
    union
    select r.keyword, a.alias
    from resolved as r
    inner join {{ ref('stg_keyword_aliases') }} as a
        on a.normalized_canonical = {{ normalize_keyword('r.canonical_keyword') }}
)

select
    keyword,
    search_keyword,
    search_keyword <> keyword as is_alias
from candidates
where search_keyword is not null
  and {{ py_strip('search_keyword') }} <> ''
