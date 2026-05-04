import logging

import fastjsonschema

from ..errors import ASABIrisError, ErrorCode
from ..formatter.jinja.service import construct_context
from ..schemas.mattermostschema import mattermost_schema

L = logging.getLogger(__name__)


class SendMattermostOrchestrator(object):
	"""
	Render Mattermost templates and route the resulting payload to the output service.

	This orchestrator validates the inbound IRIS message shape, enforces the
	`/Templates/Mattermost/` template location, renders the main message body with
	Jinja, optionally renders structured `props`, and then delegates delivery to
	`MattermostOutputService`.
	"""

	ValidationSchemaMattermost = fastjsonschema.compile(mattermost_schema)

	def __init__(self, app):
		self.JinjaService = app.get_service("JinjaService")
		self.MattermostOutputService = app.get_service("MattermostOutputService")

	async def send_to_mattermost(self, msg):
		"""
		Send a Mattermost notification described by an IRIS message.

		Expected structure:
		{
			"channel_id": "optional-channel-id",
			"username": "optional-target-username-for-dm",
			"body": {
				"template": "/Templates/Mattermost/message.md",
				"params": {...},
				"props": {...}
			}
		}

		Args:
			msg: IRIS notification payload.

		Raises:
			ASABIrisError: When the template path is invalid or when downstream
				Mattermost delivery fails.
		"""
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
		"""
		Recursively render string values inside Mattermost `props`.

		This allows callers to provide structured attachments/metadata with Jinja
		expressions while preserving lists, dictionaries, and non-string scalar
		values.

		Args:
			value: A nested props structure or scalar value.
			context: Render context prepared from global variables and message params.

		Returns:
			The same structure with all string leaves rendered through Jinja.
		"""
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
