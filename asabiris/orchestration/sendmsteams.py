import logging
import fastjsonschema

from ..schemas import slack_schema

from ..utils import handle_exceptions
from ..exceptions import PathError
from ..exception_manager import ExceptionManager

L = logging.getLogger(__name__)


class SendMSTeamsOrchestrator(object):

	ValidationSchemaMSTeams = fastjsonschema.compile(slack_schema)

	"""
	A class for sending messages to MS Teams.

	Args:
		app (object): The application object.

	Attributes:
		JinjaService (object): The JinjaService object.
		MSTeamsOutputService (object): The MSTeamsOutputService object.
	"""

	def __init__(self, app, exception_handler: ExceptionManager):
		self.JinjaService = app.get_service("JinjaService")
		self.MSTeamsOutputService = app.get_service("MSTeamsOutputService")

		# Our Exception manager
		self.ExceptionHandler = exception_handler

	@handle_exceptions("ExceptionHandler")
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
		try:
			SendMSTeamsOrchestrator.ValidationSchemaMSTeams(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning("Invalid notification format: {}".format(e))
			return

		body = msg['body']
		template = body["template"]

		if not template.startswith("/Templates/MSTeams/"):
			raise PathError(use_case='MSTeams', invalid_path=template)

		params = body.get("params", {})
		output = await self.JinjaService.format(template, params)

		return await self.MSTeamsOutputService.send(output)
