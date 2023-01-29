# Tests

## Instructions

1) Configure proper SMTP server for a test
2) Replace `foo@example.com` by the valid email address that you have an access into

## TSM001: Send an email using Markdown template

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "hello.md"
    }
}
```


## TSM002: Send an email using HTML template

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "hello.html"
    }
}
```


## TSM03: Send an email to multiple To, CC and BCC

```
{
    "to": ["foo1@example.com", "foo2@example.com"],
    "cc": ["foo3@example.com", "foo4@example.com"],
    "bcc": ["foo5@example.com", "foo6@example.com"],
    "body": {
        "template": "hello.html"
    }
}
```


## TSM03: Try to send an email with missing template

```
{
    "to": ["foo@example.com"],
    "body": {
        "template": "MISSING.html"
    }
}
```

