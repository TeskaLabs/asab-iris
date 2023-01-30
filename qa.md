# Tests

## Instructions

1) Configure proper SMTP server for a test
2) Replace `foo@example.com` by the valid email address that you have access into

## TSM001: Send an email using Markdown template

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/Emails/hello.md"
    }
}
```


## TSM002: Send an email using HTML template

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/Emails/hello.html"
    }
}
```


## TSM03: Send an email to multiple To, CC and BCC.

`PUT /send_mail`

```
{
    "to": ["foo1@example.com", "foo2@example.com"],
    "cc": ["foo3@example.com", "foo4@example.com"],
    "bcc": ["foo5@example.com", "foo6@example.com"],
    "body": {
        "template": "/Templates/Emails/hello.html"
    }
}
```

## TSM04: Try to send an email with template as body and attachment.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "from":"foo1@example.com",
     "body":{
      "template":"/Templates/Emails/hello.md",
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
    "body": {
        "template": "/Templates/MISSING.html"
    }
}
```


## TSM05: Try to send an email with missing template

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/MISSING.html"
    }
}
```


## TSM06: Try to send an email with base64 attachment.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/Emails/hello.html"
    },
    'attachments': [{
        'base64': '',
        'content-type': 'text/csv',
        'filename': 'c7fbbb3d716d4d7c95d3b887b288ed62.csv'
    }]
}
```

## TSM07: Try to render PDF report using html template

`PUT /render?format=pdf&template=/Templates/General/hello.html`

```
{
    "name": "Iris"
}
```

## TSM08: Try to render PDF report using html template

`PUT /render?format=html&template=/Templates/General/hello.html`

```
{
    "name": "Iris"
}
```

## TSM09: Try to render PDF report using markdown template

`PUT /render?format=pdf&template=/Templates/General/hello.md`

```
{
    "name": "Iris"
}
```

## TSM10: Try to render PDF report using html template

`PUT /render?format=html&template=/Templates/General/hello.md`

```
{
    "name": "Iris"
}
```

## TSM11: Try to render PDF using missing template

`PUT /render?format=pdf&template=/Templates/MISSING.html`

```
{}
```

## TSM12: Try to render HTML using missing template

`PUT /render?format=html&template=/Templates/MISSING.html`

```

{}

```

## TSM13: Try to send Slack message using markdown template

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templats/General/hello.md",
      "params":{
         "message":"I am testing a template",
         "event":"Iris-Event",
      }
   }
}
```

## TSM14: Try to send Slack message using missing template

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templats/General/MISSING.md",
      "params":{
         "message":"I am testing a template",
         "event":"Iris-Event",
      }
   }
}
```