mattermost_schema = {
	"type": "object",
	"properties": {
		"channel_id": {
			"type": "string",
		},
		"username": {
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
				"props": {
					"type": "object",
					"default": {}
				},
			},
			"required": ["template"],
		},
	},
	"required": ["body"],
}
