teams_schema = {
	"type": "object",
	"properties": {
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
