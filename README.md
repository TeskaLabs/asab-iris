# ASAB Iris

ASAB Iris is a microservice for (1) rendering documents (reports, email bodies and attachments) using templates and (2) sending these documents to users using email, SMS and instant messaging services such as Slack.

ASAB Iris could be used for e.g. generating emails based on templates, rendering regular reports from dataset and so on.
It is a multifuntional messanger.


## Supported technologies

 * HTTP REST API
 * Apache Kafka (for incoming async requests)
 * Email (SMTP for outgoing mails)
 * Slack
 * Jinja2 for templating
 * Markdown (for templating, using Jinja2)
 * HTML (for templating, using Jinja2)
 * PDF (conversion of the output)
 * Powered by [ASAB](https://github.com/TeskaLabs/asab)


## Use cases


### Send email

 * Use a template for email (Jinja, Markdown or HTML)
 * Use a template for attachment(s) (Jinja or Markdown) and format is HTML or PDF
 * Specify To, From, CC, BCC; or use defaults from configuration
 * Specify Subject or extract it from email body
 * Triggers by a web handler call (or calls), or Apache Kafka message
 * Use SMTP to send email
 * Templates are in the ASAB library


### Render a report

 * Use a template from ASAB library
 * Use formatter(s) to get HTML or PDF document
 * HTTP REST API to get the report
 * Templates are in the ASAB library
