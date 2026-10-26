-- 원천 JSONL 의 모든 줄 (중복 URL 포함). 수량 대사와 최초 수집 행 판단에 쓴다.
with files as (
    select filename, string_split(content, chr(10)) as lines
    from read_text('{{ raw_glob("articles/dt=*/*.jsonl") }}')
),

lines as (
    select
        filename,
        generate_subscripts(lines, 1) - 1 as line_no,
        unnest(lines) as line
    from files
),

docs as (
    -- 빈 줄은 건너뛴다. 필터가 JSON 파싱보다 뒤로 밀려도 깨지지 않게 CASE 로 감싼다
    select
        filename,
        line_no,
        case when {{ py_strip('line') }} <> '' then line::json end as doc
    from lines
    where {{ py_strip('line') }} <> ''
)

select
    filename as file_path,
    line_no,
    json_extract_string(doc, '$.runId') as run_id,
    json_extract_string(doc, '$.channel') as channel,
    json_extract_string(doc, '$.source') as source,
    json_extract_string(doc, '$.category') as raw_category,
    json_extract_string(doc, '$.title') as title,
    json_extract_string(doc, '$.summary') as summary,
    json_extract_string(doc, '$.sourceUrl') as source_url,
    try_strptime(json_extract_string(doc, '$.publishedAt'), '%Y-%m-%dT%H:%M:%S') as published_at,
    try_cast(replace(json_extract_string(doc, '$.crawledAt'), 'Z', '') as timestamp) as crawled_at,
    coalesce(json_extract(doc, '$.keywords'), '[]'::json) as keywords_json
from docs
