# ASAB Iris

Welcome to ASAB Iris, your go-to multifunctional messenger microservice, designed for automated *document rendering* and message dispatching across various communication channels!

## Use Cases

### 📧 1. Sending Emails

**Overview:**
- Craft beautiful emails with templates using Jinja, Markdown, or HTML.
- Personalize recipient details or go with default configurations.
- Trigger them through a web handler or an Apache Kafka message - flexibility is key!

**Configuration:**
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

**Explanation:**
- `host`: Your SMTP server's address.
- `user`: Your username for the SMTP server.
- `password`: Your super-secret password.
- `from`: The default "From" address for your emails.
- `ssl`: `yes`/`no` for SSL, depends on the SMTP server.
- `starttls`: `yes`/`no` for STARTTLS, depends on the SMTP server.
- `subject`: The default subject line, if not provided by a caller or a template.

### 🚨 2. Sending Slack messages

**Overview:**
- Send messages to a Slack via HTTP REST API or thru Kafka Topic
- Apply Jinja2 templates.
- Trigger them through a web handler or an Apache Kafka message - flexibility is key!

**Configuration:**
```ini
[slack]
token=xoxb-111111111111-2222222222222-3333333333333voe
channel=general
```
**Explanation:**
- `token`: Your Slack OAuth access token.
- `channel`: The Slack channel you want to send messages to.

### 📬 3. Sending Microsoft Teams messages

**Overview:**
- Send messages to a Microsoft Teams via HTTP REST API or thru Kafka Topic
- Apply Jinja2 templates.
- Trigger them through a web handler or an Apache Kafka message - flexibility is key!

**Configuration:**
```ini
[outlook]
webhook_url=https://outlook.office.com/webhook/...
```

**Explanation:**
- `webhook_url`: Your webhook URL.


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

* [Documentation](https://teskalabs.github.io/asab-iris/).

Architecture: 

![Architecture](./docs/asab-iris-architecture.drawio.svg)


## 🎨 Template Storage and Usage

In the enchanting world of ASAB Iris, templates (especially those crafty Jinja ones) are the spells you cast to conjure up dynamic content for various communication channels like email and Slack.

**Storage Warning:**
Keep your templates in these sacred vaults or the mighty Templates node in Zookeeper, so they're ready for your next spell.

**Directory Structure:**
- `/Templates/Email/`: For your email incantations.
- `/Templates/Slack/`: For Slack spell-casting.
- `/Templates/MSTeams/`: For Microsoft Teams magic
- `/Templates/General/`: For your everyday sorcery.

**Explanation:**
- **Variables**: Your spell components (e.g., `{{ username }}`).
- **Control Statements**: Incantations for content control (like `if` and `for`).
- **Filters**: Magical modifiers for your variables.
- **Inheritance**: Keep your spellbook organized with a master grimoire and supplementary scrolls.

Remember, a tidy spellbook is a mighty spellbook! Store those templates wisely! 📜✨

## 🌐 Creating an Incoming Webhook for Outlook

1. Open your Outlook account and navigate to the "Settings" menu.
2. Search for "Webhooks" or "Connectors" in the Settings menu.
3. Click "Add" or "Create Webhook" to start the magic.
4. Name your webhook (e.g., "GitHub Webhook") so you can recognize it in your spellbook.
5. Set the webhook URL, ensuring it's a valid portal for your messages and files.
6. Choose the events or triggers that will summon the webhook.
7. Customize any additional incantations and save your new magical ally!

## 🤖 Creating Xbot Tokens for Slack Apps

### Prerequisites:
- A Slack workspace where you're the wizard of app creation.
- A GitHub repository for your spell formulas.

### Steps:
1. Visit the [Slack API website](https://api.slack.com/apps).
2. "Create New App" - your wand for this journey.
3. Name your app and choose its home (workspace).
4. "Create App" and watch the magic happen!
5. Configure "OAuth & Permissions" - your spell's components.
6. Add the necessary scopes (e.g., `chat:write`, `files:write`).
7. "Install to Workspace" - like choosing where to cast your spell.
8. "Allow" - give your spell the go-ahead!
9. Copy the OAuth access token (your xbot token , a.k.a. magic key).

### Adding the App to a Channel:
1. Choose a channel in your Slack workspace.
2. Invite the app (summon it to your channel).
3. Search for your app and select it.
4. Confirm the addition (consent is key in magic!).
5. Verify the app's presence (make sure the spell was cast correctly).

And voilà, you're all set to weave some ASAB Iris magic! ✨
