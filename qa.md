# Tests

## Instructions

1) Configure proper SMTP server for a test
2) Replace `foo@example.com` by the valid email address that you have access into

## TSM001A: Send an email using Markdown template(Subject should be taken from md file)

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/Email/message.md",
         "params":{
            "name":"Iris"
      }
    }
}
```

## TSM001B: Send an email using Markdown template(Subject should be taken from md file) with html wrapper

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/Email/message.md",
        "wrapper": "/Templates/Email/Markdown wrapper.html",
         "params":{
            "name":"Iris"
      }
    }
}
```

## TSM001C: Send an email using Markdown template with html wrapper from incorrect path.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/Email/message.md",
        "wrapper": "/Templates/Emails/Markdown wrapper.html",
         "params":{
            "name":"Iris"
      }
    }
}
```

## TSM001D: Send an email using Markdown template with html wrapper from a template that does not exist.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/Emails/message.md",
        "wrapper": "/Templates/Email/Markdown wrapper.md",
         "params":{
            "name":"Iris"
      }
    }
}
```

## TSM001E: Send an email using Markdown template from a template that uses now from template global.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/Email/render_now_variable.md",
         "params":{
            "name":"Iris",
            "tenant":"Default",
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
        "template": "/Templates/Email/message.html",
         "params":{
            "name":"Iris"
      }
    }
}
```

## TSM003: Send an email using md template and base-64 attachment.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/Email/message.md",
        "params":{
          "name":"Iris"
      }
    },
    "attachments": [{
        "base64": "TixOLEEsQSxBLE4sTkI=",
        "content-type": "text/csv",
        "filename": "c7fbbb3d716d4d7c95d3b887b288ed62.csv"
    }]
}
```

## TSM004: Try to send an email with base64 attachment.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/Email/message.html",
        "params":{
          "name":"Iris"
      }
    },
    "attachments": [{
        "base64": "TixOLEEsQSxBLE4sTkI=",
        "content-type": "text/csv",
        "filename": "c7fbbb3d716d4d7c95d3b887b288ed62.csv"
    }]
}
```


## TSM005: Email with multiple To, CC and BCC with html as template.

`PUT /send_mail`

```
{
    "to": ["foo1@example.com", "foo2@example.com"],
    "cc": ["foo3@example.com", "foo4@example.com"],
    "bcc": ["foo5@example.com", "foo6@example.com"],
    "body": {
        "template": "/Templates/Email/message.html",
         "params":{
            "name":"Iris"
      }
    }
}
```

## TSM006: Try to send an email with '.md' template as body and attachment(pdf) format.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",
            "params":{
                "name":"Iris"
            },       
            "format":"pdf"
        }
      ]
   }

```



## TSM007: Try to send an email with '.html' template as body and attachment.(Format=pdf)

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/message.html",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",     
            "format":"pdf"
        }
      ]
}
```


## TSM008A: Try to send an email with '.md' template as body and attachment in both html and pdf formats.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",     
            "format":"html"
        },
         {
            "template":"/Templates/Attachment/attachment.md",     
            "format":"pdf"
        }
      ]
   }
```

## TSM008B: Try to send an email with '.md' template as body and three attachment(pdf-pdf-md).

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",     
            "format":"pdf"
        },
         {
            "template":"/Templates/Attachment/attachment.md",    
            "format":"pdf"
        },
         {
            "template": "/Templates/Attachment/attachment.md",
            "format": "md"
      }
      ]
   }
```

## TSM008C: Try to send an email with '.md' template as body and attachment (pdf-pdf).

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",    
            "format":"pdf"
        },
         {
            "template":"/Templates/Attachment/attachment.md", 
            "format":"pdf"
        }
      ]
   }
```

## TSM009A: Try to send an email with '.md' template as body and attachment (html-pdf)formats.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/message.html",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",       
            "format":"html"
        },
         {
            "template":"/Templates/Attachment/attachment.md",
            "format":"pdf"
        }
      ]
   }
```

## TSM009B: Try to send an email with '.html' template as body and attachment (pdf-html)formats.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/message.html",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",    
            "format":"pdf"
        },
         {
            "template":"/Templates/Attachment/attachment.md", 
            "format":"pdf"
        }
      ]
   }
```

## TSM009C: Try to send an email with '.html' template as body and attachment(html-html) format.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/message.html",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",    
            "format":"html"
        },
         {
            "template":"/Templates/Attachment/attachment.md",     
            "format":"html"
        }
      ]
   }
```


## TSM010A: Try to send an email with base64 attachment.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/Email/message.html",
        "params":{
           "name":"Iris"
        }
    },
    "attachments": [{
        "base64": "TixOLEEsQSxBLE4sTkI=",
        "content-type": "text/csv",
        "filename": "testfile.csv"
    }]
}
```

## TSM010B: Try to send an email with base64 attachment.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"BASE64-BASE64",
    "body": {
        "template": "/Templates/Email/message.md",
        "params":{
          "name":"Iris"
      }
    },
    "attachments": [{
        "base64": "TixOLEEsQSxBLE4sTkI=",
        "content-type": "text/csv",
        "filename": "File1.csv"
    },
    {
        "base64": "TixOLEEsQSxBLE4sTkI=",
        "content-type": "text/csv",
        "filename": "file2.csv"
    }

    ]
}

```

## TSM010C: Try to send an email with base64 attachment and a PDF attachment.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"BASE64-PDF",
    "body": {
        "template": "/Templates/Email/message.md",
        "params":{
          "name":"Iris"
      }
    },
    "attachments": [{
        "base64": "TixOLEEsQSxBLE4sTkI=",
        "content-type": "text/csv",
        "filename": "File1.csv"
    },
    {
        "template":"/Templates/Attachment/attachment.md",      
        "format":"pdf"
    }

    ]
}

```

## TSM010D: Try to send an email with html as body template and base64 attachment and an HTML attachment.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"BASE64-HTML",
    "body": {
        "template": "/Templates/Email/message.html",
        "params":{
          "name":"Iris"
      }
    },
    "attachments": [{
        "base64": "TixOLEEsQSxBLE4sTkI=",
        "content-type": "text/csv",
        "filename": "File1.csv"
    },
    {
        "template":"/Templates/Attachment/attachment.md",      
        "format":"html"
    }

    ]
}
```

## TSM010E: Try to send an email with html as body template and base64 attachment and an PDF attachment.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "body":{
      "template":"/Templates/Email/message.html",
      "params":{
         "name":"Iris"
      },
    "attachments": [{
        "base64": "TixOLEEsQSxBLE4sTkI=",
        "content-type": "text/csv",
        "filename": "testfile1.csv"
    },
    {
        "template":"/Templates/Attachment/attachment.md",    
         "format":"pdf"
        }]
}
```

## TSM011A: Try to send an email with '.md' template as body and attachment in both html and pdf formats.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"md-md",
     "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",     
            "format":"md"
        },
         {
            "template":"/Templates/Attachment/attachment.md",     
            "format":"md"
        }
      ]
   }
```

## TSM011B: Try to send an email with '.md' template as body and attachment (md-md-pdf) formats.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",     
            "format":"md"
        },
         {
            "template":"/Templates/Attachment/attachment.md",    
            "format":"md"
        },
         {
            "template": "/Templates/Attachment/attachment.md",
            "format": "pdf"
      },
      ]
   }
```

## TSM011C: Try to send an email with '.md' template as body and attachment (md-md-html) formats.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",     
            "format":"md"
        },
         {
            "template":"/Templates/Attachment/attachment.md",    
            "format":"md"
        },
         {
            "template": "/Templates/Attachment/attachment.md",
            "format": "html"
      },
      ]
   }
```

## TSM011D: Try to send an email with '.md' template as body and attachment (md-html-html) formats.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",     
            "format":"md"
        },
         {
            "template":"/Templates/Attachment/attachment.md",    
            "format":"html"
        },
         {
            "template": "/Templates/Attachment/attachment.md",
            "format": "html"
      },
      ]
   }
```

## TSM011E: Try to send an email with '.md' template as body and attachment (md-pdf-pdf) formats.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",     
            "format":"md"
        },
         {
            "template":"/Templates/Attachment/attachment.md",    
            "format":"pdf"
        },
         {
            "template": "/Templates/Attachment/attachment.md",
            "format": "pdf"
      },
      ]
   }
```

## TSM011F: Try to send an email with '.md' template as body and attachment (html-html-md-md) formats with filename.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "subject":"Alert-Report-Test",
    "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "message":"I am testing a template",
         "event":"Iris-Event"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",
            "format":"html"
        },
         {
            "template":"/Templates/Attachment/attachment.md",    
            "format":"html"
        },
        {
            "template":"/Templates/Attachment/attachment.md",
            "format":"md"
        },
        {
            "template":"/Templates/Attachment/attachment.md", 
            "format":"md"
        }
      ]
}
```


## TSM011G: Try to send an email with '.md' template as body and attachment (html-html-md-md) formats without filename.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "subject":"Alert-Report-Test",
    "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "message":"I am testing a template",
         "event":"Iris-Event"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",
            "format":"html"
        },
         {
            "template":"/Templates/Attachment/attachment.md",    
            "format":"html"
        },
        {
            "template":"/Templates/Attachment/attachment.md",
            "format":"md"
        },
        {
            "template":"/Templates/Attachment/attachment.md",
            "format":"md"
        }
      ]
}
```

## TSM011G: Try to send an email with '.md' template as body and attachment (html-html-md-md) formats without filename.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "subject":"Alert-Report-Test",
    "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "message":"I am testing a template",
         "event":"Iris-Event"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",
            "format":"html"
        },
         {
            "template":"/Templates/Attachment/attachment.md",    
            "format":"html"
        },
        {
            "template":"/Templates/Attachment/attachment.md",
            "format":"md"
        },
        {
            "template":"/Templates/Attachment/attachment.md",
            "format":"md"
        }
      ]
}
```

## TSM011G: Try to send an email with '.md' template as body and attachment (html-html-md-md-pdf-pdf) formats without filename.

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "subject":"Alert-Report-Test",
    "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "message":"I am testing a template",
         "event":"Iris-Event"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",
            "format":"html"
        },
         {
            "template":"/Templates/Attachment/attachment.md",    
            "format":"html"
        },
        {
            "template":"/Templates/Attachment/attachment.md",
            "format":"md"
        },
        {
            "template":"/Templates/Attachment/attachment.md",
            "format":"md"
        },
        {
            "template":"/Templates/Attachment/attachment.md",
            "format":"pdf"
        },
        {
            "template":"/Templates/Attachment/attachment.md",
            "format":"pdf"
        }
      ]
}
```


## TSM011: Try to send an email with template as body and an attachment html file "NOT-FOUND".

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/MISSING.html",   
            "format":"pdf"
        }
      ]
}

```

## TSM012: Try to send an email with template as body and accessing attachment that does not exist".

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
     "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Emails/message.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachments/MISSING.html",       
            "format":"pdf"
        }
      ]
}

```

## TSM013: Try to send an email with message.md as body and accessing template from wrong location.
    

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/MISSING.html",      
            "format":"pdf"
        }
      ]
}
```

## TSM014: Try to send an email with template as body and a docx attachment.
    

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "subject":"Alert-Report-Test",
     "body":{
      "template":"/Templates/Email/message.md",
      "params":{
         "name":"Iris"
      }
   },
    "attachments":[
        {
            "template":"/Templates/Attachment/attachment.md",
            "params":{
                "name":"Iris"
            },       
            "format":"docx"
        }
      ]
}
```

## TSM015: Try to send an email with missing template

`PUT /send_mail`

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "/Templates/MISSING.html"
    }
}
```

## TSM0016: Try to send an email with no template

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
    "uuid": "a59e48ca-3980-4394-9323-8c7e174fe55a"
}

```

## TSM017: Try to render PDF report using html template

`PUT /render?format=html&template=/Templates/General/hello.html`

```
{
    "name": "Iris"
}
```

## TSM018: Try to render PDF report using html template

`PUT /render?format=pdf&template=/Templates/General/hello.html`

```
{
    "name": "Iris"
}
```

## TSM019: Try to render PDF report using markdown template

`PUT /render?format=pdf&template=/Templates/General/hello.md`

```
{
    "name": "Iris"
}
```

## TSM020: Try to render PDF report using html template

`PUT /render?format=html&template=/Templates/General/hello.md`

```
{
    "name": "Iris"
}
```

## TSM021: Try to render PDF using missing template

`PUT /render?format=pdf&template=/Templates/MISSING.html`

```
{}

EXPECTED RESPONSE:

{
    "result": "NOT-FOUND",
    "message": "The entered path '/Templates/MISSING.html' is not correct. Please move your files to '/Templates/General/'.",
    "uuid": "518ab833-1f1a-4711-952d-dcd78bc272a8"
}
```

## TSM022: Try to render HTML using missing template

`PUT /render?format=html&template=/Templates/MISSING.html`

```

{}

EXPECTED RESPONSE:

{
    "result": "NOT-FOUND",
    "message": "The entered path '/Templates/MISSING.html' is not correct. Please move your files to '/Templates/General/'.",
    "uuid": "518ab833-1f1a-4711-952d-dcd78bc272a8"
}
```

## TSM023: Try to render HTML using missing template

`PUT /render?format=docx&template=/Templates/General/hello.md`

```

{}

EXPECTED RESPONSE:

{
    "result": "ERROR",
    "message": "Invalid/unknown conversion format: 'docx'",
    "uuid": "8c417770-d931-4397-985b-1e8a5710d1c6"
}
```

## TSM024:A Try to send Slack message using markdown template

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/Slack/message.md",
      "params":{
         "message":"I am testing a template",
         "event":"Iris-Event"
      }
   }
}
```

## TSM024B: Try to send Slack message using plain-text template

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/Slack/message.txt",
      "params":{
         "message":"I am testing a template"
      }
   }
}
```

## TSM024C: Try to send Slack message using plain-text template

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/Slack/message.html",
      "params":{
         "message":"I am testing a template"
      }
   }
}
```


## TSM025: Try to send Slack message using a template from incorrect location.

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/MISSING.md",
      "params":{
         "message":"I am testing a template"
      }
   }
}

EXPECTED RESPONSE:

{
    "result": "NOT-FOUND",
    "message": "The entered path '/Templates/MISSING.md' is not correct. Please move your files to '/Templates/Slack/'.",
    "uuid": "168196bc-eace-4b5c-b8e6-747dd224454c"
}
```

## TSM025B: Try to send Slack message using a template from template that does not exist.

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/Slack/MISSING.md",
      "params":{
         "message":"I am testing a template"
      }
   }
}

EXPECTED RESPONSE:

{
    "result": "NOT-FOUND",
    "message": "Template '/Templates/Slack/MISSING.md' not found",
    "uuid": "12a9e888-30e5-45e9-a832-494fabe11f4d"
}
```


## TSM026: Try to send Slack with attachment

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/Slack/message.md",
      "params":{
         "message":"I am testing a template"
      }
   },
   "attachments":[
      {
         "base64":"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",
         "content-type":"image/jpeg",
         "filename":"kiwi.jpeg"
      }
   ]
}

EXPECTED RESPONSE:

{
    "result": "OK"
}
```

## TSM027: Try to send Slack with two base64 attachment

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/Slack/message.md",
      "params":{
         "message":"I am testing a template"
      }
   },
   "attachments":[
      {
         "base64":"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",
         "content-type":"image/jpeg",
         "filename":"kiwi.jpeg"
      },
       {
         "base64":"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",
         "content-type":"image/jpeg",
         "filename":"kiwi.jpeg"
      }
   ]
}

EXPECTED RESPONSE:

{
    "result": "OK"
}
```

## TSM027: Try to send Slack with two base64 attachment

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/Slack/message.md",
      "params":{
         "message":"I am testing a md template"
      }
   },
   "attachments":[
      {
         "base64":"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",
         "content-type":"image/jpeg",
         "filename":"kiwi.jpeg"
      },
       {
         "base64":"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",
         "content-type":"image/jpeg",
         "filename":"kiwi.jpeg"
      }
   ]
}

EXPECTED RESPONSE:

{
    "result": "OK"
}
```

## TSM028: Try to send Slack with two (md-md) attachment.

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/Slack/message.md",
      "params":{
         "message":"I am testing a md template"
      }
   },
   "attachments":[
      {
        "template":"/Templates/Attachment/attachment.md",     
        "format":"md"
      },
       {
        "template":"/Templates/Attachment/attachment.md",     
        "format":"md"
      }
   ]
}

EXPECTED RESPONSE:

{
    "result": "OK"
}
```

## TSM029: Try to send Slack with two (md-md) attachment.

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/Slack/message.html",
      "params":{
         "message":"I am testing a md template"
      }
   },
   "attachments":[
      {
        "template":"/Templates/Attachment/attachment.md",     
        "format":"html"
      },
       {
        "template":"/Templates/Attachment/attachment.md",     
        "format":"html"
      }
   ]
}

EXPECTED RESPONSE:

{
    "result": "OK"
}
```

## TSM030: Try to send Slack with two (txt-txt) attachment.

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/Slack/message.txt",
      "params":{
         "message":"I am testing a md template"
      }
   },
   "attachments":[
      {
        "template":"/Templates/Attachment/attachment.md",     
        "format":"txt"
      },
       {
        "template":"/Templates/Attachment/attachment.md",     
        "format":"txt"
      }
   ]
}

EXPECTED RESPONSE:

{
    "result": "ERROR",
    "message": "Unsupported conversion format 'txt'.",
    "uuid": "73e0c27f-c527-474e-834d-a69ddaab4641"
}
```


## TSM031: Try to send Slack with (base64-txt) attachment

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/Slack/message.md",
      "params":{
         "message":"I am testing a template"
      }
   },
   "attachments":[
     {
        "template":"/Templates/Attachment/attachment.md",     
        "format":"txt"
     },
      {
         "base64":"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",
         "content-type":"image/jpeg",
         "filename":"kiwi.jpeg"
     }
   ]
}

EXPECTED RESPONSE:

{
    "result": "OK"
}

```

## TSM031B: Try to send Slack with (txt-base64) attachment

`PUT /send_slack`

```
{
   "body":{
      "template":"/Templates/Slack/message.md",
      "params":{
         "message":"I am testing a template"
      }
   },
   "attachments":[
     {
        "template":"/Templates/Attachment/attachment.md",     
        "format":"txt"
      },
      {
         "base64":"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",
         "content-type":"image/jpeg",
         "filename":"kiwi.jpeg"
      }
   ]
}

EXPECTED RESPONSE:

{
    "result": "OK"
}

```



## TSM032: Try to send MS Teams using markdown template

 `PUT /send_msteams`

 ```
 {
    "body":{
       "template":"/Templates/MSTeams/alert.md",
       "params":{
          "message":"I am testing a template",
          "event":"Iris-Event"
       }
    }
 }
 ```


## TSM033: Kakka handler

 `EMAIL`

 ```
{"type":"email", "to": ["Shivashankar <mithunshivashankar@gmail.com>"], "from": "info@teskalabs.com", "body":{"template":"/Templates/Email/message.md", "params":{"name": "I am testing a template", "error": "None" }}}

{"type":"email", "to": ["Shivashankar <mithunshivashankar@gmail.com>"], "from": "info@teskalabs.com", "body":{"template":"/Templates/Export.md", "params":{"name": "I am testing a template", "error": "None" }}}

'MARKDOWN-WRAPPER'

{"type":"email", "to": ["Shivashankar <mithunshivashankar@gmail.com>"], "from": "info@teskalabs.com", "body":{"template":"/Templates/Email/message.md", "params":{"name": "I am testing a template", "error": "None" }}}

{"type":"email", "to": ["Shivashankar <mithunshivashankar@gmail.com>"], "from": "info@teskalabs.com", "body":{"template":"/Templates/Email/message.md", "wrapper":"/Templates/Wrapper/Markdown wrapper.md",  "params":{"name": "I am testing a template", "error": "None" }}}

{"type": "email", "to": ["Shivashankar <mithunshivashankar@gmail.com>"], "from": "info@teskalabs.com", "body":{"template":"/Templates/Email/message.md", "wrapper":"/Templates/Wrapper/Markdown wrapper.html", "params":{"name": "I am testing a template", "error": "None" }}}

{"type": "email", "to": ["Shivashankar <mithunshivashankar@gmail.com>"], "from": "info@teskalabs.com", "body":{"template":"/Templates/Email/message.md", "wrapper":"/Templates/Wrappers/Markdown wrapper.html", "params":{"name": "I am testing a template", "error": "None" }}}

'Missing from'

{"type":"email", "to": ["Shivashankar <mithunshivashankar@gmail.com>"], "body":{"template":"/Templates/Email/message.md", "params":{"name": "I am testing a template", "error": "None" }}}

'Bad template path'

{"type":"email", "to": ["Shivashankar <mithunshivashankar@gmail.com>"], "body":{"template":"/Templates/Emails/message.md", "params":{"name": "I am testing a template", "error": "None" }}}

'Access non existant template'

{"type":"email", "to": ["Shivashankar <mithunshivashankar@gmail.com>"], "body":{"template":"/Templates/Email/message22.md", "params":{"name": "I am testing a template", "error": "None" }}}
 ```

 `SLACK`

 ```
{"type":"slack", "body":{"template":"/Templates/Slack/Slack example.txt", "params":{"name": "I am testing a template", "error": "None" }}}

{"type":"slack", "body":{"template":"/Templates/Slack/Slack example.txt", "params":{"name": "I am testing a template", "error": "None" }}}

'Bad template path'
{"type":"slack", "body":{"template":"/Templates/SlackS/message.md", "params":{"name": "I am testing a template", "error": "None" }}}

'Access non existant template'
{"type":"slack", "body":{"template":"/Templates/Slack/message.md2", "params":{"name": "I am testing a template", "error": "None" }}}
 ```

 `MSTEAMS`

 ```
{"type":"msteams", "body":{"template":"/Templates/MSTeams/Slack example.txt", "params":{"name": "I am testing a template", "error": "None" }}}

{"type":"msteams", "body":{"template":"/Templates/MSTeams/Slack example.txt", "params":{"name": "I am testing a template", "error": "None" }}}

'Bad template path'
{"type":"msteams", "body":{"template":"/Templates/MSTeamss/message.md", "params":{"name": "I am testing a template", "error": "None" }}}

'Access non existant template'
{"type":"msteams", "body":{"template":"/Templates/MSTeams/message.md2", "params":{"name": "I am testing a template", "error": "None" }}}
 ```


 `UNSUPPORTED-TYPE`

 ```
{"type":"sms", "body":{"template":"/Templates/MSTeams/Slack example.txt", "params":{"name": "I am testing a template", "error": "None" }}}
 ```