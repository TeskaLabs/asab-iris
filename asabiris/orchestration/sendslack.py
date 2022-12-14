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

		body = msg['body']
		# if params no provided pass empty params
		body["params"] = body.get("params", {})

		output = await self.JinjaService.format(body["template"], body["params"])

		await self.SlackOutputService.send(output)
