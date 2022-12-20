import configparser
import logging

import aiohttp

import asab

from ...output_abc import OutputABC

#

L = logging.getLogger(__name__)

#


class SlackOutputService(asab.Service, OutputABC):
	def __init__(self, app, service_name="SlackOutputService"):
		super().__init__(app, service_name)
		# If there is slack configuration section, but no webhook_url, exception is raised.
		try:
			self.SlackWebhookUrl = asab.Config.get("slack", "webhook_url")
		except configparser.NoOptionError as e:
			L.error("Please provide webhook_url in slack configuration section.")
			raise e
		except configparser.NoSectionError:
			self.SlackWebhookUrl = None

	async def send(self, body):
		if self.SlackWebhookUrl is None:
			return
		async with aiohttp.ClientSession() as session:
			async with session.post(self.SlackWebhookUrl, json={"text": body}) as resp:
				if resp.status != 200:
					L.warning(
						"Sending alert to Slack was NOT successful. Response status: {}, response: {}".format(
							resp.status,
							await resp.text()))
