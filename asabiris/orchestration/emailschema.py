email_schema = {
	"type": "object",
	"required": [
		"to",
		"body"
	],
	"properties": {
		"to": {
			"type": "array",
			"items": {
				"type": "string",
			},
		},
		"cc": {
			"type": "array",
			"items": {
				"type": "string",
			},
			"default": [],
		},
		"bcc": {
			"type": "array",
			"items": {
				"type": "string",
			},
			"default": [],
		},
		"subject": {
			"type": "string",
		},
		"from": {
			"type": "string",
		},
		"body": {
			"type": "object",
			"required": [
				"template"
			],
			"properties": {
				"template": {
					"type": "string",
					"default": "hello.md",
				},
				"params": {
					"type": "object",
					"default": {},
				}
			},
		},
		"attachments": {
			"type": "array",
			"items": {
				"type": "object",
				"required": [
					"template",
					"format"
				],
				"properties": {
					"template": {
						"type": "string",
					},
					"params": {
						"type": "object",
						"default": {},
					},
					"format": {
						"type": "string",
						"default": "html",
					}
				},
			},
		}
	},
}
