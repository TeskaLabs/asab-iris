unified = {
	"type": "object",
	"required": ["destination", "body"],
	"properties": {
		"destination": {
			"type": "array",
			"minItems": 1,
			"items": {
				"type": "object",
				"required": ["type"],
				"properties": {
					"type": {"type": "string"},
					"value": {},
				},
			},
		},
		"body": {"type": "object"},
		"template": {
			"type": "object",
			"properties": {
				"template": {"type": "string"},
				"wrapper": {"type": "string"},
			},
		},
	},
}
