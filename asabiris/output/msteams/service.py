import configparser
import logging

import aiohttp

import asab

from ...output_abc import OutputABC

#

L = logging.getLogger(__name__)

#


class MSTeamsOutputService(asab.Service, OutputABC):
	def __init__(self, app, service_name="MSTeamsOutputService"):
		super().__init__(app, service_name)
		try:
			self.TeamsWebhookUrl = asab.Config.get("msteams", "webhook_url")
		except configparser.NoOptionError as e:
			L.error("Please provide webhook_url in slack configuration section.")
			raise e
		except configparser.NoSectionError:
			self.TeamsWebhookUrl = None

	async def send(self, payload):
		if self.TeamsWebhookUrl is None:
			return
		async with aiohttp.ClientSession() as session:
			async with session.post(self.TeamsWebhookUrl, json=payload) as resp:
				if resp.status == 200:
					return True
				else:
					L.warning(
						"Sending alert to Teams was NOT successful. Response status: {}, response: {}".format(
							resp.status,
							await resp.text()))
