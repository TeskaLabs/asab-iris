import logging
import fastjsonschema

from .. exceptions import PathError
from ..schemas import slack_schema

L = logging.getLogger(__name__)


#


class SendMSTeamsOrchestrator(object):

	ValidationSchemaSlack = fastjsonschema.compile(slack_schema)


	def __init__(self, app):
		# formatters
		self.JinjaService = app.get_service("JinjaService")
		# output
		self.MSTeamsOutputService = app.get_service("MSTeamsOutputService")
		# location of slack templates

	async def send_to_teams(self, msg):

		body = msg['body']
		# if params no provided pass empty params
		# - primarily use absolute path - starts with "/"
		# - if absolute path is used, check it start with "/Templates"
		# - if it is not absolute path, it is file name - assume it's a file in Templates folder

		# templates must be stores in /Templates/Slack
		if not body['template'].startswith("/Templates/Slack/"):
			raise PathError(path=body['template'])

		body["params"] = body.get("params", {})
		output = await self.JinjaService.format(body["template"], body["params"])

		await self.MSTeamsOutputService.send(output)