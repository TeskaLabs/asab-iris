SUBJECT: TeskaLabs LogMan.io EPS kalkulace

Dobrý den,

Děkujeme za použití _TeskaLabs LogMan.io_ EPS kalkulačky.
Níže naleznete shrnutí vašich odhadovaných požadavků na události za sekundu (EPS) a objem dat:

## Shrnutí

- **Odhadovaný celkový EPS**: {{ "%.2f"|format(totaleps) }}
- **Odhadovaný celkový objem za den**: {{ "%.2f"|format(totalvolume) }} GB
- **Požadovaná retence**: {{ retention }} měsíců

## Rozpis zdrojů logů

| Typ zdroje logů         | Počet | EPS     | Objem |
|--------------------------|-------|---------|--------|
{% for item in items if item.count | int > 0 -%}
| {{ item.id }} | {{ item.count }} | {{ "%.2f"|format(item.eps) }} | {{ "%.2f"|format(item.volume) }} GB/den |
{% endfor %}

## Vaše kontaktní údaje

- **Jméno**: {{ fromname }}
- **Společnost**: {{ fromcompany }}
- **Email**: {{ fromemail }}
{% if fromphone %}
- **Telefon**: {{ fromphone }}
{% endif %}

Pokud máte jakékoliv otázky nebo potřebujete další pomoc, neváhejte nás kontaktovat na [sales@teskalabs.com](mailto:sales@teskalabs.com).

S pozdravem,  
Tým TeskaLabs

[https://logman.io](https://logman.io)
