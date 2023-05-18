# ASAB Iris

ASAB Iris is a microservice for (1) rendering documents (reports, email bodies and attachments) using templates and (2) sending these documents to users using email, SMS and instant messaging services such as Slack.

ASAB Iris could be used for e.g. generating emails based on templates, rendering regular reports from dataset and so on.
It is a multifuntional messanger.

## Documentation

https://teskalabs.github.io/asab-iris/


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

### Send slack Alerts

 * Consume the messages from Kafka topic.
 * With the help of info from messages , get a template from ASAB library.
 * HTTP REST API to send the alert messages using rendered template.



## Architecture

![](./docs/asab-iris-architecture.drawio.svg)

**WARNING: Templates used for email or Slack must be stored in Templates dir in filesystem or Templates node in zookeeper**

**Templates used for emailing must be stored under**
```
/Templates/Email/
```

**Templates used by Slack must be stored under**
```
/Templates/Slack/
```

**Templates used for other purpose must be stored under**
```
/Templates/General/
```

## Creating Xbot Tokens for Slack Apps

### Prerequisites
- You have a Slack workspace where you can create and install apps.
- You have a GitHub repository where you want to add the instructions.

### Step 1: Create a Slack App
1. Go to the [Slack API website](https://api.slack.com/apps) and sign in to your Slack account.
2. Click on the "Create New App" button.
3. Give your app a name and select the workspace where you want to install it.
4. Click on the "Create App" button.

### Step 2: Configure App Permissions
1. In the left sidebar, click on "OAuth & Permissions".
2. Scroll down to the "Bot Token Scopes" section and click on the "Add an OAuth Scope" button.
3. Add the necessary scopes for sending messages and uploading files. For example:
   - `chat:write` (for sending messages)
   - `files:write` (for uploading files)
4. Click on the "Save Changes" button.

### Step 3: Install the App in your Workspace
1. In the left sidebar, click on "OAuth & Permissions".
2. Scroll up to the "OAuth Tokens & Redirect URLs" section.
3. Click on the "Install to Workspace" button.
4. Review the requested scopes and click on the "Allow" button.
5. Copy the generated OAuth access token. This will be your xbot token.

## Adding the App to a Channel

### Step 1: Choose a Channel
1. Open your Slack workspace and navigate to the channel where you want to add the app.

### Step 2: Invite the App to the Channel
1. In the channel, click on the channel name or the gear icon to access the channel settings.
2. Select "Add apps" from the dropdown menu.

### Step 3: Search for the App
1. In the search bar, type the name of your app and press Enter.
2. Locate your app in the search results and click on it to select it.

### Step 4: Confirm the Addition
1. Review the app details and permissions to ensure it aligns with your requirements.
2. Click on the "Add to Channel" or "Add" button to add the app to the channel.

### Step 5: Verify the App's Presence
1. Look for the app's name or icon in the channel member list.
2. If the app is successfully added, it should appear as a member of the channel.
