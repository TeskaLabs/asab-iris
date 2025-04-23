ms365_schema = {
  "type": "object",
  "required": [
    "to",
    "body"
  ],
  "properties": {
    "to": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "cc": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "default": []
    },
    "bcc": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "default": []
    },
    "subject": {
      "type": "string"
    },
    "from": {
      "type": "string"
    },
    "tenant": {
      "type": "string",
      "default": ""
    },
    "body": {
      "type": "object",
      "required": [
        "template"
      ],
      "properties": {
        "template": {
          "type": "string",
          "default": "/Templates/MS365/alert.md"
        },
        "params": {
          "type": "object",
          "default": {}
        }
      }
    },
  }
}
