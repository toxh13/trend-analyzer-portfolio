{#
  v1 키워드 비교 규칙을 SQL 로 옮긴 매크로입니다.
  기준 구현(fixtures/reference/v1_reference.py)은 Python str.strip()/split() 을 쓰므로,
  RE2 의 \s(ASCII 공백)만으로는 부족해 Python 이 공백으로 보는 문자를 모두 나열합니다.
#}

{% macro py_whitespace_class() -%}
[\s\x{0b}\x{1c}-\x{1f}\x{85}\x{a0}\x{1680}\x{2000}-\x{200a}\x{2028}\x{2029}\x{202f}\x{205f}\x{3000}]
{%- endmacro %}

{# Python str.strip() #}
{% macro py_strip(expr) -%}
regexp_replace({{ expr }}, '^{{ py_whitespace_class() }}+|{{ py_whitespace_class() }}+$', '', 'g')
{%- endmacro %}

{# v1 normalizeForCompare: trim → 소문자 (차단 키워드, 기사 안 중복 판단) #}
{% macro normalize_for_compare(expr) -%}
lower({{ py_strip(expr) }})
{%- endmacro %}

{# v1 KeywordNormalizer.normalize: trim → 소문자 → 모든 공백 제거 → '.' 제거 → '-' 제거 (alias 조회) #}
{% macro normalize_keyword(expr) -%}
replace(replace(regexp_replace(lower(coalesce({{ expr }}, '')), '{{ py_whitespace_class() }}+', '', 'g'), '.', ''), '-', '')
{%- endmacro %}

{# 대표 키워드·카테고리·기사 URL 의 slug: UTF-8 SHA-256 앞 16자리 hex #}
{% macro slug(expr) -%}
left(sha256({{ expr }}), 16)
{%- endmacro %}

{# v1 KeywordAliasCacheService.resolveKeyword: 승인된 alias 면 대표 키워드, 아니면 입력 그대로.
   alias_alias 는 stg_keyword_aliases 를 normalized_alias 로 left join 한 별칭 #}
{% macro resolve_keyword(expr, alias_alias) -%}
coalesce({{ alias_alias }}.canonical_keyword, {{ expr }})
{%- endmacro %}

{# Python 처럼 왼쪽부터 차례로 더한 double 합계. 정렬 동점 판단이 기준 구현과 같은 부동소수점 값을 보게 한다 #}
{% macro ordered_fsum(expr, order_by) -%}
list_reduce(list(({{ expr }})::double order by {{ order_by }}), lambda acc, value: acc + value)
{%- endmacro %}

{# v1 TrendService.roundToThreeDecimals: Math.round(value * 1000.0) / 1000.0 (half-up) #}
{% macro java_round3(expr) -%}
(floor(({{ expr }}) * 1000.0::double + 0.5::double) / 1000.0::double)
{%- endmacro %}
