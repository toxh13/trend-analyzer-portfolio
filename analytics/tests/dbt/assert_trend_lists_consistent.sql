-- 계산식: 목록 행의 score·changeValue 가 병합 값과 맞고, 순위가 1부터 빈틈없이 이어져야 한다
with ranks as (
    select list_type, scope, count(*) as row_count, max(list_rank) as max_rank
    from {{ ref('fct_trend_lists') }}
    group by 1, 2
)

select list_type, scope, 'rank gap' as problem
from ranks
where row_count <> max_rank

union all

select list_type, scope, 'value mismatch'
from {{ ref('fct_trend_lists') }}
where abs(score - hotness_score) > 1e-4
   or change_value <> abs(velocity_score)
   or mention_count <= 0
   or (list_type = 'surging' and velocity_score <= 0)
