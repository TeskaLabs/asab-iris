import logging


L = logging.getLogger(__name__)


#


class SendSlackOrchestrator(object):


	def __init__(self, app):
		# formatters
		self.JinjaService = app.get_service("JinjaService")
		# output
		self.SlackOutputService = app.get_service("SlackOutputService")


	async def send_to_slack(self, msg):
		body = msg.get("body", None)
		if body is not 	None:
			body = await self.JinjaService.format(body['template'], body['params'])
			await self.SlackOutputService.send(body)
		else:
			raise RuntimeError("Failed to send message to Slack. Reason: Missing body info.")
