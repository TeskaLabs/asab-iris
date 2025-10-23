# ASAB Iris

Welcome to ASAB Iris, your go-to multifunctional messenger microservice, designed for automated *document rendering* and message dispatching across various communication channels!

## Use Cases

### 📧 1. Sending Emails

**Overview**  
- Craft emails with Jinja, Markdown or HTML templates.  
- Personalize recipients, subject, and body via template parameters.  
- Trigger through the single `/send_email` endpoint (HTTP or Kafka).

---

**Configuration**

IRIS will automatically choose **MS365** if *all* of these settings are present in your `asab.Config`:

```ini
[m365_email]
tenant_id     = YOUR_AZURE_TENANT_ID
client_id     = YOUR_APP_CLIENT_ID
client_secret = YOUR_APP_CLIENT_SECRET
user_email    = sender@yourdomain.com
subject       = Default MS365 Subject
````

Otherwise, if `[m365_email]` is missing or incomplete, IRIS falls back to **SMTP** when you set a non-empty `host`:

```ini
[smtp]
host      = smtp.example.com
user      = admin
password  = secret
from      = info@example.com
ssl       = no
starttls  = yes
subject   = Default SMTP Subject
```

> **Note**
>
> * SMTP **supports** attachments and will include them in the outbound message.
> * MS365 **ignores** attachments (you’ll see a warning in the logs if you pass any).
> * All email templates must live under `/Templates/Email/`.
> * If both SMTP and MS365 are configured, SMTP will be used as the default mail transport.

---

Good point — you should make that explicit so readers understand the **precedence** clearly.
Here’s a concise, polished version you can drop in (replacing your current “How Microsoft 365 Email Works” section):

---

### ⚙️ How Microsoft 365 Email Works

When **MS365** is configured, Iris sends emails through the **Microsoft Graph API** instead of SMTP.
It uses **OAuth2 client-credentials flow** to authenticate using your Azure app credentials.

**Flow summary:**

1. Reads the `[m365_email]` configuration.
2. Initializes an MSAL client with your `tenant_id`, `client_id`, and `client_secret`.
3. Obtains an access token for the scope `https://graph.microsoft.com/.default`.
4. Sends the message via `POST https://graph.microsoft.com/v1.0/users/{user_email}/sendMail`.
5. Supports HTML body, CC/BCC, and inline base64-encoded attachments.

**Transport selection logic:**

* If **only `[m365_email]`** is configured → MS365 is used.
* If **only `[smtp]`** is configured → SMTP is used.
* If **both** are configured → **SMTP takes priority** and will be used as the default transport.
* If **neither** is configured → the `/send_email` API returns `400 Email service not configured.`

---

**Example Web Request**

```http
PUT /send_email
Content-Type: application/json

{
  "to": ["alice@example.com", "bob@example.com"],
  "from": "noreply@yourdomain.com",
  "subject": "Monthly Report",
  "body": {
    "template": "/Templates/Email/report.md",
    "params": {
      "name": "Alice",
      "month": "June"
    }
  },
  "attachments": [
    {
      "template": "/Templates/Email/summary.html",
      "params": {},
      "format": "pdf",
      "filename": "summary.pdf"
    }
  ]
}
```

> Depending on your configuration, this request will be sent via **SMTP** (with the PDF attachment) or via **MS365** (attachment dropped).


## Email Markdown Wrapper Configuration

**Configuration**

```ini
[email]
markdown_wrapper=/Templates/Email/body_wrapper.html
```

- `markdown_wrapper`: Specifies the path to the HTML template for wrapping email content.
If this configuration is not provided, or if the value is left empty, the markdown_wrapper will default to None. In such cases, Markdown-formatted emails will be sent without any additional HTML wrapping. This means the emails will consist solely of the content converted from Markdown to HTML, without any extra styling or structure provided by a wrapper template.

## 🔐 SMTP Transport & TLS Verification

**Keys (under `[smtp]`)**

```ini
# Transport
host            = smtp.example.com
port            = 465                 ; 465 = implicit TLS (SMTPS), 587 = STARTTLS
user            = admin
password        = secret
from            = info@example.com

# TLS mode (choose ONE)
ssl             = yes                 ; yes => implicit TLS (465)
starttls        = no                  ; yes => STARTTLS (587). Do NOT enable both.

# Verification
validate_certs  = yes                 ; Verify server certificate (recommended in prod)
cert_bundle     =                     ; Path to CA/chain PEM when validate_certs=yes.
                                      ; Needed for self-signed/internal CAs.
                                      ; Leave empty to use system trust store.
                                      ; When validate_certs=no, both chain and hostname checks are disabled and
                                      ; cert_bundle is ignored.

```

**Important**

* Use real booleans: `yes|no` (not quoted strings).
* `cert_bundle` must be a **CA/chain PEM**, **not** the server cert.
* If you supply a custom TLS context in code, some clients ignore `validate_certs`/`cert_bundle`.

**Common Setups**

**A) Production — SMTPS (465) with internal CA**

```ini
[smtp]
host            = mail.internal.lan
user            = admin
port            = 465
ssl             = yes
starttls        = no
password        = ****
from            = noreply@internal.lan
validate_certs  = yes
cert_bundle     = /etc/ssl/internal_ca.pem
```

**B) Production — STARTTLS (587) with public CA**

```ini
[smtp]
host            = smtp.example.com
user            = admin
port            = 587
ssl             = no
starttls        = yes
password        = ****
from            = noreply@example.com
validate_certs  = yes
cert_bundle     =                    ; empty = use system trust store
```

**C) Local Dev — no TLS (not for prod)**

```ini
[smtp]
host            = 127.0.0.1
user            = admin
port            = 2525
ssl             = no
starttls        = no
password        =
from            = dev@localhost
validate_certs  = no
cert_bundle     =
```

### 🚨 2. Sending Slack messages

**Overview**

- Send messages to a Slack via HTTP REST API or through Kafka Topic
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

### 📱 4. Sending SMS messages

**Overview**

- Send SMS messages using the SMSBrana.cz API.
- Supports automatic segmentation of long messages.
- Apply Jinja2 templates.
- Trigger them through a web handler or an Apache Kafka message - flexibility is key!

**Configuration**

```ini
[sms]
login=your_smsbrana_login
password=your_smsbrana_password
timestamp_format=%Y%m%dT%H%M%S
api_url=https://api.smsbrana.cz/smsconnect/http.php
```

**Explanation**

- `login`: Your login for the SMSBrana.cz service.
- `password`: Your password for the SMSBrana.cz service.
- `timestamp_format`: The format used for timestamps, typically `"%Y%m%dT%H%M%S"`.
- `api_url`: The API URL for SMSBrana.cz, typically `https://api.smsbrana.cz/smsconnect/http.php`.

**Handling Long Messages**

- SMS messages are automatically split into segments if they exceed the length limits:
  - 1 SMS: up to 160 characters.
  - 2 SMS: up to 306 characters (153 characters per segment).
  - 3 SMS: up to 459 characters (153 characters per segment).
- Each segment is sent separately, ensuring that messages are not truncated.

**Usage Example**

To send an SMS, you can configure the SMS service in your application and trigger it via a web handler or Kafka message. The service will handle splitting long messages into segments and sending them sequentially.

**Error Handling**

- **Invalid Phone Number**: If the phone number is missing or invalid, an `ASABIrisError` is raised.
- **Non-ASCII Characters**: If the message contains non-ASCII characters, an `ASABIrisError` is raised.
- **Service Errors**: Errors returned by the SMSBrana.cz API are mapped to custom error messages and logged for troubleshooting.


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

## Jinja2 Filters and Functions

### `now()` Function

The `now()` function returns the current UTC datetime. You can use this function in your Jinja2 templates to insert the current date and time.

**Usage Example:**

```jinja2
{{ now() }}
```

This will output the current date and time in the default format.

### `datetimeformat` Filter

The `datetimeformat` filter allows you to format datetime objects in your Jinja2 templates. 

**Usage Example:**

To format the current datetime returned by `now()`:

```jinja2
{{ now()|datetimeformat('%Y-%m-%d %H:%M:%S') }}
```

**Possible Formats:**

Here are some common format strings you can use with the `datetimeformat` filter:

- `%Y-%m-%d %H:%M:%S` - Outputs as `2024-06-17 14:45:30`
- `%d-%m-%Y` - Outputs as `17-06-2024`
- `%A, %d %B %Y` - Outputs as `Monday, 17 June 2024`
- `%I:%M %p` - Outputs as `02:45 PM`
- `%B %d, %Y` - Outputs as `June 17, 2024`
- `%Y-%m-%d` - Outputs as `2024-06-17`


### 🚀 5. Sending Notifications to Kafka

**Overview**

ASAB Iris supports sending notifications to various communication channels such as email, Slack, and Microsoft Teams via Kafka. Each notification is structured using templates and parameters to ensure customizable content.

#### Kafka Message Structure

- Notifications are sent to Kafka in JSON format.
- Each notification contains a `type` field specifying the channel (e.g., `email`, `slack`, `msteams`), and a `body` that includes the template and its parameters.

#### 1. Sending Email Notifications

**Example Kafka Message:**

```json
{
    "type": "email",
    "to": ["Shivashankar <mithunshivashankar@gmail.com>"],
    "from": "info@teskalabs.com",
    "body": {
        "template": "/Templates/Email/message.md",
        "params": {
            "name": "I am testing a template",
            "error": "None"
        }
    }
}
```

**Explanation:**

- `type`: Defines the notification type as `email`.
- `to`: List of recipients.
- `from`: The sender's email address.
- `template`: Path to the template used for the email content.
- `params`: Parameters for populating the email template.

#### 2. Sending Slack Notifications

**Example Kafka Message:**

```json
{
    "type": "slack",
    "body": {
        "template": "/Templates/Slack/Slack example.md",
        "params": {
            "name": "I am testing a template",
            "error": "None"
        }
    }
}
```

**Explanation:**

- `type`: Defines the notification type as `slack`.
- `body.template`: Path to the Slack message template.
- `params`: Parameters for populating the Slack template.

#### 3. Sending Microsoft Teams Notifications

**Example Kafka Message:**

```json
{
    "type": "msteams",
    "body": {
        "template": "/Templates/MSTeams/Teams example.md",
        "params": {
            "name": "I am testing a template",
            "error": "None"
        }
    }
}
```

**Explanation:**

- `type`: Defines the notification type as `msteams`.
- `body.template`: Path to the Microsoft Teams message template.
- `params`: Parameters for populating the Teams template.
```
