-- v1 CrawlingService.saveCrawledData 의 키워드 저장 규칙 (v1 article_keywords 테이블에 해당)
-- 1. normalizeForCompare(trim → 소문자) 가 같은 키워드는 합치고 첫 표기를 유지, 횟수는 max(1, n) 합산
-- 2. trim 후 빈 값과 차단 키워드는 저장하지 않음
-- 3. weight = max(1, 합산 횟수)
with grouped as (
    select
        source_url,
        {{ normalize_for_compare('keyword') }} as compare_key,
        arg_min(keyword, item_order) as first_keyword,
        sum(greatest(1, occurrence_count)) as total_count
    from {{ ref('stg_article_keywords') }}
    where keyword is not null
    group by 1, 2
)

select
    g.source_url,
    {{ py_strip('g.first_keyword') }} as keyword,
    greatest(1, g.total_count) as weight
from grouped as g
where {{ py_strip('g.first_keyword') }} <> ''
  and g.compare_key not in (select blocked_key from {{ ref('stg_blocked_keywords') }})
