import logging

import asab
from ..errors import ASABIrisError, ErrorCode

L = logging.getLogger(__name__)


class SendPushOrchestrator(object):

	def __init__(self, app):
		self.App = app
		self.JinjaService = app.get_service("JinjaService")
		self.PushOutput = app.get_service("PushOutputService")

	async def send_push(self, push_dict):
		"""
		Expected structure:
		{
			"type": "push",                 # (Kafka) optional in API path
			"topic": "send_ph",             # optional if [push] default_topic is set
			"body": {
				"template": "/Templates/Push/alert.txt",
				"params": { ... }           # Jinja2 params; may include title/priority/tags/click
			},
			"tenant": "pharma-dev"          # optional
		}
		"""
		# 0) Sanity checks on services
		if self.JinjaService is None:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="JinjaService not available.",
				error_i18n_key="Template engine is not initialized."
			)
		if self.PushOutput is None:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="PushOutputService not available.",
				error_i18n_key="Push service is not configured."
			)

		try:
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

			params = body.get("params", {}) or {}

			# 1) Render
			rendered = await self.JinjaService.format(template, params)
			if rendered is None:
				rendered = ""
			rendered = str(rendered).strip()
			if len(rendered) == 0:
				raise ASABIrisError(
					ErrorCode.RENDERING_ERROR,
					tech_message="Rendered push body is empty.",
					error_i18n_key="Rendered push body is empty."
				)

			# 2) Optional: support TITLE: header in the template (like email SUBJECT:)
			title = params.get("title")
			if title is None and rendered.upper().startswith("TITLE:"):
				parts = rendered.split("\n", 1)
				extracted = parts[0].split(":", 1)[1].strip() if len(parts) > 0 else ""
				if extracted:
					body.setdefault("params", {})
					body["params"]["title"] = extracted
				rendered = parts[1].strip() if len(parts) > 1 else ""

			# 3) Attach rendered content and pass through
			push_dict["rendered_message"] = rendered
			push_dict["body"] = body

			# 4) Delegate to output
			res = await self.PushOutput.send(push_dict, push_dict.get("tenant"))
			L.log(asab.LOG_NOTICE, "Push sent successfully via ntfy.")
			return res

		except ASABIrisError:
			raise
		except Exception as e:
			L.exception("Unhandled error in SendPushOrchestrator.send_push: {}".format(e))
			raise ASABIrisError(
				ErrorCode.SERVER_ERROR,
				tech_message="Unhandled error in push orchestrator: {}".format(e),
				error_i18n_key="Push notification failed.",
				error_dict={"error_message": "{}".format(e)}
			)
