select count(*) as row_count
from {{ ref('fct_pipeline_status') }}
having count(*) <> 1
