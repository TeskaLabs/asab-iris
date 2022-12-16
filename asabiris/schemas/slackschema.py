slack_schema ={
		"type": "object",
		"properties": {
			"type": {"type": "string"},
			"body": {
				"type": "object",
				"properties": {
					"template": {"type": "string"},
					"params": {"type": "object"},
				}},
		},
		"required": ["type", "body"],
	}
