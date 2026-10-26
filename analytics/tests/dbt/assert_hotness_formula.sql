-- 계산식: hotness = mention × 0.4 + velocity × 0.6 (오차 1e-6), mention ≥ 0, previous ≥ 0
select keyword, category, mention_count, velocity_score, hotness_score
from {{ ref('fct_trend_snapshot') }}
where abs(hotness_score - (mention_count * 0.4 + velocity_score * 0.6)) > 1e-6
   or mention_count < 0
   or previous_count < 0
   or velocity_score <> mention_count - previous_count
   or (mention_count = 0 and previous_count = 0)
