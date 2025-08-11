sms_schema = {
    "type": "object",
    "properties": {
        "phone": {
            "type": "string",
        },
        "body": {
            "type": "object",
            "properties": {
                "template": {
                    "type": "string",
                },
                "params": {
                    "type": "object",
                    "default": {}
                },
            },
            "required": ["template"],
        },
    },
    "required": ["body"],
}
