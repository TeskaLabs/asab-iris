# Tests

## Instructions

1) Configure proper SMTP server for a test
2) Replace `foo@example.com` by the valid email address that you have access into

## TSM001: Send an email using Markdown template(Subject should be taken from md file)

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/Email/hello.md",
         "params":{
            "name":"Iris"
      }
    }
}
```


## TSM002: Send an email using HTML template

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/Email/hello.html",
         "params":{
            "name":"Iris"
      }
    }
}
```


## TSM003: Email with multiple To, CC and BCC with html as template.

`PUT /send_mail`

```
{
    "to": ["foo1@example.com", "foo2@example.com"],
    "cc": ["foo3@example.com", "foo4@example.com"],
    "bcc": ["foo5@example.com", "foo6@example.com"],
    "body": {
        "template": "/Templates/Email/hello.html",
         "params":{
            "name":"Iris"
      }
    }
}
```

## TSM004: Try to send an email with template as body and attachment(Subject should be taken from md body).

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "body":{
      "template":"/Templates/Email/hello.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Email/hello.md",
            "params":{
                "name":"Iris"
            },       
            "format":"pdf"
        }
      ]
   }

```



## TSM005: Try to send an email with '.html' template as body and attachment.(Format=pdf)

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/hello.html",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Email/hello.md",
            "params":{
                "name":"Iris"
            },       
            "format":"pdf"
        }
      ]
}
```


## TSM006: Try to send an email with '.md' template as body and attachment.(Format=html)

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/hello.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Email/hello.md",
            "params":{
                "name":"Iris"
            },       
            "format":"html"
        }
      ]
}
```

## TSM007: Try to send an email with template as body and a missing html attachment.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/hello.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/MISSING.html",
            "params":{
                "name":"Iris"
            },       
            "format":"pdf"
        }
      ]
}

EXPECTED RESPONSE:

{
    "result": "NOT-FOUND",
    "message": "Invalid path '/Templates/MISSING.html'.",
    "uuid": "c941fe16-470e-42d2-958c-c9fb09ac8e7d"
}
```

## TSM008: Try to send an email with template as body and a missing html attachment.
    

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/hello.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/MISSING.html",
            "params":{
                "name":"Iris"
            },       
            "format":"pdf"
        }
      ]
}

EXPECTED RESPONSE:

{
    "result": "NOT-FOUND",
    "message": "Invalid path '/Templates/MISSING.html'.",
    "uuid": "c941fe16-470e-42d2-958c-c9fb09ac8e7d"
}
```

## TSM009: Try to send an email with template as body and a missing html attachment.
    

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/hello.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/MISSING.html",
            "params":{
                "name":"Iris"
            },       
            "format":"docx"
        }
      ]
}

EXPECTED RESPONSE:

{
    "result": "ERROR",
    "message": "Invalid/unknown conversion format: 'docx'",
    "uuid": "8c417770-d931-4397-985b-1e8a5710d1c6"
}
```

## TSM010: Try to send an email with missing template

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/MISSING.html"
    }
}

EXPECTED RESPONSE:

{
    "result": "NOT-FOUND",
    "message": "Invalid path '/Templates/MISSING.html'.",
    "uuid": "c941fe16-470e-42d2-958c-c9fb09ac8e7d"
}

```

## TSM0011: Try to send an email with no template

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
    }
}

EXPECTED RESPONSE:
{
    "result": "ERROR",
    "message": "400: data.body must contain ['template'] properties",
    "uuid": "0cda7e20-046c-498c-bbea-9361e2b4dd11"
}
```

## TSM012: Try to send an email with base64 attachment.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/Email/hello.html"
    },
    "attachments": [{
        "base64": "TixOLEEsQSxBLE4sTkI=",
        "content-type": "text/csv",
        "filename": "c7fbbb3d716d4d7c95d3b887b288ed62.csv"
    }]
}
```

## TSM013: Try to render PDF report using html template

`PUT /render?format=html&template=/Templates/General/hello.html`

```
{
    "name": "Iris"
}
```

## TSM014: Try to render PDF report using html template

`PUT /render?format=pdf&template=/Templates/General/hello.html`

```
{
    "name": "Iris"
}
```

## TSM015: Try to render PDF report using markdown template

`PUT /render?format=pdf&template=/Templates/General/hello.md`

```
{
    "name": "Iris"
}
```

## TSM016: Try to render PDF report using html template

`PUT /render?format=html&template=/Templates/General/hello.md`

```
{
    "name": "Iris"
}
```

## TSM017: Try to render PDF using missing template

`PUT /render?format=pdf&template=/Templates/MISSING.html`

```
{}

EXPECTED RESPONSE:

{
    "result": "NOT-FOUND",
    "message": "Invalid path '/Templates/MISSING.html'.",
    "uuid": "c941fe16-470e-42d2-958c-c9fb09ac8e7d"
}
```

## TSM018: Try to render HTML using missing template

`PUT /render?format=html&template=/Templates/MISSING.html`

```

{}

EXPECTED RESPONSE:

{
    "result": "NOT-FOUND",
    "message": "Invalid path '/Templates/MISSING.html'.",
    "uuid": "c941fe16-470e-42d2-958c-c9fb09ac8e7d"
}
```

## TSM019: Try to render HTML using missing template

`PUT /render?format=docx&template=/Templates/MISSING.html`

```

{}

EXPECTED RESPONSE:

{
    "result": "ERROR",
    "message": "Invalid/unknown conversion format: 'docx'",
    "uuid": "8c417770-d931-4397-985b-1e8a5710d1c6"
}
```

## TSM020: Try to send Slack message using markdown template

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/Slack/alert.md",
      "params":{
         "message":"I am testing a template",
         "event":"Iris-Event"
      }
   }
}
```

## TSM021: Try to send Slack message using missing template

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/MISSING.md",
      "params":{
         "message":"I am testing a template",
         "event":"Iris-Event"
      }
   }
}

EXPECTED RESPONSE:

{
    "result": "NOT-FOUND",
    "message": "Invalid path '/Templates/MISSING.md'.",
    "uuid": "c941fe16-470e-42d2-958c-c9fb09ac8e7d"
}
```