import logging

import fastjsonschema

from ..errors import ASABIrisError, ErrorCode
from ..formatter.jinja.service import construct_context
from ..schemas.mattermostschema import mattermost_schema

L = logging.getLogger(__name__)


class SendMattermostOrchestrator(object):

	ValidationSchemaMattermost = fastjsonschema.compile(mattermost_schema)

	def __init__(self, app):
		self.JinjaService = app.get_service("JinjaService")
		self.MattermostOutputService = app.get_service("MattermostOutputService")

	async def send_to_mattermost(self, msg):
		try:
			SendMattermostOrchestrator.ValidationSchemaMattermost(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning("Invalid Mattermost notification format: {}".format(e))
			return

		body = msg["body"]
		template = body["template"]
		if not template.startswith("/Templates/Mattermost/"):
			raise ASABIrisError(
				ErrorCode.INVALID_PATH,
				tech_message="Incorrect template path '{}'. Move templates to '/Templates/Mattermost/'.".format(template),
				error_i18n_key="Incorrect template path '{{incorrect_path}}'. Please move your templates to '/Templates/Mattermost/'.",
				error_dict={
					"incorrect_path": template,
				}
			)

		params = body.get("params", {}) or {}
		message = await self.JinjaService.format(template, params)
		payload = {"message": message}

		props = body.get("props")
		if props:
			context = construct_context(dict(), getattr(self.JinjaService, "Variables", {}), params)
			payload["props"] = self._render_props(props, context)

		await self.MattermostOutputService.send(
			payload,
			channel_id=msg.get("channel_id"),
			username=msg.get("username"),
		)

	def _render_props(self, value, context):
		if isinstance(value, dict):
			return {
				key: self._render_props(item, context)
				for key, item in value.items()
			}

		if isinstance(value, list):
			return [self._render_props(item, context) for item in value]

		if isinstance(value, str):
			template = self.JinjaService.Environment.from_string(value)
			return template.render(context)

		return value
