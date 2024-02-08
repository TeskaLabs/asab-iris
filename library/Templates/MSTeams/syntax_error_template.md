{# Incorrect Jinja2 syntax (missing endfor) which will raise a TemplateSyntaxError #}
{% for item in some_list %}
    {{ item }}
{# Missing {% endfor %} here #}
