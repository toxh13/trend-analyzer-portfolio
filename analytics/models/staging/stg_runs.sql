-- 수집 실행 1회 = 1행 (raw/runs/dt=*/<runId>.json)
with files as (
    select filename, content::json as doc
    from read_text('{{ raw_glob("runs/dt=*/*.json") }}')
)

select
    filename as file_path,
    doc ->> 'runId' as run_id,
    doc ->> 'startedAt' as started_at_text,
    doc ->> 'completedAt' as completed_at_text,
    try_cast(replace(doc ->> 'startedAt', 'Z', '') as timestamp) as started_at,
    try_cast(replace(doc ->> 'completedAt', 'Z', '') as timestamp) as completed_at,
    doc ->> 'outcome' as outcome,
    doc ->> 'trigger' as trigger,
    cast(doc ->> 'crawlerOutputCount' as bigint) as crawler_output_count,
    cast(doc ->> 'validationRejectedCount' as bigint) as validation_rejected_count,
    cast(doc ->> 'duplicateUrlCount' as bigint) as duplicate_url_count,
    cast(doc ->> 'previouslySeenCount' as bigint) as previously_seen_count,
    cast(doc ->> 'eligibleCount' as bigint) as eligible_count,
    cast(doc ->> 'selectedCount' as bigint) as selected_count,
    cast(doc ->> 'droppedByLimitCount' as bigint) as dropped_by_limit_count,
    cast(doc ->> 'preprocessingFailedCount' as bigint) as preprocessing_failed_count,
    cast(doc ->> 'writtenCount' as bigint) as written_count,
    cast(doc ->> 'writeFailedCount' as bigint) as write_failed_count,
    cast(doc ->> 'reconciliationOk' as boolean) as reconciliation_ok,
    cast(doc ->> 'durationMs' as bigint) as duration_ms,
    doc ->> 'codeVersion' as code_version,
    coalesce(doc -> 'channels', '[]'::json) as channels_json
from files
