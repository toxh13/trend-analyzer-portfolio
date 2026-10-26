-- 정규화 alias → 대표 키워드 (v1 KeywordAliasCacheService.aliasMap).
-- 같은 정규화 alias 가 서로 다른 대표 키워드를 가리키면 assert_alias_no_conflict 테스트가 build 를 멈춘다.
select
    normalized_alias,
    min(canonical_keyword) as canonical_keyword
from {{ ref('stg_keyword_aliases') }}
group by normalized_alias
