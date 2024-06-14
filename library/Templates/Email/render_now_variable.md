SUBJECT: LogMan.io detected anomaly for {% if dimension %}'{{ dimension }}'{% endif %}

## Anomaly detected

Please find more information below:

{% if name %}
Event reason: ***{{ name }}***
{% endif %}

{% if tenant %}
Tenant: ***{{ tenant }}***
{% endif %}

{% if dimension %}
User anomaly occurred for: ***{{ dimension }}*** {% endif %}{% if now %}
at ***{{ now() | datetimeformat('%d-%m-%Y %H:%M') }} UTC***{% endif %}

For more information regarding this anomaly, please see this **[event]({{public_url}}/?tenant={{tenant}}#/discover/lmio-{{tenant}}-events-complex?aggby=day&filter=&ts=now-14d&te=now&refresh=off&size=40&selectedfields=%255B%255D&groupby=&filteredfields=%255B%257B%2522lmio.alert.dimension%2522%253A%2522{{ dimension }}%2522%257D%255D)** in your **[TeskaLabs LogMan.io]({{ public_url }}/?tenant={{ tenant }}#/discover)**
