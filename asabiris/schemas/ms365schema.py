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
          "default": "/Templates/M365/alert.md"
        },
        "params": {
          "type": "object",
          "default": {}
        }
      }
    },
    "attachments": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "template": {
            "type": "string"
          },
          "base64": {
            "type": "string"
          },
          "params": {
            "type": "object",
            "default": {}
          },
          "format": {
            "type": "string",
            "default": "html"
          }
        }
      }
    }
  }
}
