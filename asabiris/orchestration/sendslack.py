import logging


L = logging.getLogger(__name__)


#


class SendSlackOrchestrator(object):


	def __init__(self, app):

		self.JinjaService = app.get_service("JinjaService")

	async def send_to_slack(self, msg):
		body = msg.get("body")
		body = await self.JinjaService.format(body['template'], body['params'])
		await self.App.SlackOutputService.send(body)
