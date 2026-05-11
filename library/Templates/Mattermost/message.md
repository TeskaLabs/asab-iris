### TeskaLabs LogMan.io Notification

{% if title %}
**Alert:** {{ title }}
{% else %}
**Alert:** LogMan.io detected an event that may require attention.
{% endif %}

{% if severity %}
**Severity:** {{ severity }}
{% endif %}

{% if tenant %}
**Tenant:** {{ tenant }}
{% endif %}

{% if type %}
**Type:** {{ type }}
{% endif %}

{% if status %}
**Status:** {{ status }}
{% endif %}

{% if ticketid %}
**Ticket ID:** {{ ticketid }}
{% endif %}

{% if username %}
**User:** {{ username }}
{% elif user.name %}
**User:** {{ user.name }}
{% endif %}

{% if device.name %}
**Device:** {{ device.name }}
{% endif %}

{% if source.ip %}
**Source IPv4:** {{ source.ip }}
{% endif %}

{% if client.ip %}
**Source IPv6:** {{ client.ip }}
{% endif %}

{% if event.code %}
**Event Code:** {{ event.code }}
{% endif %}

{% if message %}
**Summary:** {{ message }}
{% endif %}

{% if credid %}
**Changed By Credential ID:** {{ credid }}
{% endif %}

{% if public_url and tenant %}
[Open incident in LogMan.io]({{ public_url }}/?tenant={{ tenant }}#)
{% elif public_url %}
[Open LogMan.io]({{ public_url }})
{% endif %}

Please review the event details and validate the rendered output before release or integration.
