# ASAB Iris

ASAB Iris is a multifunctional messenger microservice designed for rendering documents and sending them to users via various communication channels. It can generate emails based on templates, render regular reports from datasets, and more.

## Use Cases

### 1. Sending Emails

#### Overview
- Utilize templates for email and attachments using Jinja, Markdown, or HTML.
- Specify recipients, senders, CC, BCC, or use default configurations.
- Define the subject or extract it from the email body.
- Trigger via a web handler call(s) or Apache Kafka message.

#### Configuration
```ini
[smtp]
host=smtp.example.com
user=admin
password=password
from=info@example.com
ssl=no
starttls=yes
subject=Mail from ASAB Iris
```
Explanation:
- `host`: The address of the SMTP server.
- `user`: Username for SMTP server authentication.
- `password`: Password for SMTP server authentication.
- `from`: Default "From" address for emails.
- `ssl`: Use SSL for the connection (yes/no).
- `starttls`: Use STARTTLS (yes/no).
- `subject`: Default email subject.

### 2. Sending Slack Alerts

#### Overview
- Consume messages from a Kafka topic and retrieve templates using message info from the ASAB library.
- Use HTTP REST API to send alert messages using rendered templates.

#### Configuration
```ini
[slack]
token=xoxb-111111111111-2222222222222-3333333333333voe
channel=general
```
Explanation:
- `token`: OAuth access token (xbot token) for Slack.
- `channel`: Default Slack channel for sending messages.

### 3. Creating an Incoming Webhook for Outlook

#### Overview
- Navigate to Outlook settings and create a new webhook.
- Configure the webhook URL and set triggers.
- Customize additional settings and save the configuration.

#### Configuration
```ini
[outlook]
webhook_url=https://outlook.office.com/webhook/...
```
Explanation:
- `webhook_url`: Webhook URL provided by Outlook.

## Supported Technologies
- HTTP REST API
- Apache Kafka (for incoming async requests)
- Email (SMTP for outgoing mails)
- Slack
- Jinja2, Markdown, and HTML for templating
- PDF (conversion of the output)
- Powered by [ASAB](https://github.com/TeskaLabs/asab)

## Documentation
Detailed documentation is available [here](https://teskalabs.github.io/asab-iris/).

## Architecture
![ASAB Iris Architecture](./docs/asab-iris-architecture.drawio.svg)

### Template Storage Warning
Templates used for email or Slack must be stored in specific directories in the filesystem or Templates node in Zookeeper. For example, email templates must be stored under `/Templates/Email/`.

## Example Configuration

```ini
[library]
providers=./library

[web]
listen=:8080

[smtp]
host=smtp.example.com
user=admin
password=password
from=info@example.com
ssl=no
starttls=yes
subject=Mail from ASAB Iris

[slack]
token=xoxb-111111111111-2222222222222-3333333333333voe
channel=general

[msteams]
webhook_url=https://teskalabscom.webho
```
Explanation:
- `[library]`: Configuration related to the ASAB library.
  - `providers`: Path to the library.
- `[web]`: Configuration related to the web interface.
  - `listen`: The address and port on which ASAB Iris will listen for HTTP requests.
- `[msteams]`: Configuration related to Microsoft Teams (if applicable).
  - `webhook_url`: Webhook URL for sending messages to Microsoft Teams.

Feel free to adjust the explanations as per your specific setup and requirements. If there are any other sections or details you'd like to add or modify, please let me know!