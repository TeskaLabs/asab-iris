import logging
import fastjsonschema

from ..schemas import teams_schema
from ..errors import ASABIrisError, ErrorCode

L = logging.getLogger(__name__)


class SendMSTeamsOrchestrator(object):

	ValidationSchemaMSTeams = fastjsonschema.compile(teams_schema)

	"""
	A class for sending messages to MS Teams.

	Args:
		app (object): The application object.

	Attributes:
		JinjaService (object): The JinjaService object.
		MSTeamsOutputService (object): The MSTeamsOutputService object.
	"""

	def __init__(self, app):
		self.JinjaService = app.get_service("JinjaService")
		self.MSTeamsOutputService = app.get_service("MSTeamsOutputService")


	async def send_to_msteams(self, msg):
		"""
		Sends a message to MS Teams.

		Args:
			msg (dict): A dictionary containing the message details.

		Raises:
			PathError: If the template path is invalid.

		Returns:
			None
		"""
		prepared = await self.prepare_msteams(msg)
		if prepared is None:
			return
		return await self.send_prepared_msteams(prepared)

	async def prepare_msteams(self, msg):
		try:
			SendMSTeamsOrchestrator.ValidationSchemaMSTeams(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning(
				"Microsoft Teams notification request failed schema validation; fix the request payload structure.",
				struct_data={"validation_error": str(e)},
			)
			return

		body = msg['body']
		template = body["template"]

		if not template.startswith("/Templates/MSTeams/"):
			raise ASABIrisError(
				ErrorCode.INVALID_PATH,
				tech_message="Incorrect template path '{}'. Move templates to '/Templates/MSTeams/'.".format(template),
				error_i18n_key="Incorrect template path '{{incorrect_path}}'. Please move your templates to '/Templates/MSTeams/'.",
				error_dict={
					"incorrect_path": template,
				}
			)

		params = body.get("params", {})
		output = await self.JinjaService.format(template, params)

		return {"tenant": msg.get("tenant"), "body": output}

	async def send_prepared_msteams(self, prepared):
		return await self.MSTeamsOutputService.send(prepared["body"])
