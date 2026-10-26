-- 대사: reconciliationOk = true 라고 적은 실행은 DESIGN 4절 대사식을 실제로 만족해야 한다
-- received = validInput + validationRejected, validInput = duplicateUrl + previouslySeen + eligible,
-- eligible = selected + droppedByLimit, selected = preprocessingFailed + written + writeFailed
select run_id
from {{ ref('stg_runs') }}
where reconciliation_ok
  and not (
      crawler_output_count - validation_rejected_count
          = duplicate_url_count + previously_seen_count + eligible_count
      and eligible_count = selected_count + dropped_by_limit_count
      and selected_count = preprocessing_failed_count + written_count + write_failed_count
  )
