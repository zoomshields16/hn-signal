{# In prod, a model's schema is whatever it asks for (staging, analytics).
   Everywhere else everything lands in one schema, so dev work can't touch prod tables. #}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if target.name == 'prod' and custom_schema_name is not none -%}
        {{ custom_schema_name | trim }}
    {%- else -%}
        {{ target.schema }}
    {%- endif -%}
{%- endmacro %}
