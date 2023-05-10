import configparser
import logging
import json

import aiohttp

import asab

from ...output_abc import OutputABC

#

L = logging.getLogger(__name__)

#


class MSTeamsOutputService(asab.Service, OutputABC):
	def __init__(self, app, service_name="MSTeamsOutputService"):
		super().__init__(app, service_name)
		# If there is slack configuration section, but no webhook_url, exception is raised.
		try:
			self.TeamsWebhookUrl = asab.Config.get("msteams", "webhook_url")
		except configparser.NoOptionError as e:
			L.error("Please provide webhook_url in slack configuration section.")
			raise e
		except configparser.NoSectionError:
			self.TeamsWebhookUrl = None

	async def send(self, body):
		if self.TeamsWebhookUrl is None:
			return
		async with aiohttp.ClientSession() as session:
			headers = {"Content-Type": "application/json"}
			async with session.post(self.TeamsWebhookUrl, json=json.dumps(body), headers=headers) as resp:
				if resp.status != 200:
					L.warning(
						"Sending alert to Teams was NOT successful. Response status: {}, response: {}".format(
							resp.status,
							await resp.text()))