import logging
import fastjsonschema

from ..schemas import slack_schema

L = logging.getLogger(__name__)


#


class SendSlackOrchestrator(object):

	ValidationSchemaSlack = fastjsonschema.compile(slack_schema)


	def __init__(self, app):
		# formatters
		self.JinjaService = app.get_service("JinjaService")
		# output
		self.SlackOutputService = app.get_service("SlackOutputService")


	async def send_to_slack(self, msg):
		try:
			SendSlackOrchestrator.ValidationSchemaSlack(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning("Invalid notification format: {}".format(e))
			return
		# setup o/p variable
		output = None
		body = msg['body']
		params = body.get("params", {})
		template = body.get("template", None)

		if template is not None:
			output = await self.JinjaService.format(body['template'], params)
		else:
			L.warning("Sending to slack failed. Reason: Template name not provided.")

		await self.SlackOutputService.send(output)
