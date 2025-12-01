# Minimal schema for push notifications over ntfy.sh
push_schema = {
	"type": "object",
	"required": ["body"],
	"properties": {
		"type": {"const": "push"},
		"topic": {"type": "string"},              # optional; falls back to [push] default_topic
		"tenant": {"type": ["string", "null"]},
		"body": {
			"type": "object",
			"required": ["template"],
			"properties": {
				"template": {
					"type": "string",
					"pattern": r"^/Templates/Push/"
				},
				"params": {"type": "object"}       # title, priority, tags, click, message, time, etc.
			},
			"additionalProperties": True
		}
	},
	"additionalProperties": True
}
