-- 차단 키워드. 비교는 v1 normalizeForCompare(trim → 소문자) 기준
select distinct
    {{ normalize_for_compare('keyword') }} as blocked_key
from read_csv(
    '{{ seed_file("blocked_keywords.csv") }}',
    header = true,
    columns = {'keyword': 'VARCHAR', 'reason': 'VARCHAR'}
)
where keyword is not null
