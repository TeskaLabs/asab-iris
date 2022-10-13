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
* PDF (output)


## Use cases examples

### Send email

  * Use template from ASAB library for email body (Jinja or Markdown)
  * Use template from ASAB library for attachment(s) (Jinja or Markdown) and format is HTML or PDF
  * Specify To, From, CC, BCC - or use defaults from configuration
  * Specify Subject or extract it from email body
  * Triggers by a web handler call (or calls)
  * Use SMTP to send email


### Render a report

  * Use template from ASAB library
  * Use formatter(s) to get HTML or PDF
  * Reply with a HTTP response with the result


### Send email (simplified PUT request)

Possible parameters:
- format - format of attachment file
- template - jinja template for attachment
- to - receiver [can be more than one]
- cc - copy [can be more than one]
- bcc- blind copy [can be more than one]
- subject - subject of the email. (Will be replaced by subject from Jinja template if there's any.)
- attachments - array of attachments.

The structure of attachments is:
- format - format of attachment file.
- params - Pramaters used wile rendering jinja templates.
- template - jinja template for attachment.

example:
```
      {
            "template":"test.md",
            "params":{
               "order_id":123,
               "order_creation_date":"2020-01-01 14:14:52",
               "company_name":"Test Company",
               "city":"Mumbai",
               "state":"MH"
            },       
            "format":"html"
        }
```
JSON body must contain `parameters` section to render data into `template`. and `body_parameters` section to render data into `body_template`.


*example*

```
localhost:8080/send_mail
```

body:

```
{
   "to":["Tony.Montana@teskalabs.com"],
   "subject":"Alert-Report",
   "from":"info@info.com",
   "body":{
      "template":"test.md",
      "params":{
         "order_id":123,
         "order_creation_date":"2020-01-01 14:14:52",
         "company_name":"Test Company",
         "city":"Mumbai",
         "state":"MH"
      }
   },
    "attachments":[
        {
            "template":"test.md",
            "params":{
               "order_id":123,
               "order_creation_date":"2020-01-01 14:14:52",
               "company_name":"Test Company",
               "city":"Mumbai",
               "state":"MH"
            },       
            "format":"html"
        }
      ]
   }

```

### Render a report

**PUT**

## Rendering Service
Renders templates into output files of format pdf or html. Provide Jinja templates in local Filesystem or in Zookeeper. 

Use `<title>` tag in HTML templates or `SUBJECT:` keyword as the first line of Markdown templates to paste email *subject* into Jinja templates.

Output format to render is determined using query param 'format' and path of the templte used for rendering html files  
is found usinf query param 'template'.

*Configuration example:*
```
[iris]
templates=/templates
```
```

## MarkdowntoHTML Service
Implements Markdown templates  
*Configuration example:*
```
[markdown]
markdown_path=templates
```

*example*
```
localhost:8080/render?format=pdf&template=test.md
```

*body*
```
{
        "order_id":123,
        "order_creation_date":"2020-01-01 14:14:52",
        "company_name":"Test Company",
        "city":"Mumbai",
        "state":"MH"
}

## Notifications Service
Awaits alert from Kafka and pastes the incoming data into Jinja templates (HTML and Markdown supported).

Depends on Rendering Service and Email Service.



### Kafka
#### Notifications format

Notifications are collected from Kafka topic. Events must respect required JSON schemas:  
*E-mail notifications:*
```
{
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "to": {"type": "string"},
        "template": {"type": "string"},
        "alert": {"type": "object"},
        "event": {"type": "object"}
    },
    "required": ["type", "to", "template", "alert", "event"],
}
```
and "type" == "mail"

*Slack notifications:*
```
{
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "template": {"type": "string"},
        "alert": {"type": "object"},
        "event": {"type": "object"}
    },
    "required": ["type", "template", "alert", "event"],
}
```
and "type" == "slack"

#### Kafka connection
To configure kafka connection, add `[kafka]` section into configuration.  
*Example:*
```
[kafka]
topic=your_topic
group_id=your_id
bootstrap_servers=kafka-1,kafka-2,kafka-3
```

### Slack
Slack notifications are sent through webhook. 
To get webhook url:
- Go to: https://api.slack.com/ 
- Hit "Create an app" (https://api.slack.com/apps?new_app=1)
- Enter asab-print as app name and create app from scratch. 
- Choose "Incoming Webhooks" feature
- Activate Incoming Webhooks
- Add New Webhook to Workspace
- Choose channel
- Copy webhook and paste it into `slack` configuration section

*Configuration example:*
```
[slack]
webhook_url=https://hooks.slack.com/services/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
```
