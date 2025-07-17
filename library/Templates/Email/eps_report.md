# TeskaLabs LogMan.io  

Dear {{ username }},  

**{{ message }}**  

You can log in to your [TeskaLabs LogMan.io]({{ public_url }}/?tenant={{ tenant }}#/discover) for more details.  

---

## **EPS Calculation Summary**
- **Custom EPS:** {{ customeps | default("N/A") }}
- **Custom Volume:** {{ customvolume | default("N/A") }} MB
- **Retention (months):** {{ retention | default("N/A") }}
- **Total EPS:** {{ totaleps | default("N/A") }}
- **Total Volume:** {{ totalvolume | default("N/A") }} GB

---

## **Device Breakdown**  
{% for device, details in devices.items() %}
- **{{ device }}**
  - **EPS:** {{ details.eps | default("N/A") }}
  - **Volume:** {{ details.volume | default("N/A") }} MB
  - **Count:** {{ details.count | default("N/A") }}
{% endfor %}

---

## **Contact Details**  
If you have any questions, feel free to contact us:  

- **Name:** {{ fromname | default("N/A") }}  
- **Company:** {{ fromcompany | default("N/A") }}  
- **Phone:** {{ fromphone | default("N/A") }}  
- **Email:** {{ fromemail | default("N/A") }}  

---

Best regards,  
TeskaLabs ASAB-IRIS Team  
📧 Automated Report System  
