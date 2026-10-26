{# dbt_utils 없이 쓰는 복합 키 유일성 테스트 (외부 패키지 설치 없이 오프라인 실행) #}
{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as row_count
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
