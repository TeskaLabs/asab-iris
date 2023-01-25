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
		# location of slack templates

	async def send_to_slack(self, msg):
		try:
			SendSlackOrchestrator.ValidationSchemaSlack(msg)
		except fastjsonschema.exceptions.JsonSchemaException as e:
			L.warning("Invalid notification format: {}".format(e))
			return

		body = msg['body']
		# if params no provided pass empty params
		# - primarily use absolute path - starts with "/"
		# - if absolute path is used, check it start with "/Templates"
		# - if it is not absolute path, it is file name - assume it's a file in Templates folder
		assert body['template'].startswith("/Templates"), "Your template must be stored in /Templates directory"

		body["params"] = body.get("params", {})
		output = await self.JinjaService.format(body["template"], body["params"])

		await self.SlackOutputService.send(output)
