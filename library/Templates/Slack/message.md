*🚨 Alert Management Notification 🚨*

*<{{ public_url }}/?tenant={{ tenant }}#|TeskaLabs LogMan.io>* has identified a noteworthy event in your IT infrastructure that might require your immediate attention. 🕵️‍♂️ Please review the following summary of the event:

{% if ticketid %}
🔖 *Ticket ID:* {{ ticketid }} - This ticket has been updated.
{% endif %}

{% if type %}
📑 *Type of Ticket:* {{ type }}
{% endif %}

{% if status %}
📊 *Status Update:* The status was changed to: *{{ status }}*
{% endif %}

{% if credid %}
🔑 *Changed by Credential ID:* {{ credid }}
{% endif %}

{% if username %}
👤 *Changed by User:* {{ username }}
{% endif %}

We encourage you to *review this incident promptly* to determine the next appropriate course of action.

🔍 To examine the incident in greater detail, please log in to your *<{{ public_url }}/?tenant={{ tenant }}#|TeskaLabs LogMan.io>*.

💡 *Remember,* the effectiveness of any security program lies in a swift response. Thank you for your attention to this matter.

Stay safe,

*<{{ public_url }}/?tenant={{ tenant }}#|TeskaLabs LogMan.io>*

Made with ❤️ by *<https://teskalabs.com|TeskaLabs>*
