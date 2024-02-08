# ASAB Iris

Welcome to ASAB Iris, your go-to multifunctional messenger microservice, designed for automated *document rendering* and message dispatching across various communication channels!

## Use Cases

### 📧 1. Sending Emails

**Overview**

- Craft beautiful emails with templates using Jinja, Markdown, or HTML.
- Personalize recipient details or go with default configurations.
- Trigger them through a web handler or an Apache Kafka message - flexibility is key!

**Configuration**

```ini
[smtp]
host=smtp.example.com
user=admin
password=secret
from=info@example.com
ssl=no
starttls=yes
subject=Mail from ASAB Iris
```

**Explanation**

- `host`: Your SMTP server's address.
- `user`: Your username for the SMTP server.
- `password`: Your super-secret password.
- `from`: The default "From" address for your emails.
- `ssl`: `yes`/`no` for SSL, depends on the SMTP server.
- `starttls`: `yes`/`no` for STARTTLS, depends on the SMTP server.
- `subject`: The default subject line, if not provided by a caller or a template.

### 🚨 2. Sending Slack messages

**Overview**

- Send messages to a Slack via HTTP REST API or thru Kafka Topic
- Apply Jinja2 templates.
- Trigger them through a web handler or an Apache Kafka message - flexibility is key!

**Configuration**

```ini
[slack]
token=xoxb-111111111111-2222222222222-3333333333333voe
channel=general
```
**Explanation**

- `token`: Your Slack OAuth access token.
- `channel`: The Slack channel you want to send messages to.

#### 🤖 Creating Slack OAuth access token for Slack Apps

##### Prerequisites

- A Slack workspace where you're the admin of app creation.

##### Steps

1. Visit the [Slack API website](https://api.slack.com/apps).
2. Select "Create New App".
3. Name your app and choose its home (workspace).
4. Select "Create App"
5. Configure "OAuth & Permissions".
6. Add the necessary scopes: `chat:write`, `files:write`, `files:read` and `channels:read`.
7. Select "Install to Workspace".
8. "Allow"
9. Copy the OAuth access token.

Add following scopes for:

* `groups:read`: for posting to private channels
* `im:read`: for posting to direct messsages
* `mpim:read`: for posting to group direct messages


##### Adding the App to a Channel

1. Choose a channel in your Slack workspace.
2. Invite the app.
3. Search for your app and select it.
4. Confirm the addition.
5. Verify the app's presence.


### 📬 3. Sending Microsoft Teams messages

**Overview**

- Send messages to a Microsoft Teams via HTTP REST API or thru Kafka Topic
- Apply Jinja2 templates.
- Trigger them through a web handler or an Apache Kafka message - flexibility is key!

**Configuration**

```ini
[outlook]
webhook_url=https://outlook.office.com/webhook/...
```

**Explanation**

- `webhook_url`: Your webhook URL.


## Error Handling

asab-iris implements specific error handling strategies for the Kafka and Web handlers to ensure robustness and reliability.

### KafkaHandler Error Handling

- **Fallback Mechanism:** In case of errors during message processing, a fallback mechanism is triggered. This ensures that the system can still operate or recover gracefully when encountering issues.
- **General Error Logging:** Any errors during message dispatching are logged as exceptions.

### WebHandler Error Handling

- **Error Responses:** Internal error codes are mapped to HTTP status codes, providing meaningful responses to clients.
- **Exception Handling:** General exceptions are logged, and standardized error responses are sent to clients.


## 🛠 Supported Technologies

- Inbound: HTTP REST API
- Inbound: Apache Kafka
- Jinja2 for template specifications
- Markdown for templates
- HTML for templates and the output
- PDF for the output
- Output: Email SMTP
- Output: Slack
- Output: Microsoft Teams
- Powered by [ASAB](https://github.com/TeskaLabs/asab) (because we’re standing on the shoulders of giants)

## 📚 More info

* [Documentation](https://teskalabs.github.io/asab-iris/)

_Diagram: Architecture_  

![Architecture](./docs/asab-iris-architecture.drawio.svg)
