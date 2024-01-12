import logging
import fastjsonschema

from ..schemas import slack_schema

from ..exceptions import PathError, Jinja2TemplateSyntaxError, Jinja2TemplateUndefinedError
from ..exception_strategy import ExceptionStrategy

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

	def __init__(self, app):
		self.JinjaService = app.get_service("JinjaService")
		self.MSTeamsOutputService = app.get_service("MSTeamsOutputService")

		# Our Exception manager
		self.ExceptionStrategy = None


	async def send_to_msteams(self, msg, exception_strategy=None):
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
			self.ExceptionStrategy = exception_strategy
			SendMSTeamsOrchestrator.ValidationSchemaMSTeams(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning("Invalid notification format: {}".format(e))
			return
		try:
			body = msg['body']
			template = body["template"]

			if not template.startswith("/Templates/MSTeams/"):
				raise PathError(use_case='MSTeams', invalid_path=template)

			params = body.get("params", {})
			output = await self.JinjaService.format(template, params)

			return await self.MSTeamsOutputService.send(output)
		except Jinja2TemplateSyntaxError as e:
			await self._handle_exception(e)
		except Jinja2TemplateUndefinedError as e:
			await self._handle_exception(e)
		except PathError as e:
			await self._handle_exception(e)
		except Exception as e:
			await self._handle_exception(e)


	async def _handle_exception(self, exception):
		await self.ExceptionStrategy.handle_exception(exception)
