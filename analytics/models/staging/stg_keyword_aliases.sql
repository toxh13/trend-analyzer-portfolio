-- 승인된 alias (운영: analytics/seeds, 테스트: fixtures/seeds). v1 keyword_aliases 의 active 행에 해당
select
    alias,
    canonical_keyword,
    approved_at,
    note,
    {{ normalize_keyword('alias') }} as normalized_alias,
    {{ normalize_keyword('canonical_keyword') }} as normalized_canonical
from read_csv(
    '{{ seed_file("keyword_aliases.csv") }}',
    header = true,
    columns = {'alias': 'VARCHAR', 'canonical_keyword': 'VARCHAR', 'approved_at': 'VARCHAR', 'note': 'VARCHAR'}
)
where alias is not null and canonical_keyword is not null
