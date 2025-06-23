SUBJECT: TeskaLabs LogMan.io EPS calculation

Dear,

Thank you for using the _TeskaLabs LogMan.io_ EPS Calculator.
Below is the summary of your estimated Event Per Second (EPS) and data volume requirements:

## Summary

- **Estimated Total EPS**: {{ "%.2f"|format(totaleps) }}
- **Estimated Total Volume per Day**: {{ "%.2f"|format(totalvolume) }} GB
- **Requested Retention**: {{ retention }} months

## Input Breakdown

| Logs Source Type         | Count | EPS     | Volume |
|--------------------------|-------|---------|--------|
{% for item in items if item.count | int > 0 -%}
| {{ item.id }} | {{ item.count }} | {{ "%.2f"|format(item.eps) }} | {{ "%.2f"|format(item.volume) }} GB/day |
{% endfor %}

## Your Contact Details

- **Name**: {{ fromname }}
- **Company**: {{ fromcompany }}
- **Email**: {{ fromemail }}
{% if fromphone %}
- **Phone**: {{ fromphone }}
{% endif %}

If you have any questions or need further assistance, feel free to reach out to our team at [sales@teskalabs.com](mailto:sales@teskalabs.com).

Best regards,  
TeskaLabs Team

[https://logman.io](https://logman.io)
