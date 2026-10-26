{#
  입력 위치와 기준 시각. 경로는 환경 변수로 받아서 build_site.py 가 --raw-root, --seeds-dir 를 그대로 넘긴다.
  read_text 는 일치하는 파일이 없으면 빈 결과를 돌려주므로 첫 실행(빈 data 브랜치)에서도 실패하지 않는다.
#}

{% macro raw_glob(relative) -%}
{{ (env_var('RAW_DATA_DIR', '../fixtures/raw-root') ~ '/raw/' ~ relative) | replace("'", "''") }}
{%- endmacro %}

{% macro seed_file(name) -%}
{{ (env_var('SEEDS_DIR', 'seeds') ~ '/' ~ name) | replace("'", "''") }}
{%- endmacro %}

{# 서울 로컬 기준 시각 (timestamp, 오프셋 없음) #}
{% macro as_of() -%}
strptime('{{ var("as_of") }}', '%Y-%m-%dT%H:%M:%S')
{%- endmacro %}

{# 같은 시각의 UTC (서울은 1988년 이후 일광 절약 시간이 없어 +09:00 고정) #}
{% macro as_of_utc() -%}
({{ as_of() }} - interval 9 hours)
{%- endmacro %}

{# 30일 추이 시작: 오늘-29일 00:00 #}
{% macro history_start() -%}
(cast({{ as_of() }} as date) - interval 29 days)::timestamp
{%- endmacro %}
