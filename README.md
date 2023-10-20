# 🌟 ASAB Iris 🌟

Welcome to ASAB Iris, your go-to multifunctional messenger microservice, shining bright in the world of automated document rendering and message dispatching across various communication channels! 🚀

## 🎯 Use Cases

### 📧 1. Sending Emails

**Overview:**
- Craft beautiful emails with templates using Jinja, Markdown, or HTML.
- Personalize recipient details or go with default configurations - the world is your oyster!
- Subjects? Write your own or let ASAB Iris pick up the vibes from the email body.
- Kick things off through a web handler or an Apache Kafka message - flexibility is key!

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
- `host`: Your SMTP server's address, where all the magic starts.
- `user`: The magician's name (well, your username for the SMTP server).
- `password`: The magic word (a.k.a. your super-secret password).
- `from`: Your wizard's alias (the default "From" address for your emails).
- `ssl`: A spell to encrypt your messages (yes/no for SSL).
- `starttls`: Another incantation for security (yes/no for STARTTLS).
- `subject`: The default subject line - because even magicians need intros!

### 🚨 2. Sending Slack Alerts

**Overview:**
- Consume messages like a pro from a Kafka topic, retrieving templates with ASAB's library.
- Send out those alert messages via HTTP REST API, all jazzed up with your rendered templates.

**Configuration:**
```ini
[slack]
token=xoxb-111111111111-2222222222222-3333333333333voe
channel=general
```
**Explanation:**
- `token`: Your secret key to the Slack kingdom (OAuth access token).
- `channel`: Your default court for heralding messages (Slack channel).

### 📬 3. Creating an Incoming Webhook for Outlook

**Overview:**
- Dive into Outlook settings and whip up a new webhook.
- Set the stage with your webhook URL and chosen acts (triggers).
- Tweak the settings to your heart's content and let the show begin!

**Configuration:**
```ini
[outlook]
webhook_url=https://outlook.office.com/webhook/...
```
**Explanation:**
- `webhook_url`: The stage door (your webhook URL provided by Outlook).

## 🛠 Supported Technologies
- HTTP REST API (for all your webby needs)
- Apache Kafka (bringing async requests into the mix)
- Email (SMTP for outgoing mails, because retro is cool)
- Slack (for when you need to slide into those DMs)
- Jinja2, Markdown, and HTML (templating galore)
- PDF (making sure your docs are picture-perfect)
- Powered by [ASAB](https://github.com/TeskaLabs/asab) (because we’re standing on the shoulders of giants)

## 📚 Documentation
Dive deep into the knowledge ocean with our [detailed documentation](https://teskalabs.github.io/asab-iris/).

## 🏛 Architecture
Behold the blueprint of greatness: ![ASAB Iris Architecture](./docs/asab-iris-architecture.drawio.svg)

## 🧙‍♂️ Example Configuration

```ini
[library]
providers=./library

[web]
listen=:8080

[smtp]
host=smtp.example.com
user=admin
password=secret
from=info@example.com
ssl=no
starttls=yes
subject=Mail from ASAB Iris

[slack]
token=xoxb-111111111111-2222222222222-3333333333333voe
channel=general

[msteams]
webhook_url=https://teskalabscom.webhook.office.com/...
```
**Explanation:**
- `[library]`: The sacred scrolls (configuration related to the ASAB library).
  - `providers`: The path to wisdom (your library location).
- `[web]`: Your digital storefront (web interface configuration).
  - `listen`: Ears to the digital ground (where ASAB Iris listens for HTTP requests).
- `[msteams]`: For when you need to rally the troops on Microsoft Teams.
  - `webhook_url`: Your bat-signal (webhook URL for MS Teams).

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

And voilà, you're all set to weave some ASAB Iris magic! 🌈✨
