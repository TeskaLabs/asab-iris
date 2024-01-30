import configparser
import logging

import aiohttp

import asab

from ...output_abc import OutputABC

from ...errors import ASABIrisError, ErrorCode

#

L = logging.getLogger(__name__)

#


class MSTeamsOutputService(asab.Service, OutputABC):

	def __init__(self, app, service_name="MSTeamsOutputService"):
		super().__init__(app, service_name)
		try:
			self.TeamsWebhookUrl = asab.Config.get("msteams", "webhook_url")
		except (configparser.NoOptionError, configparser.NoSectionError) as e:
			L.error("Please provide webhook_url in slack configuration section.")
			raise e


	async def send(self, body):
		if self.TeamsWebhookUrl is None:
			return

		adaptive_card = {
			"type": "message",
			"attachments": [
				{
					"contentType": "application/vnd.microsoft.card.adaptive",
					"contentUrl": None,
					"content": {
						"$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
						"type": "AdaptiveCard",
						"version": "1.2",
						"body": [
							{
								"type": "TextBlock",
								"text": body
							}
						]
					}
				}
			]
		}
		try:
			async with aiohttp.ClientSession() as session:
				async with session.post(self.TeamsWebhookUrl, json=adaptive_card) as resp:
					if resp.status == 200:
						return True
					else:
						L.warning(
							"Sending alert to Teams was NOT successful. Response status: {}, response: {}".format(
								resp.status,
								await resp.text())
						)
		except Exception as e:
			raise ASABIrisError(
				ErrorCode.GENERAL_ERROR,
				tech_message="Error encountered sending message to MS Teams. Reason: {}".format( str(e)),
				error_i18n_key="Error occurred while sending message to MS Teams.  Reason: '{{error_message}}'.",
				error_dict={
					"error_message": str(e)
				}
			)
