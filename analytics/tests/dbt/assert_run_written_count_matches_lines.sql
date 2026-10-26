-- 대사: run JSON 의 writtenCount = 그 run 이 쓴 JSONL 줄 수 (0건 실행은 파일이 없어야 하므로 0 = 0)
with lines as (
    select run_id, count(*) as line_count
    from {{ ref('stg_article_lines') }}
    group by 1
)

select r.run_id, r.written_count, coalesce(l.line_count, 0) as line_count
from {{ ref('stg_runs') }} as r
left join lines as l
    on l.run_id = r.run_id
where r.written_count <> coalesce(l.line_count, 0)
