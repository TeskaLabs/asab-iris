import logging
from ..errors import ASABIrisError, ErrorCode

L = logging.getLogger(__name__)


class SendPushOrchestrator(object):

	def __init__(self, app):
		self.JinjaService = app.get_service("JinjaService")
		self.PushOutput = app.get_service("PushOutputService")

	async def send_push(self, push_dict):
		"""
		Expected structure:
		{
			"topic": "send_ph",            # optional if default_topic is set in config
			"body": {
				"template": "/Templates/Push/alert.txt",
				"params": { ... }           # Jinja2 params; may include title/priority/tags/click
			},
			"tenant": "pharma-dev"          # optional
		}
		"""
		body = push_dict.get("body", {})
		template = body.get("template")
		if not template:
			raise ASABIrisError(
				ErrorCode.INVALID_FORMAT,
				tech_message="Missing 'body.template' in request.",
				error_i18n_key="Invalid input: {{error_message}}.",
				error_dict={"error_message": "Missing 'body.template'."}
			)

		if not template.startswith("/Templates/Push/"):
			raise ASABIrisError(
				ErrorCode.INVALID_PATH,
				tech_message="Incorrect template path '{}'. Move templates to '/Templates/Push/'.".format(template),
				error_i18n_key="Incorrect template path '{{incorrect_path}}'. Please move your templates to '/Templates/Push/'.",
				error_dict={"incorrect_path": template}
			)

		params = body.get("params", {})
		rendered_message = await self.JinjaService.format(template, params)

		# Pass through along with rendered content
		push_dict["rendered_message"] = rendered_message
		return await self.PushOutput.send(push_dict, push_dict.get("tenant"))
